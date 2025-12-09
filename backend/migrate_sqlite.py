#!/usr/bin/env python3
"""
SQLite to MongoDB Migration Tool
Migrates CDR data from SQLite database to MongoDB
"""

import sqlite3
import asyncio
import sys
from datetime import datetime
from typing import Optional
from database import get_database
from models import CDRRecord, CallType, CallDirection, CallStatus

def parse_datetime(value) -> Optional[datetime]:
    """Parse datetime from various formats"""
    if value is None:
        return None

    if isinstance(value, str):
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except:
                continue

    return None

def normalize_call_type(value: str) -> CallType:
    """Normalize call type"""
    if not value:
        return CallType.VOICE

    value_lower = str(value).lower()
    if "sms" in value_lower or "text" in value_lower:
        return CallType.SMS
    elif "data" in value_lower or "internet" in value_lower:
        return CallType.DATA
    return CallType.VOICE

def normalize_direction(value: str) -> CallDirection:
    """Normalize call direction"""
    if not value:
        return CallDirection.OUTGOING

    value_lower = str(value).lower()
    if "incoming" in value_lower or "in" in value_lower or "received" in value_lower:
        return CallDirection.INCOMING
    return CallDirection.OUTGOING

def normalize_status(value: str) -> CallStatus:
    """Normalize call status"""
    if not value:
        return CallStatus.COMPLETED

    value_lower = str(value).lower()
    if "failed" in value_lower:
        return CallStatus.FAILED
    elif "missed" in value_lower:
        return CallStatus.MISSED
    elif "busy" in value_lower:
        return CallStatus.BUSY
    return CallStatus.COMPLETED

async def migrate_sqlite_to_mongodb(sqlite_path: str, suspect_name: Optional[str] = None):
    """Migrate CDR data from SQLite to MongoDB"""

    print(f"📂 Opening SQLite database: {sqlite_path}")
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    # Get table name (assume 'cdr' or 'cdr_records')
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    table_name = None
    for name in ['cdr_records', 'cdr', 'records', 'calls']:
        if name in tables:
            table_name = name
            break

    if not table_name:
        table_name = tables[0] if tables else None

    if not table_name:
        print("❌ No table found in SQLite database")
        return

    print(f"📊 Found table: {table_name}")

    # Get column names
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1]: row[0] for row in cursor.fetchall()}
    print(f"📋 Columns: {list(columns.keys())}")

    # Get all records
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    print(f"📦 Found {len(rows)} records to migrate")

    # Get MongoDB database
    db = await get_database()

    # Map SQLite columns to CDR fields
    column_mapping = {
        'calling_number': ['calling_number', 'caller', 'from_number', 'a_number', 'msisdn_a'],
        'called_number': ['called_number', 'callee', 'to_number', 'b_number', 'msisdn_b'],
        'call_start_time': ['call_start_time', 'start_time', 'timestamp', 'event_time'],
        'call_end_time': ['call_end_time', 'end_time'],
        'duration_seconds': ['duration_seconds', 'duration', 'call_duration'],
        'call_type': ['call_type', 'type', 'service_type'],
        'direction': ['direction', 'call_direction'],
        'cell_tower_id': ['cell_tower_id', 'tower_id', 'cell_id', 'lac'],
        'location_lat': ['location_lat', 'latitude', 'lat'],
        'location_lon': ['location_lon', 'longitude', 'lon'],
        'imei': ['imei', 'device_imei'],
        'imsi': ['imsi', 'subscriber_imsi'],
        'cost': ['cost', 'charge', 'amount'],
        'data_volume_mb': ['data_volume_mb', 'data_volume', 'volume_mb'],
        'call_status': ['call_status', 'status'],
        'sms_content': ['sms_content', 'message', 'text']
    }

    def find_column(field_name):
        """Find SQLite column name for a field"""
        possible_names = column_mapping.get(field_name, [])
        for name in possible_names:
            if name in columns:
                return name
        return None

    # Process and insert records
    records = []
    inserted = 0

    for row in rows:
        try:
            # Create dictionary from row
            row_dict = {col: row[idx] for col, idx in columns.items()}

            # Map to CDR record
            record_data = {}

            # Map each field
            for field, sqlite_col in [(k, find_column(k)) for k in column_mapping.keys()]:
                if sqlite_col and sqlite_col in row_dict:
                    value = row_dict[sqlite_col]
                    if value is not None and value != '':
                        record_data[field] = value

            # Parse datetime fields
            if 'call_start_time' in record_data:
                record_data['call_start_time'] = parse_datetime(record_data['call_start_time'])
            if 'call_end_time' in record_data:
                record_data['call_end_time'] = parse_datetime(record_data['call_end_time'])

            # Calculate duration if not present
            if 'duration_seconds' not in record_data or not record_data['duration_seconds']:
                if 'call_start_time' in record_data and 'call_end_time' in record_data:
                    if record_data['call_start_time'] and record_data['call_end_time']:
                        delta = record_data['call_end_time'] - record_data['call_start_time']
                        record_data['duration_seconds'] = delta.total_seconds()

            # Normalize enums
            if 'call_type' in record_data:
                record_data['call_type'] = normalize_call_type(record_data['call_type'])
            else:
                record_data['call_type'] = CallType.VOICE

            if 'direction' in record_data:
                record_data['direction'] = normalize_direction(record_data['direction'])
            else:
                record_data['direction'] = CallDirection.OUTGOING

            if 'call_status' in record_data:
                record_data['call_status'] = normalize_status(record_data['call_status'])
            else:
                record_data['call_status'] = CallStatus.COMPLETED

            # Set suspect name
            if suspect_name:
                record_data['suspect_name'] = suspect_name

            # Generate call_id if missing
            if 'call_id' not in record_data or not record_data['call_id']:
                calling = record_data.get('calling_number', 'unknown')
                timestamp = record_data.get('call_start_time', datetime.now())
                record_data['call_id'] = f"{calling}_{timestamp.timestamp()}"

            # Convert numeric fields
            for field in ['duration_seconds', 'cost', 'data_volume_mb', 'location_lat', 'location_lon']:
                if field in record_data and record_data[field] is not None:
                    try:
                        record_data[field] = float(record_data[field])
                    except:
                        record_data[field] = None

            # Validate required fields
            if not record_data.get('calling_number') or not record_data.get('called_number'):
                continue

            if not record_data.get('call_start_time'):
                continue

            # Create CDR record
            cdr_record = CDRRecord(**record_data)
            records.append(cdr_record.dict())

            # Insert in batches
            if len(records) >= 1000:
                await db.cdr_records.insert_many(records)
                inserted += len(records)
                print(f"✅ Inserted {inserted}/{len(rows)} records...")
                records = []

        except Exception as e:
            print(f"⚠️  Error processing record: {e}")
            continue

    # Insert remaining records
    if records:
        await db.cdr_records.insert_many(records)
        inserted += len(records)

    conn.close()

    print(f"✅ Migration complete! Inserted {inserted} records into MongoDB")
    return inserted

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate_sqlite.py <sqlite_file> [suspect_name]")
        sys.exit(1)

    sqlite_file = sys.argv[1]
    suspect_name = sys.argv[2] if len(sys.argv) > 2 else None

    asyncio.run(migrate_sqlite_to_mongodb(sqlite_file, suspect_name))
