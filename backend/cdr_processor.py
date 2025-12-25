import pandas as pd
from datetime import datetime
from typing import Dict, Optional
import re
import uuid
import os
import json
from models import CDRRecord, VENDOR_FORMATS, CallType, CallDirection, CallStatus
from database import get_database
from shapely.geometry import Point, Polygon

async def check_geofence_breach(record, manager):
    db = await get_database()
    geofences = await db.geofences.find({"suspect_name": record["suspect_name"]}).to_list(1000)

    if "location_lat" in record and "location_lon" in record:
        point = Point(record["location_lon"], record["location_lat"])
        for geofence in geofences:
            polygon = Polygon(geofence["geometry"]["coordinates"][0])
            if polygon.contains(point):
                alert_message = {
                    "type": "geofence_breach",
                    "suspect_name": record["suspect_name"],
                    "geofence_name": geofence["name"],
                    "timestamp": record["call_start_time"].isoformat(),
                    "location": {
                        "lat": record["location_lat"],
                        "lon": record["location_lon"]
                    }
                }
                await manager.broadcast(json.dumps(alert_message))

async def detect_format(file_path: str) -> Optional[Dict]:
    """Auto-detect CDR file format and vendor"""
    try:
        # Read first few rows
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, nrows=5)
        elif file_path.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_path, nrows=5)
        else:
            return None

        columns = [col.lower().strip() for col in df.columns]

        # Detect vendor based on column names
        detected_vendor = None
        column_mapping = {}

        for vendor, mappings in VENDOR_FORMATS.items():
            matches = 0
            temp_mapping = {}

            for standard_field, possible_names in mappings.items():
                for col in columns:
                    if col in possible_names:
                        temp_mapping[standard_field] = col
                        matches += 1
                        break

            if matches > len(column_mapping):
                detected_vendor = vendor
                column_mapping = temp_mapping

        # If no vendor detected, try standard format
        if not detected_vendor:
            detected_vendor = "standard"
            for standard_field, possible_names in VENDOR_FORMATS["standard"].items():
                for col in columns:
                    if col in possible_names:
                        column_mapping[standard_field] = col
                        break

        return {
            "vendor": detected_vendor,
            "column_mapping": column_mapping,
            "columns_found": columns
        }
    except Exception as e:
        print(f"Format detection error: {e}")
        return None

def clean_value(value):
    """Clean and normalize data values"""
    if pd.isna(value) or value == '' or value == 'nan' or value == 'None':
        return None
    if isinstance(value, str):
        value = value.strip()
        if value.lower() in ['nan', 'none', 'null', '']:
            return None
    return value

def parse_datetime(value) -> Optional[datetime]:
    """Parse various datetime formats"""
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if value is None or value == '':
        return None

    # Common datetime formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",  # DD-MM-YYYY HH:MM:SS
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y"  # DD-MM-YYYY
    ]

    for fmt in formats:
        try:
            if isinstance(value, str):
                result = datetime.strptime(value, fmt)
                return result
            elif isinstance(value, pd.Timestamp):
                return value.to_pydatetime()
        except Exception as e:
            continue

    return None

def normalize_phone_number(number):
    """Normalize phone number format"""
    if pd.isna(number) or number is None:
        return None

    # Remove non-digit characters except +
    number = str(number).strip()
    number = re.sub(r'[^\d+]', '', number)

    return number if number else None

def infer_call_type(row: pd.Series, column_mapping: Dict) -> CallType:
    """Infer call type from row data"""
    call_type_col = column_mapping.get("call_type")
    if call_type_col and call_type_col in row.index:
        value = str(row[call_type_col]).lower()
        if "sms" in value or "text" in value:
            return CallType.SMS
        elif "data" in value or "internet" in value:
            return CallType.DATA
    return CallType.VOICE

def infer_direction(row: pd.Series, column_mapping: Dict, suspect_number: Optional[str]) -> CallDirection:
    """Infer call direction"""
    direction_col = column_mapping.get("direction")
    if direction_col and direction_col in row.index:
        value = str(row[direction_col]).lower()
        if "incoming" in value or "in" in value or "received" in value:
            return CallDirection.INCOMING
        elif "outgoing" in value or "out" in value or "originated" in value:
            return CallDirection.OUTGOING

    # Infer from suspect number
    if suspect_number:
        calling_col = column_mapping.get("calling_number")
        if calling_col and calling_col in row.index:
            if str(row[calling_col]) == suspect_number:
                return CallDirection.OUTGOING
            else:
                return CallDirection.INCOMING

    return CallDirection.OUTGOING

async def process_cdr_file(
    file_path: str,
    suspect_name: Optional[str] = None,
    format_info: Optional[Dict] = None,
    manager=None,
    session_id: Optional[str] = None
) -> Dict:
    """Process CDR file and insert into database"""
    try:
        # Generate session_id if not provided (use filename-based ID)
        if not session_id:
            filename = os.path.basename(file_path)
            session_id = f"session_{uuid.uuid4().hex[:12]}_{int(datetime.now().timestamp())}"

        # Handle JSON files
        if file_path.endswith('.json'):
            return await process_json_file(file_path, suspect_name, manager, session_id)

        # Read file with header detection
        if file_path.endswith('.csv'):
            # Try to detect header row
            df = pd.read_csv(file_path)
            # Skip empty rows and metadata headers
            df = df.dropna(how='all')  # Remove completely empty rows
        elif file_path.endswith(('.xls', '.xlsx')):
            # For Excel, try to find the actual data header
            # Read first 20 rows without header to inspect structure
            df_preview = pd.read_excel(file_path, header=None, nrows=20)

            # Find the best header row by checking for meaningful column names
            # A good header should have:
            # 1. Multiple non-empty values
            # 2. Values that look like column names (not all dashes, not "Unnamed")
            # 3. Not all numeric values
            header_row = 0
            best_score = 0

            for idx in range(min(20, len(df_preview))):
                row = df_preview.iloc[idx]
                non_null_count = row.notna().sum()

                # Skip rows with too few values
                if non_null_count < 3:
                    continue

                # Check if values look like column headers
                score = 0
                valid_names = 0
                for val in row.values:
                    if pd.notna(val):
                        val_str = str(val).strip()
                        # Good column name indicators
                        if val_str and len(val_str) > 0:
                            if not val_str.startswith('Unnamed'):
                                if not val_str.replace('-', '').replace('_', '').strip() == '':
                                    if not val_str.replace('-', '').replace('_', '').replace('=', '').strip() == '':
                                        valid_names += 1
                                        # Bonus for common CDR column name patterns
                                        val_lower = val_str.lower()
                                        if any(keyword in val_lower for keyword in ['number', 'time', 'date', 'duration', 'call', 'msisdn', 'imei', 'imsi', 'cell', 'tower', 'location']):
                                            score += 2
                                        else:
                                            score += 1

                # Require at least 3 valid column names
                if valid_names >= 3 and score > best_score:
                    best_score = score
                    header_row = idx

            # Read full file with detected header
            df = pd.read_excel(file_path, header=header_row)
            # Skip empty rows
            df = df.dropna(how='all')

            # Clean up column names - remove "Unnamed" columns and normalize
            df.columns = [str(col).strip() if pd.notna(col) and not str(col).startswith('Unnamed') else f'Column_{i}' for i, col in enumerate(df.columns)]

            # Remove rows that are clearly footers (e.g., contain "Total", "Page", etc.)
            footer_keywords = ['total', 'page', 'summary', 'disclaimer', 'note:', 'note :']
            mask = df.astype(str).apply(
                lambda x: x.str.lower().str.contains('|'.join(footer_keywords), na=False)
            ).any(axis=1)
            df = df[~mask]
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

        # Build column mapping from actual DataFrame columns
        # This is more reliable than pre-detection since we now have the correct header
        column_mapping = {}

        # Normalize column names for matching (lowercase, remove special chars)
        def normalize_col_name(col):
            return str(col).lower().strip().replace('/', ' ').replace('-', ' ').replace('_', ' ')

        # Map actual column names to standard fields
        for col in df.columns:
            col_normalized = normalize_col_name(col)

            # Try to match against all possible field names
            for standard_field, possible_names in VENDOR_FORMATS["standard"].items():
                for possible_name in possible_names:
                    possible_normalized = normalize_col_name(possible_name)
                    # Check if column name contains any of the possible names or vice versa
                    if (possible_normalized in col_normalized or
                        col_normalized in possible_normalized or
                        any(word in col_normalized for word in possible_normalized.split() if len(word) > 3)):
                        if standard_field not in column_mapping:  # Don't overwrite if already mapped
                            column_mapping[standard_field] = col
                            break
                if standard_field in column_mapping:
                    break

            # Special handling for Airtel-specific column names
            if "a party" in col_normalized or "target" in col_normalized or "a-party" in col_normalized:
                if "calling_number" not in column_mapping:
                    column_mapping["calling_number"] = col
            elif "b party" in col_normalized or "b-party" in col_normalized:
                if "called_number" not in column_mapping:
                    column_mapping["called_number"] = col
            elif "call initiation time" in col_normalized or ("initiation" in col_normalized and "time" in col_normalized):
                if "call_start_time" not in column_mapping:
                    column_mapping["call_start_time"] = col
            elif "call date" in col_normalized or ("date" in col_normalized and "time" not in col_normalized):
                if "call_date" not in column_mapping:
                    column_mapping["call_date"] = col
            elif "duration" in col_normalized:
                if "duration_seconds" not in column_mapping:
                    column_mapping["duration_seconds"] = col
            elif "cell" in col_normalized and "id" in col_normalized:
                if "cell_tower_id" not in column_mapping:
                    column_mapping["cell_tower_id"] = col
            elif "bts location" in col_normalized or ("location" in col_normalized and "bts" in col_normalized):
                if "cell_tower_id" not in column_mapping:
                    column_mapping["cell_tower_id"] = col
            elif "imei" in col_normalized:
                if "imei" not in column_mapping:
                    column_mapping["imei"] = col
            elif "imsi" in col_normalized:
                if "imsi" not in column_mapping:
                    column_mapping["imsi"] = col
            elif "roaming network" in col_normalized or "circle" in col_normalized:
                if "circle" not in column_mapping:
                    column_mapping["circle"] = col

        # Get database
        db = await get_database()

        # Process rows
        records = []
        suspect_number = None
        validation_failures = {"missing_msisdn":0,"missing_time":0,"other":0}

        for idx, row in df.iterrows():
            try:
                # Map columns
                record_data = {}

                # Get suspect number from first row if available
                if suspect_number is None and suspect_name:
                    calling_col = column_mapping.get("calling_number")
                    if calling_col and calling_col in row.index:
                        suspect_number = normalize_phone_number(row[calling_col])

                # Map all fields
                for standard_field, source_col in column_mapping.items():
                    if source_col in row.index:
                        value = clean_value(row[source_col])
                        if value is not None:
                            record_data[standard_field] = value

                # Fill missing fields with direct column names
                for col in df.columns:
                    col_lower = col.lower().strip()
                    if col_lower not in [v.lower() for v in column_mapping.values()]:
                        # Try to match standard fields
                        for standard_field, possible_names in VENDOR_FORMATS["standard"].items():
                            if col_lower in [n.lower() for n in possible_names]:
                                value = clean_value(row[col])
                                if value is not None:
                                    record_data[standard_field] = value
                                break

                # Parse datetime fields - handle date + time combination
                # Check if call_start_time exists but is None/empty - if so, try to combine date+time
                has_call_start_time = "call_start_time" in record_data
                call_start_time_value = record_data.get("call_start_time")
                needs_combination = not call_start_time_value or (isinstance(call_start_time_value, str) and not call_start_time_value.strip())

                # Check if call_start_time is just a time (HH:MM:SS or HH:MM format) without a date
                is_time_only = False
                if isinstance(call_start_time_value, str) and call_start_time_value.strip():
                    time_str = call_start_time_value.strip()
                    # Check if it matches time-only patterns (HH:MM:SS or HH:MM)
                    if re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', time_str):
                        is_time_only = True
                        needs_combination = True

                if has_call_start_time and not needs_combination:
                    # Already have valid time field - try to parse it
                    parsed = parse_datetime(record_data["call_start_time"])
                    if parsed:
                        record_data["call_start_time"] = parsed
                    else:
                        # Parsing failed, might be time-only, try combining with date
                        needs_combination = True

                if needs_combination and "call_date" in record_data:
                    # Try to find time field and combine
                    time_col = column_mapping.get("call_start_time")
                    if not time_col:
                        # Look for time-related columns
                        for col in df.columns:
                            col_lower = str(col).lower()
                            if ("time" in col_lower or "initiation" in col_lower) and "date" not in col_lower:
                                time_col = col
                                break

                    # Get time value - either from mapped column or from record_data if it's time-only
                    time_val = None
                    if is_time_only and call_start_time_value:
                        time_val = call_start_time_value
                    elif time_col and time_col in row.index:
                        time_val = clean_value(row[time_col])

                    if time_val:
                        # Combine date and time
                        date_val = record_data.get("call_date")
                        if date_val:
                            combined = f"{date_val} {time_val}"
                            record_data["call_start_time"] = parse_datetime(combined)
                        else:
                            record_data["call_start_time"] = parse_datetime(time_val)
                    else:
                        # Just parse the date
                        parsed_date = parse_datetime(record_data["call_date"])
                        if parsed_date:
                            record_data["call_start_time"] = parsed_date

                if "call_end_time" in record_data:
                    record_data["call_end_time"] = parse_datetime(record_data["call_end_time"])

                # Calculate duration if not present
                if "duration_seconds" not in record_data or record_data["duration_seconds"] is None:
                    if "call_start_time" in record_data and "call_end_time" in record_data:
                        if record_data["call_start_time"] and record_data["call_end_time"]:
                            delta = record_data["call_end_time"] - record_data["call_start_time"]
                            record_data["duration_seconds"] = delta.total_seconds()

                # Normalize phone numbers
                if "calling_number" in record_data:
                    record_data["calling_number"] = normalize_phone_number(record_data["calling_number"])
                if "called_number" in record_data:
                    record_data["called_number"] = normalize_phone_number(record_data["called_number"])

                # Infer call type and direction
                if "call_type" not in record_data:
                    record_data["call_type"] = infer_call_type(row, column_mapping)
                else:
                    value = str(record_data["call_type"]).lower()
                    if "sms" in value:
                        record_data["call_type"] = CallType.SMS
                    elif "data" in value:
                        record_data["call_type"] = CallType.DATA
                    else:
                        record_data["call_type"] = CallType.VOICE

                if "direction" not in record_data:
                    record_data["direction"] = infer_direction(row, column_mapping, suspect_number)
                else:
                    value = str(record_data["direction"]).lower()
                    if "incoming" in value or "in" in value:
                        record_data["direction"] = CallDirection.INCOMING
                    else:
                        record_data["direction"] = CallDirection.OUTGOING

                # Set session_id (primary identifier) and optional suspect_name
                record_data["session_id"] = session_id
                if suspect_name:
                    record_data["suspect_name"] = suspect_name

                # Generate call_id if missing
                if "call_id" not in record_data or not record_data["call_id"]:
                    calling_num = record_data.get('calling_number', 'unknown')
                    call_time = record_data.get('call_start_time')
                    if call_time:
                        timestamp = call_time.timestamp() if isinstance(call_time, datetime) else datetime.now().timestamp()
                    else:
                        timestamp = datetime.now().timestamp()
                    record_data["call_id"] = f"{calling_num}_{timestamp}"

                # Normalize to canonical schema
                # Map to msisdn_a and msisdn_b
                if "calling_number" in record_data:
                    record_data["msisdn_a"] = record_data["calling_number"]
                if "called_number" in record_data:
                    record_data["msisdn_b"] = record_data["called_number"]

                # Map cell_tower_id to cell_id
                if "cell_tower_id" in record_data and not record_data.get("cell_id"):
                    record_data["cell_id"] = record_data["cell_tower_id"]

                # Map duration_seconds to call_duration_sec
                if "duration_seconds" in record_data:
                    record_data["call_duration_sec"] = record_data["duration_seconds"]

                # Extract call_date from call_start_time if not already set
                if "call_date" not in record_data and "call_start_time" in record_data and record_data["call_start_time"]:
                    if isinstance(record_data["call_start_time"], datetime):
                        record_data["call_date"] = record_data["call_start_time"].strftime("%Y-%m-%d")

                # Generate record_id if missing
                if "record_id" not in record_data:
                    record_data["record_id"] = record_data.get("call_id", f"REC_{idx}_{int(datetime.now().timestamp())}")

                # Store raw row reference
                record_data["raw_row_reference"] = f"Row_{idx + 1}"

                # Convert numeric fields
                for field in ["duration_seconds", "cost", "data_volume_mb"]:
                    if field in record_data and record_data[field] is not None:
                        try:
                            record_data[field] = float(record_data[field])
                        except:
                            record_data[field] = None

                for field in ["location_lat", "location_lon"]:
                    if field in record_data and record_data[field] is not None:
                        try:
                            record_data[field] = float(record_data[field])
                        except:
                            record_data[field] = None

                # Parse LAC, MNC, MCC fields
                for field in ["lac", "mnc", "mcc"]:
                    if field in record_data and record_data[field] is not None:
                        try:
                            record_data[field] = int(record_data[field])
                        except:
                            record_data[field] = None

                # Skip rows that are clearly separators (all dashes, empty, or invalid)
                calling_val = record_data.get("calling_number") or record_data.get("msisdn_a")
                called_val = record_data.get("called_number") or record_data.get("msisdn_b")

                # Check if values are just dashes or separators
                def is_separator(val):
                    if not val or pd.isna(val):
                        return True
                    val_str = str(val).strip()
                    if not val_str or val_str == '':
                        return True
                    # Check if it's all dashes, underscores, or equals signs
                    if all(c in ['-', '_', '=', ' '] for c in val_str):
                        return True
                    return False

                if is_separator(calling_val) or is_separator(called_val):
                    validation_failures["missing_msisdn"] += 1
                    continue

                # Validate required fields (check both canonical and legacy fields)
                has_msisdn_a = record_data.get("msisdn_a") or record_data.get("calling_number")
                has_msisdn_b = record_data.get("msisdn_b") or record_data.get("called_number")

                if not has_msisdn_a or not has_msisdn_b:
                    validation_failures["missing_msisdn"] += 1
                    continue

                if not record_data.get("call_start_time"):
                    validation_failures["missing_time"] += 1
                    continue

                # Convert IMEI and IMSI to strings (Excel may read them as floats)
                if "imei" in record_data and record_data["imei"] is not None:
                    if isinstance(record_data["imei"], (int, float)):
                        # Convert to int first to remove decimal, then to string
                        record_data["imei"] = str(int(record_data["imei"]))
                    else:
                        record_data["imei"] = str(record_data["imei"])

                if "imsi" in record_data and record_data["imsi"] is not None:
                    if isinstance(record_data["imsi"], (int, float)):
                        # Convert to int first to remove decimal, then to string
                        record_data["imsi"] = str(int(record_data["imsi"]))
                    else:
                        record_data["imsi"] = str(record_data["imsi"])

                # Create CDR record
                cdr_record = CDRRecord(**record_data)
                records.append(cdr_record.dict())

                if manager:
                    await check_geofence_breach(cdr_record.dict(), manager)

            except Exception as e:
                validation_failures["other"] += 1
                print(f"Error processing row {idx}: {e}")
                continue

        # Insert into database
        if records:
            result = await db.cdr_records.insert_many(records)
            return {
                "records_inserted": len(result.inserted_ids),
                "session_id": session_id,
                "suspect_name": suspect_name,
                "format_detected": format_info
            }
        else:
            return {
                "records_inserted": 0,
                "session_id": session_id,
                "suspect_name": suspect_name,
                "format_detected": format_info
            }

    except Exception as e:
        raise Exception(f"Error processing CDR file: {str(e)}")

async def process_json_file(
    file_path: str,
    suspect_name: Optional[str] = None,
    manager=None,
    session_id: Optional[str] = None
) -> Dict:
    """Process JSON CDR file and insert into database"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        # Handle different JSON structures
        if isinstance(data, dict):
            # If it's an export format with records array
            if 'records' in data:
                records_data = data['records']
                # Use suspect_name from data if not provided
                if not suspect_name and 'suspect_name' in data:
                    suspect_name = data['suspect_name']
            # If it's a single record
            elif 'calling_number' in data or 'call_id' in data:
                records_data = [data]
            else:
                raise ValueError("Invalid JSON structure: expected 'records' array or CDR record object")
        elif isinstance(data, list):
            records_data = data
        else:
            raise ValueError("Invalid JSON format: expected object or array")

        db = await get_database()
        records = []

        for record_data in records_data:
            try:
                # Parse datetime fields
                if 'call_start_time' in record_data and isinstance(record_data['call_start_time'], str):
                    record_data['call_start_time'] = parse_datetime(record_data['call_start_time'])
                if 'call_end_time' in record_data and isinstance(record_data['call_end_time'], str):
                    record_data['call_end_time'] = parse_datetime(record_data['call_end_time'])

                # Normalize phone numbers
                if 'calling_number' in record_data:
                    record_data['calling_number'] = normalize_phone_number(record_data['calling_number'])
                if 'called_number' in record_data:
                    record_data['called_number'] = normalize_phone_number(record_data['called_number'])

                # Convert enum strings to enum values
                if 'call_type' in record_data and isinstance(record_data['call_type'], str):
                    record_data['call_type'] = CallType(record_data['call_type'].lower())
                if 'direction' in record_data and isinstance(record_data['direction'], str):
                    record_data['direction'] = CallDirection(record_data['direction'].lower())
                if 'call_status' in record_data and isinstance(record_data['call_status'], str):
                    record_data['call_status'] = CallStatus(record_data['call_status'].lower())

                # Set session_id and optional suspect_name
                if not session_id:
                    session_id = f"session_{uuid.uuid4().hex[:12]}_{int(datetime.now().timestamp())}"
                record_data['session_id'] = session_id
                if suspect_name:
                    record_data['suspect_name'] = suspect_name
                elif 'suspect_name' not in record_data:
                    record_data['suspect_name'] = None

                # Generate call_id if missing
                if 'call_id' not in record_data or not record_data['call_id']:
                    calling = record_data.get('calling_number', 'unknown')
                    timestamp = record_data.get('call_start_time', datetime.now())
                    if isinstance(timestamp, str):
                        timestamp = parse_datetime(timestamp) or datetime.now()
                    record_data['call_id'] = f"{calling}_{timestamp.timestamp()}"

                # Validate required fields
                if not record_data.get('calling_number') or not record_data.get('called_number'):
                    continue
                if not record_data.get('call_start_time'):
                    continue

                # Create CDR record
                cdr_record = CDRRecord(**record_data)
                records.append(cdr_record.dict())

                if manager:
                    await check_geofence_breach(cdr_record.dict(), manager)

            except Exception as e:
                print(f"Error processing JSON record: {e}")
                continue

        # Insert into database
        if records:
            result = await db.cdr_records.insert_many(records)
            return {
                "records_inserted": len(result.inserted_ids),
                "session_id": session_id,
                "suspect_name": suspect_name,
                "format_detected": {"vendor": "json", "type": "json_import"}
            }
        else:
            return {
                "records_inserted": 0,
                "session_id": session_id,
                "suspect_name": suspect_name,
                "format_detected": {"vendor": "json", "type": "json_import"}
            }

    except Exception as e:
        raise Exception(f"Error processing JSON file: {str(e)}")
