import pandas as pd
from datetime import datetime
from typing import Dict, Optional
import re
from models import CDRRecord, VENDOR_FORMATS, CallType, CallDirection, CallStatus
from database import get_database

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
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y"
    ]

    for fmt in formats:
        try:
            if isinstance(value, str):
                return datetime.strptime(value, fmt)
            elif isinstance(value, pd.Timestamp):
                return value.to_pydatetime()
        except:
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
    format_info: Optional[Dict] = None
) -> Dict:
    """Process CDR file and insert into database"""
    try:
        # Handle JSON files
        if file_path.endswith('.json'):
            return await process_json_file(file_path, suspect_name)

        # Read file
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

        # Auto-detect format if not provided
        if format_info is None:
            format_info = await detect_format(file_path)

        if format_info is None:
            format_info = {"vendor": "standard", "column_mapping": {}}

        column_mapping = format_info.get("column_mapping", {})

        # Get database
        db = await get_database()

        # Process rows
        records = []
        suspect_number = None

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

                # Parse datetime fields
                if "call_start_time" in record_data:
                    record_data["call_start_time"] = parse_datetime(record_data["call_start_time"])
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

                # Set suspect name
                if suspect_name:
                    record_data["suspect_name"] = suspect_name

                # Generate call_id if missing
                if "call_id" not in record_data or not record_data["call_id"]:
                    record_data["call_id"] = f"{record_data.get('calling_number', 'unknown')}_{record_data.get('call_start_time', datetime.now()).timestamp()}"

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

                # Validate required fields
                if not record_data.get("calling_number") or not record_data.get("called_number"):
                    continue

                if not record_data.get("call_start_time"):
                    continue

                # Create CDR record
                cdr_record = CDRRecord(**record_data)
                records.append(cdr_record.dict())

            except Exception as e:
                print(f"Error processing row {idx}: {e}")
                continue

        # Insert into database
        if records:
            result = await db.cdr_records.insert_many(records)
            return {
                "records_inserted": len(result.inserted_ids),
                "suspect_name": suspect_name,
                "format_detected": format_info
            }
        else:
            return {
                "records_inserted": 0,
                "suspect_name": suspect_name,
                "format_detected": format_info
            }

    except Exception as e:
        raise Exception(f"Error processing CDR file: {str(e)}")

async def process_json_file(
    file_path: str,
    suspect_name: Optional[str] = None
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

                # Set suspect name
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

            except Exception as e:
                print(f"Error processing JSON record: {e}")
                continue

        # Insert into database
        if records:
            result = await db.cdr_records.insert_many(records)
            return {
                "records_inserted": len(result.inserted_ids),
                "suspect_name": suspect_name,
                "format_detected": {"vendor": "json", "type": "json_import"}
            }
        else:
            return {
                "records_inserted": 0,
                "suspect_name": suspect_name,
                "format_detected": {"vendor": "json", "type": "json_import"}
            }

    except Exception as e:
        raise Exception(f"Error processing JSON file: {str(e)}")
