"""
Comprehensive CDR Analytics Module
Generates all 10 analytical views as specified in the requirements
"""

from database import get_database
from typing import Dict, List, Optional
from datetime import datetime, date
from collections import defaultdict
import re

async def _build_match_query(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """Helper to build match query - prefer session_id, fallback to suspect_name"""
    match_query = {}
    latest = None
    if session_id:
        match_query["session_id"] = session_id
    elif suspect_name:
        match_query["suspect_name"] = suspect_name
    else:
        # Get most recent session
        db = await get_database()
        latest = await db.cdr_records.find_one(sort=[("call_start_time", -1)])
        if latest and latest.get("session_id"):
            match_query["session_id"] = latest["session_id"]
    return match_query


async def generate_summary(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """
    1. SUMMARY - Compute total calls, incoming vs outgoing, unique B-numbers,
    unique IMEIs, unique locations, first/last activity dates
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return {
            "total_calls": 0,
            "incoming_count": 0,
            "outgoing_count": 0,
            "unique_b_numbers": 0,
            "unique_imeis": 0,
            "unique_locations": 0,
            "first_activity_date": None,
            "last_activity_date": None
        }

    pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": None,
            "total_calls": {"$sum": 1},
            "incoming_count": {"$sum": {"$cond": [{"$eq": ["$direction", "incoming"]}, 1, 0]}},
            "outgoing_count": {"$sum": {"$cond": [{"$eq": ["$direction", "outgoing"]}, 1, 0]}},
            "unique_b_numbers": {"$addToSet": "$msisdn_b"},
            "unique_imeis": {"$addToSet": "$imei"},
            "unique_locations": {"$addToSet": "$cell_id"},
            "first_activity": {"$min": "$call_start_time"},
            "last_activity": {"$max": "$call_start_time"}
        }}
    ]

    result = await db.cdr_records.aggregate(pipeline).to_list(length=1)

    if result and result[0]:
        data = result[0]
        # Safely convert datetime objects to ISO format strings
        first_activity = data.get("first_activity")
        if first_activity:
            if isinstance(first_activity, datetime):
                first_activity_str = first_activity.isoformat()
            else:
                first_activity_str = str(first_activity)
        else:
            first_activity_str = None

        last_activity = data.get("last_activity")
        if last_activity:
            if isinstance(last_activity, datetime):
                last_activity_str = last_activity.isoformat()
            else:
                last_activity_str = str(last_activity)
        else:
            last_activity_str = None

        return {
            "total_calls": data.get("total_calls", 0),
            "incoming_count": data.get("incoming_count", 0),
            "outgoing_count": data.get("outgoing_count", 0),
            "unique_b_numbers": len([x for x in data.get("unique_b_numbers", []) if x]),
            "unique_imeis": len([x for x in data.get("unique_imeis", []) if x]),
            "unique_locations": len([x for x in data.get("unique_locations", []) if x]),
            "first_activity_date": first_activity_str,
            "last_activity_date": last_activity_str
        }

    return {
        "total_calls": 0,
        "incoming_count": 0,
        "outgoing_count": 0,
        "unique_b_numbers": 0,
        "unique_imeis": 0,
        "unique_locations": 0,
        "first_activity_date": None,
        "last_activity_date": None
    }


async def generate_corrected(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> List[Dict]:
    """
    2. CORRECTED - Cleaned and validated dataset with only valid MSISDN rows
    Standardized operator/circle names
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return []

    # Get all records with valid MSISDN
    cursor = db.cdr_records.find({
        **match_query,
        "$or": [
            {"msisdn_a": {"$exists": True, "$ne": None, "$ne": ""}},
            {"calling_number": {"$exists": True, "$ne": None, "$ne": ""}}
        ],
        "$or": [
            {"msisdn_b": {"$exists": True, "$ne": None, "$ne": ""}},
            {"called_number": {"$exists": True, "$ne": None, "$ne": ""}}
        ]
    })

    records = await cursor.to_list(length=None)

    corrected = []
    for record in records:
        # Normalize MSISDN fields
        msisdn_a = record.get("msisdn_a") or record.get("calling_number") or ""
        msisdn_b = record.get("msisdn_b") or record.get("called_number") or ""

        # Clean phone numbers (remove non-digits except +)
        msisdn_a = re.sub(r'[^\d+]', '', str(msisdn_a)) if msisdn_a else ""
        msisdn_b = re.sub(r'[^\d+]', '', str(msisdn_b)) if msisdn_b else ""

        if not msisdn_a or not msisdn_b:
            continue

        # Standardize operator/circle names
        operator = record.get("operator", "").strip().title() if record.get("operator") else ""
        circle = record.get("circle", "").strip().title() if record.get("circle") else ""

        corrected_record = {
            "record_id": record.get("record_id") or record.get("call_id") or str(record.get("_id", "")),
            "msisdn_a": msisdn_a,
            "msisdn_b": msisdn_b,
            "call_type": record.get("call_type", "voice"),
            "call_date": record.get("call_date") or (record.get("call_start_time").strftime("%Y-%m-%d") if record.get("call_start_time") else ""),
            "call_start_time": record.get("call_start_time").isoformat() if record.get("call_start_time") else "",
            "call_duration_sec": record.get("call_duration_sec") or record.get("duration_seconds") or 0,
            "imei": record.get("imei") or "",
            "imsi": record.get("imsi") or "",
            "cell_id": record.get("cell_id") or record.get("cell_tower_id") or "",
            "lac": record.get("lac") or "",
            "operator": operator,
            "circle": circle,
            "location_description": record.get("location_description") or "",
            "raw_row_reference": record.get("raw_row_reference") or ""
        }

        corrected.append(corrected_record)

    return corrected


async def generate_max_call(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """
    3. MAX CALL - Identify B-number contacted most frequently
    Include total call count
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return {"b_number": None, "total_call_count": 0}

    pipeline = [
        {"$match": {
            **match_query,
            "$or": [
                {"msisdn_b": {"$exists": True, "$ne": None, "$ne": ""}},
                {"called_number": {"$exists": True, "$ne": None, "$ne": ""}}
            ]
        }},
        {"$group": {
            "_id": {
                "$ifNull": ["$msisdn_b", "$called_number"]
            },
            "call_count": {"$sum": 1}
        }},
        {"$sort": {"call_count": -1}},
        {"$limit": 1}
    ]

    result = await db.cdr_records.aggregate(pipeline).to_list(length=1)

    if result and result[0]:
        return {
            "b_number": result[0]["_id"],
            "total_call_count": result[0]["call_count"]
        }

    return {
        "b_number": None,
        "total_call_count": 0
    }


async def generate_max_circle_call(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """
    4. MAX CIRCLE CALL - Identify telecom circle/state with highest activity
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return {"circle": None, "activity_count": 0}

    pipeline = [
        {"$match": {
            **match_query,
            "$or": [
                {"circle": {"$exists": True, "$ne": None, "$ne": ""}},
                {"operator": {"$exists": True, "$ne": None, "$ne": ""}}
            ]
        }},
        {"$group": {
            "_id": {
                "$ifNull": ["$circle", "$operator"]
            },
            "activity_count": {"$sum": 1}
        }},
        {"$sort": {"activity_count": -1}},
        {"$limit": 1}
    ]

    result = await db.cdr_records.aggregate(pipeline).to_list(length=1)

    if result and result[0]:
        return {
            "circle": result[0]["_id"],
            "activity_count": result[0]["activity_count"]
        }

    return {
        "circle": None,
        "activity_count": 0
    }


async def generate_daily_first_last(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> List[Dict]:
    """
    5. DAILY FIRST & LAST CALL - For each date:
    First call time + B-number
    Last call time + B-number
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return []

    pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": {
                "$dateToString": {
                    "format": "%Y-%m-%d",
                    "date": "$call_start_time"
                }
            },
            "first_call": {"$min": "$call_start_time"},
            "last_call": {"$max": "$call_start_time"},
            "calls": {"$push": {
                "time": "$call_start_time",
                "b_number": {"$ifNull": ["$msisdn_b", "$called_number"]}
            }}
        }},
        {"$sort": {"_id": 1}}
    ]

    result = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    daily_data = []
    for item in result:
        date_str = item["_id"]
        calls = item.get("calls", [])

        if not calls:
            continue

        # Find first call
        first_call = min(calls, key=lambda x: x["time"] if x["time"] else datetime.max)
        # Find last call
        last_call = max(calls, key=lambda x: x["time"] if x["time"] else datetime.min)

        first_time = first_call["time"]
        last_time = last_call["time"]

        daily_data.append({
            "date": date_str,
            "first_call_time": first_time.isoformat() if isinstance(first_time, datetime) else (str(first_time) if first_time else ""),
            "first_call_b_number": first_call.get("b_number") or "",
            "last_call_time": last_time.isoformat() if isinstance(last_time, datetime) else (str(last_time) if last_time else ""),
            "last_call_b_number": last_call.get("b_number") or ""
        })

    return daily_data


async def generate_max_duration(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """
    6. MAX DURATION - Single longest call
    Include B-number, Duration, Date, Location
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return {
            "b_number": None,
            "duration_seconds": 0,
            "date": None,
            "call_start_time": None,
            "cell_id": None,
            "location_description": None
        }

    pipeline = [
        {"$match": {
            **match_query,
            "$or": [
                {"call_duration_sec": {"$exists": True, "$ne": None, "$gt": 0}},
                {"duration_seconds": {"$exists": True, "$ne": None, "$gt": 0}}
            ]
        }},
        {"$project": {
            "b_number": {"$ifNull": ["$msisdn_b", "$called_number"]},
            "duration": {
                "$ifNull": ["$call_duration_sec", "$duration_seconds"]
            },
            "date": {
                "$dateToString": {
                    "format": "%Y-%m-%d",
                    "date": "$call_start_time"
                }
            },
            "call_start_time": 1,
            "cell_id": {"$ifNull": ["$cell_id", "$cell_tower_id"]},
            "location_description": 1
        }},
        {"$sort": {"duration": -1}},
        {"$limit": 1}
    ]

    result = await db.cdr_records.aggregate(pipeline).to_list(length=1)

    if result and result[0]:
        data = result[0]
        return {
            "b_number": data.get("b_number") or "",
            "duration_seconds": data.get("duration", 0),
            "date": data.get("date", ""),
            "call_start_time": data.get("call_start_time").isoformat() if isinstance(data.get("call_start_time"), datetime) else "",
            "cell_id": data.get("cell_id") or "",
            "location_description": data.get("location_description") or ""
        }

    return {
        "b_number": None,
        "duration_seconds": 0,
        "date": None,
        "call_start_time": None,
        "cell_id": None,
        "location_description": None
    }


async def generate_max_imei(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """
    7. MAX IMEI - IMEI with highest call volume
    Rank all IMEIs
    Flag multi-device usage
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return {
            "max_imei": None,
            "max_imei_call_count": 0,
            "total_imeis": 0,
            "multi_device_usage": False,
            "imei_ranking": []
        }

    pipeline = [
        {"$match": {
            **match_query,
            "imei": {"$exists": True, "$ne": None, "$ne": ""}
        }},
        {"$group": {
            "_id": "$imei",
            "call_count": {"$sum": 1}
        }},
        {"$sort": {"call_count": -1}}
    ]

    result = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    if not result:
        return {
            "max_imei": None,
            "max_imei_call_count": 0,
            "total_imeis": 0,
            "multi_device_usage": False,
            "imei_ranking": []
        }

    imei_ranking = [
        {
            "imei": item["_id"],
            "call_count": item["call_count"]
        }
        for item in result
    ]

    max_imei_data = result[0] if result else None

    return {
        "max_imei": max_imei_data["_id"] if max_imei_data else None,
        "max_imei_call_count": max_imei_data["call_count"] if max_imei_data else 0,
        "total_imeis": len(result),
        "multi_device_usage": len(result) > 1,
        "imei_ranking": imei_ranking
    }


async def generate_daily_imei_tracking(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> List[Dict]:
    """
    8. DAILY IMEI TRACKING - For each date:
    IMEI(s) used
    Call count per IMEI
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return []

    pipeline = [
        {"$match": {
            **match_query,
            "imei": {"$exists": True, "$ne": None, "$ne": ""}
        }},
        {"$group": {
            "_id": {
                "date": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$call_start_time"
                    }
                },
                "imei": "$imei"
            },
            "call_count": {"$sum": 1}
        }},
        {"$group": {
            "_id": "$_id.date",
            "imeis": {"$push": {
                "imei": "$_id.imei",
                "call_count": "$call_count"
            }}
        }},
        {"$sort": {"_id": 1}}
    ]

    result = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    daily_imei_data = []
    for item in result:
        daily_imei_data.append({
            "date": item["_id"],
            "imeis": item.get("imeis", [])
        })

    return daily_imei_data


async def generate_max_location(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """
    9. MAX LOCATION - Most frequently used Cell ID / location
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return {"cell_id": None, "usage_count": 0}

    pipeline = [
        {"$match": {
            **match_query,
            "$or": [
                {"cell_id": {"$exists": True, "$ne": None, "$ne": ""}},
                {"cell_tower_id": {"$exists": True, "$ne": None, "$ne": ""}}
            ]
        }},
        {"$group": {
            "_id": {
                "$ifNull": ["$cell_id", "$cell_tower_id"]
            },
            "usage_count": {"$sum": 1}
        }},
        {"$sort": {"usage_count": -1}},
        {"$limit": 1}
    ]

    result = await db.cdr_records.aggregate(pipeline).to_list(length=1)

    if result and result[0]:
        return {
            "cell_id": result[0]["_id"],
            "usage_count": result[0]["usage_count"]
        }

    return {
        "cell_id": None,
        "usage_count": 0
    }


async def generate_daily_first_last_location(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> List[Dict]:
    """
    10. DAILY FIRST & LAST LOCATION - For each date:
    First location
    Last location
    Associated time
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return []

    pipeline = [
        {"$match": {
            **match_query,
            "$or": [
                {"cell_id": {"$exists": True, "$ne": None, "$ne": ""}},
                {"cell_tower_id": {"$exists": True, "$ne": None, "$ne": ""}}
            ]
        }},
        {"$group": {
            "_id": {
                "$dateToString": {
                    "format": "%Y-%m-%d",
                    "date": "$call_start_time"
                }
            },
            "locations": {"$push": {
                "time": "$call_start_time",
                "cell_id": {"$ifNull": ["$cell_id", "$cell_tower_id"]},
                "location_description": "$location_description"
            }}
        }},
        {"$sort": {"_id": 1}}
    ]

    result = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    daily_location_data = []
    for item in result:
        date_str = item["_id"]
        locations = item.get("locations", [])

        if not locations:
            continue

        # Find first location
        first_location = min(locations, key=lambda x: x["time"] if x["time"] else datetime.max)
        # Find last location
        last_location = max(locations, key=lambda x: x["time"] if x["time"] else datetime.min)

        first_time = first_location["time"]
        last_time = last_location["time"]

        daily_location_data.append({
            "date": date_str,
            "first_location": {
                "cell_id": first_location.get("cell_id") or "",
                "time": first_time.isoformat() if isinstance(first_time, datetime) else (str(first_time) if first_time else ""),
                "location_description": first_location.get("location_description") or ""
            },
            "last_location": {
                "cell_id": last_location.get("cell_id") or "",
                "time": last_time.isoformat() if isinstance(last_time, datetime) else (str(last_time) if last_time else ""),
                "location_description": last_location.get("location_description") or ""
            }
        })

    return daily_location_data


async def generate_all_analytics(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """
    Generate all 10 analytical views at once
    Returns structured data for JSON and Excel export
    """
    return {
        "Summary": await generate_summary(session_id, suspect_name),
        "Corrected": await generate_corrected(session_id, suspect_name),
        "MaxCall": await generate_max_call(session_id, suspect_name),
        "MaxCircleCall": await generate_max_circle_call(session_id, suspect_name),
        "DailyFirstLast": await generate_daily_first_last(session_id, suspect_name),
        "MaxDuration": await generate_max_duration(session_id, suspect_name),
        "MaxIMEI": await generate_max_imei(session_id, suspect_name),
        "DailyIMEIATracking": await generate_daily_imei_tracking(session_id, suspect_name),
        "MaxLocation": await generate_max_location(session_id, suspect_name),
        "DailyFirstLastLocation": await generate_daily_first_last_location(session_id, suspect_name)
    }
