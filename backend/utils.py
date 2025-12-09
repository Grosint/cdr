import random
from datetime import datetime, timedelta
from database import get_database
from models import CallType, CallDirection, CallStatus
import json
import os
import csv

# Sample phone numbers by country
SAMPLE_NUMBERS = {
    "US": ["+1555", "+1415", "+1212", "+1310"],
    "UK": ["+4477", "+4479", "+4478"],
    "IN": ["+9191", "+9198", "+9199"],
    "PK": ["+9230", "+9231", "+9232"]
}

# Sample cell tower IDs
SAMPLE_TOWERS = [
    {"id": "TOWER_001", "lat": 37.7749, "lon": -122.4194},
    {"id": "TOWER_002", "lat": 37.7849, "lon": -122.4094},
    {"id": "TOWER_003", "lat": 37.7649, "lon": -122.4294},
    {"id": "TOWER_004", "lat": 37.7549, "lon": -122.4394},
    {"id": "TOWER_005", "lat": 37.7949, "lon": -122.3994},
]

# Sample IMEIs
SAMPLE_IMEIS = [
    "123456789012345",
    "234567890123456",
    "345678901234567",
    "456789012345678",
    "567890123456789"
]

# Sample IMSIs
SAMPLE_IMSIS = [
    "310150123456789",
    "310150234567890",
    "310150345678901"
]

async def generate_sample_data(suspect_name: str, record_count: int = 100) -> int:
    """Generate realistic sample CDR data"""
    db = await get_database()

    records = []
    base_time = datetime.now() - timedelta(days=30)

    # Generate suspect's number
    suspect_number = random.choice(SAMPLE_NUMBERS["US"]) + str(random.randint(1000000, 9999999))

    # Generate frequent contacts
    frequent_contacts = [
        random.choice(SAMPLE_NUMBERS["US"]) + str(random.randint(1000000, 9999999))
        for _ in range(5)
    ]

    for i in range(record_count):
        # Random time within last 30 days
        call_start = base_time + timedelta(
            days=random.randint(0, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )

        # Duration (seconds)
        duration = random.randint(10, 3600)
        call_end = call_start + timedelta(seconds=duration)

        # Call type
        call_type = random.choices(
            [CallType.VOICE, CallType.SMS, CallType.DATA],
            weights=[70, 20, 10]
        )[0]

        # Direction
        direction = random.choice([CallDirection.INCOMING, CallDirection.OUTGOING])

        # Numbers
        if direction == CallDirection.OUTGOING:
            calling_number = suspect_number
            # 60% chance to call frequent contact
            if random.random() < 0.6:
                called_number = random.choice(frequent_contacts)
            else:
                called_number = random.choice(SAMPLE_NUMBERS[random.choice(list(SAMPLE_NUMBERS.keys()))]) + str(random.randint(1000000, 9999999))
        else:
            called_number = suspect_number
            calling_number = random.choice(frequent_contacts) if random.random() < 0.5 else random.choice(SAMPLE_NUMBERS[random.choice(list(SAMPLE_NUMBERS.keys()))]) + str(random.randint(1000000, 9999999))

        # Cell tower
        tower = random.choice(SAMPLE_TOWERS)

        # IMEI (sometimes same device, sometimes different)
        imei = random.choice(SAMPLE_IMEIS) if random.random() < 0.8 else random.choice(SAMPLE_IMEIS)

        # SMS content
        sms_content = None
        if call_type == CallType.SMS:
            sms_templates = [
                "Meeting at 3pm",
                "Call me back",
                "OTP: 123456",
                "Payment received",
                "See you soon"
            ]
            sms_content = random.choice(sms_templates)

        # Data volume
        data_volume = None
        if call_type == CallType.DATA:
            data_volume = random.uniform(0.1, 100.0)

        record = {
            "call_id": f"CDR_{suspect_name}_{i}_{int(call_start.timestamp())}",
            "calling_number": calling_number,
            "called_number": called_number,
            "call_start_time": call_start,
            "call_end_time": call_end,
            "duration_seconds": duration,
            "call_type": call_type.value,
            "direction": direction.value,
            "cell_tower_id": tower["id"],
            "location_lat": tower["lat"] + random.uniform(-0.01, 0.01),
            "location_lon": tower["lon"] + random.uniform(-0.01, 0.01),
            "imei": imei,
            "imsi": random.choice(SAMPLE_IMSIS),
            "cost": random.uniform(0.01, 5.0),
            "data_volume_mb": data_volume,
            "call_status": CallStatus.COMPLETED.value,
            "sms_content": sms_content,
            "suspect_name": suspect_name
        }

        records.append(record)

    # Insert into database
    if records:
        result = await db.cdr_records.insert_many(records)
        return len(result.inserted_ids)

    return 0

async def export_to_json(suspect_name: str) -> str:
    """Export suspect data to JSON file"""
    db = await get_database()

    # Get all records for suspect
    cursor = db.cdr_records.find({"suspect_name": suspect_name})
    records = await cursor.to_list(length=None)

    # Convert ObjectId to string
    for record in records:
        record["_id"] = str(record["_id"])
        if isinstance(record.get("call_start_time"), datetime):
            record["call_start_time"] = record["call_start_time"].isoformat()
        if isinstance(record.get("call_end_time"), datetime):
            record["call_end_time"] = record["call_end_time"].isoformat()

    # Create exports directory (use absolute path)
    exports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")
    os.makedirs(exports_dir, exist_ok=True)

    # Save to file
    filename = os.path.join(exports_dir, f"{suspect_name}_cdr_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(filename, "w") as f:
        json.dump({
            "suspect_name": suspect_name,
            "export_date": datetime.now().isoformat(),
            "record_count": len(records),
            "records": records
        }, f, indent=2, default=str)

    return filename

async def export_to_csv(suspect_name: str) -> str:
    """Export suspect data to CSV file"""
    db = await get_database()

    # Get all records for suspect
    cursor = db.cdr_records.find({"suspect_name": suspect_name})
    records = await cursor.to_list(length=None)

    if not records:
        raise ValueError(f"No records found for suspect: {suspect_name}")

    # Create exports directory (use absolute path)
    exports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")
    os.makedirs(exports_dir, exist_ok=True)

    # Save to CSV file
    filename = os.path.join(exports_dir, f"{suspect_name}_cdr_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

    # Get all field names from records
    fieldnames = set()
    for record in records:
        fieldnames.update(record.keys())

    # Remove MongoDB _id and convert to list
    fieldnames = sorted([f for f in fieldnames if f != '_id'])

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for record in records:
            # Convert ObjectId and datetime to strings
            row = {}
            for field in fieldnames:
                value = record.get(field)
                if value is None:
                    row[field] = ''
                elif isinstance(value, datetime):
                    row[field] = value.isoformat()
                elif hasattr(value, '__str__'):
                    row[field] = str(value)
                else:
                    row[field] = value
            writer.writerow(row)

    return filename
