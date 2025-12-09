#!/usr/bin/env python3
"""
Generate sample CDR files in various vendor formats (Excel)
Creates sample files for testing format auto-detection
"""

import pandas as pd
from datetime import datetime, timedelta
import random
import os

# Sample data
SAMPLE_NUMBERS = ["+15551234567", "+15559876543", "+14151234567", "+12121234567"]
SAMPLE_TOWERS = ["TOWER_001", "TOWER_002", "TOWER_003", "TOWER_004"]
SAMPLE_IMEIS = ["123456789012345", "234567890123456", "345678901234567"]

def generate_ericsson_format(output_file: str, record_count: int = 50):
    """Generate Ericsson format CDR file"""
    records = []
    base_time = datetime.now() - timedelta(days=7)

    for i in range(record_count):
        start_time = base_time + timedelta(
            hours=random.randint(0, 168),
            minutes=random.randint(0, 59)
        )
        duration = random.randint(10, 3600)
        end_time = start_time + timedelta(seconds=duration)

        records.append({
            'a_number': random.choice(SAMPLE_NUMBERS),
            'b_number': random.choice(SAMPLE_NUMBERS),
            'event_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'duration': duration,
            'cell_id': random.choice(SAMPLE_TOWERS),
            'imei': random.choice(SAMPLE_IMEIS),
            'imsi': f"310150{random.randint(100000000, 999999999)}",
            'call_type': random.choice(['voice', 'sms', 'data']),
            'direction': random.choice(['originating', 'terminating'])
        })

    df = pd.DataFrame(records)
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"✅ Generated Ericsson format: {output_file}")

def generate_nokia_format(output_file: str, record_count: int = 50):
    """Generate Nokia format CDR file"""
    records = []
    base_time = datetime.now() - timedelta(days=7)

    for i in range(record_count):
        start_time = base_time + timedelta(
            hours=random.randint(0, 168),
            minutes=random.randint(0, 59)
        )
        duration = random.randint(10, 3600)

        records.append({
            'a_party': random.choice(SAMPLE_NUMBERS),
            'b_party': random.choice(SAMPLE_NUMBERS),
            'event_time': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'call_length': duration,
            'cell_identity': random.choice(SAMPLE_TOWERS),
            'equipment_id': random.choice(SAMPLE_IMEIS),
            'imsi': f"310150{random.randint(100000000, 999999999)}",
            'service_type': random.choice(['voice', 'sms', 'data']),
            'call_direction': random.choice(['outgoing', 'incoming'])
        })

    df = pd.DataFrame(records)
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"✅ Generated Nokia format: {output_file}")

def generate_huawei_format(output_file: str, record_count: int = 50):
    """Generate Huawei format CDR file"""
    records = []
    base_time = datetime.now() - timedelta(days=7)

    for i in range(record_count):
        start_time = base_time + timedelta(
            hours=random.randint(0, 168),
            minutes=random.randint(0, 59)
        )
        duration = random.randint(10, 3600)
        end_time = start_time + timedelta(seconds=duration)

        records.append({
            'calling_number': random.choice(SAMPLE_NUMBERS),
            'called_number': random.choice(SAMPLE_NUMBERS),
            'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
            'call_duration': duration,
            'cell_id': random.choice(SAMPLE_TOWERS),
            'lac': f"LAC{random.randint(1000, 9999)}",
            'imei': random.choice(SAMPLE_IMEIS),
            'imsi': f"310150{random.randint(100000000, 999999999)}",
            'service_type': random.choice(['voice', 'sms', 'data']),
            'call_direction': random.choice(['outgoing', 'incoming'])
        })

    df = pd.DataFrame(records)
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"✅ Generated Huawei format: {output_file}")

def generate_standard_format(output_file: str, record_count: int = 50):
    """Generate standard format CDR file"""
    records = []
    base_time = datetime.now() - timedelta(days=7)

    for i in range(record_count):
        start_time = base_time + timedelta(
            hours=random.randint(0, 168),
            minutes=random.randint(0, 59)
        )
        duration = random.randint(10, 3600)
        end_time = start_time + timedelta(seconds=duration)

        records.append({
            'calling_number': random.choice(SAMPLE_NUMBERS),
            'called_number': random.choice(SAMPLE_NUMBERS),
            'call_start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'call_end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
            'duration_seconds': duration,
            'call_type': random.choice(['voice', 'sms', 'data']),
            'direction': random.choice(['outgoing', 'incoming']),
            'cell_tower_id': random.choice(SAMPLE_TOWERS),
            'location_lat': round(random.uniform(37.7, 37.8), 6),
            'location_lon': round(random.uniform(-122.5, -122.4), 6),
            'imei': random.choice(SAMPLE_IMEIS),
            'imsi': f"310150{random.randint(100000000, 999999999)}",
            'cost': round(random.uniform(0.01, 5.0), 2),
            'call_status': random.choice(['completed', 'failed', 'missed'])
        })

    df = pd.DataFrame(records)
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"✅ Generated Standard format: {output_file}")

if __name__ == "__main__":
    # Create samples directory
    os.makedirs("samples", exist_ok=True)

    print("📝 Generating sample CDR files in various vendor formats...\n")

    generate_ericsson_format("samples/sample_ericsson.xlsx", 50)
    generate_nokia_format("samples/sample_nokia.xlsx", 50)
    generate_huawei_format("samples/sample_huawei.xlsx", 50)
    generate_standard_format("samples/sample_standard.xlsx", 50)

    print("\n✅ All sample files generated in 'samples' directory")
    print("You can now test the format auto-detection by uploading these files!")
