from database import get_database
from typing import List, Dict, Optional
from datetime import datetime
import phonenumbers
import pycountry
from collections import defaultdict
import httpx
import os

async def analyze_imei(suspect_name: str) -> Dict:
    """Analyze IMEI usage for a suspect"""
    db = await get_database()

    pipeline = [
        {"$match": {"suspect_name": suspect_name, "imei": {"$exists": True, "$ne": None}}},
        {"$group": {
            "_id": "$imei",
            "usage_count": {"$sum": 1},
            "first_seen": {"$min": "$call_start_time"},
            "last_seen": {"$max": "$call_start_time"},
            "call_types": {"$push": "$call_type"},
            "locations": {"$push": {"lat": "$location_lat", "lon": "$location_lon"}}
        }},
        {"$sort": {"usage_count": -1}}
    ]

    results = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    imei_list = []
    for result in results:
        imei = result["_id"]
        device_info = await decode_imei(imei)

        imei_list.append({
            "imei": imei,
            "device_info": device_info,
            "usage_count": result["usage_count"],
            "first_seen": result["first_seen"],
            "last_seen": result["last_seen"],
            "call_types": list(set(result["call_types"])),
            "timeline": {
                "start": result["first_seen"],
                "end": result["last_seen"],
                "duration_days": (result["last_seen"] - result["first_seen"]).days if result["last_seen"] and result["first_seen"] else 0
            }
        })

    return {
        "suspect_name": suspect_name,
        "unique_imeis": len(imei_list),
        "imeis": imei_list
    }

async def decode_imei(imei: str) -> Dict:
    """Decode IMEI to device information using IMEI API"""
    if not imei or len(imei) < 15:
        return {"error": "Invalid IMEI"}

    try:
        # IMEI structure: TAC (8 digits) + Serial (6 digits) + Check digit (1 digit)
        tac = imei[:8]  # Type Allocation Code

        # Try to decode from IMEI.info API (free tier available)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Using imei.info API (alternative: imei24.com, tacdb.info)
                response = await client.get(
                    f"https://imei.info/api/imei/{imei}",
                    headers={"Accept": "application/json"}
                )
                if response.status_code == 200:
                    api_data = response.json()
                    return {
                        "tac": tac,
                        "serial": imei[8:14],
                        "check_digit": imei[14] if len(imei) > 14 else None,
                        "manufacturer": api_data.get("manufacturer", "Unknown"),
                        "model": api_data.get("model", "Unknown"),
                        "brand": api_data.get("brand", "Unknown"),
                        "source": "imei.info"
                    }
        except:
            pass

        # Fallback: Try TAC database lookup
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"https://www.tacdb.info/api/v1/tac/{tac}",
                    headers={"Accept": "application/json"}
                )
                if response.status_code == 200:
                    tac_data = response.json()
                    return {
                        "tac": tac,
                        "serial": imei[8:14],
                        "check_digit": imei[14] if len(imei) > 14 else None,
                        "manufacturer": tac_data.get("manufacturer", "Unknown"),
                        "model": tac_data.get("model", "Unknown"),
                        "brand": tac_data.get("brand", "Unknown"),
                        "source": "tacdb.info"
                    }
        except:
            pass

        # Final fallback: Basic decoding
        return {
            "tac": tac,
            "serial": imei[8:14],
            "check_digit": imei[14] if len(imei) > 14 else None,
            "manufacturer": "Unknown",
            "model": "Unknown",
            "brand": "Unknown",
            "source": "basic"
        }
    except Exception as e:
        return {"error": f"Could not decode IMEI: {str(e)}"}

async def decode_cell_id(cell_tower_id: str, mcc: Optional[int] = None, mnc: Optional[int] = None, lac: Optional[int] = None) -> Optional[Dict]:
    """Decode Cell ID to latitude/longitude from database or API"""
    if not cell_tower_id:
        return None

    # If we have MCC, MNC, LAC, use API lookup
    if mcc and mnc and lac:
        try:
            cell_id_str = str(cell_tower_id)
            cell_id_int = None
            if cell_id_str.isdigit():
                cell_id_int = int(cell_id_str)
            else:
                # Try to extract numbers from string
                import re
                numbers = re.findall(r'\d+', cell_id_str)
                if numbers:
                    cell_id_int = int(numbers[0])

            if cell_id_int:
                # Import here to avoid circular imports
                from kml_export import lookup_cell_tower_coordinates
                api_key = os.getenv("OPENCELLID_API_KEY")
                return await lookup_cell_tower_coordinates(mcc, mnc, lac, cell_id_int, api_key)
        except Exception as e:
            print(f"Error looking up cell coordinates: {e}")

    # For now, return None - will use existing lat/lon from records
    return None

async def analyze_cell_towers(suspect_name: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict:
    """Analyze cell tower usage for a suspect with optional date filters"""
    db = await get_database()

    match_query = {
        "suspect_name": suspect_name,
        "cell_tower_id": {"$exists": True, "$ne": None}
    }

    # Add date filters if provided
    if start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        match_query["call_start_time"] = date_filter

    pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": "$cell_tower_id",
            "usage_count": {"$sum": 1},
            "first_seen": {"$min": "$call_start_time"},
            "last_seen": {"$max": "$call_start_time"},
            "avg_lat": {"$avg": "$location_lat"},
            "avg_lon": {"$avg": "$location_lon"},
            "locations": {"$push": {
                "lat": "$location_lat",
                "lon": "$location_lon",
                "timestamp": "$call_start_time"
            }}
        }},
        {"$sort": {"usage_count": -1}}
    ]

    results = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    towers = []
    for result in results:
        # If no lat/lon, try to decode from cell ID
        lat = result.get("avg_lat")
        lon = result.get("avg_lon")

        # Try to get MCC, MNC, LAC from first record with this tower
        tower_record = await db.cdr_records.find_one({
            "suspect_name": suspect_name,
            "cell_tower_id": result["_id"]
        })

        if not lat or not lon:
            mcc = tower_record.get("mcc") if tower_record else None
            mnc = tower_record.get("mnc") if tower_record else None
            lac = tower_record.get("lac") if tower_record else None
            decoded = await decode_cell_id(result["_id"], mcc, mnc, lac)
            if decoded:
                lat = decoded.get("lat")
                lon = decoded.get("lon")

        towers.append({
            "tower_id": result["_id"],
            "usage_count": result["usage_count"],
            "location": {
                "lat": lat,
                "lon": lon
            },
            "first_seen": result["first_seen"],
            "last_seen": result["last_seen"],
            "locations": [loc for loc in result["locations"] if loc.get("lat") and loc.get("lon")]
        })

    return {
        "suspect_name": suspect_name,
        "unique_towers": len(towers),
        "towers": towers,
        "date_filter": {
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None
        }
    }

async def analyze_contacts(suspect_name: str) -> Dict:
    """Analyze contact patterns for a suspect"""
    db = await get_database()

    if not suspect_name:
        return {
            "suspect_name": suspect_name,
            "most_called": [],
            "most_duration_called": [],
            "longest_calls": []
        }

    # Most called numbers (by count)
    pipeline_called = [
        {"$match": {"suspect_name": suspect_name, "direction": "outgoing"}},
        {"$group": {
            "_id": "$called_number",
            "call_count": {"$sum": 1},
            "total_duration": {"$sum": "$duration_seconds"},
            "first_contact": {"$min": "$call_start_time"},
            "last_contact": {"$max": "$call_start_time"},
            "calls": {"$push": {
                "timestamp": "$call_start_time",
                "duration": "$duration_seconds",
                "type": "$call_type"
            }}
        }},
        {"$sort": {"call_count": -1}},
        {"$limit": 50}
    ]

    try:
        most_called = await db.cdr_records.aggregate(pipeline_called).to_list(length=None)
    except Exception as e:
        print(f"Error in most_called aggregation: {e}")
        most_called = []

    # Most duration called numbers (by total duration)
    pipeline_duration_called = [
        {"$match": {"suspect_name": suspect_name, "duration_seconds": {"$exists": True, "$ne": None}}},
        {"$group": {
            "_id": "$called_number",
            "call_count": {"$sum": 1},
            "total_duration": {"$sum": "$duration_seconds"},
            "first_contact": {"$min": "$call_start_time"},
            "last_contact": {"$max": "$call_start_time"},
            "calls": {"$push": {
                "timestamp": "$call_start_time",
                "duration": "$duration_seconds",
                "type": "$call_type"
            }}
        }},
        {"$sort": {"total_duration": -1}},
        {"$limit": 50}
    ]

    try:
        most_duration_called = await db.cdr_records.aggregate(pipeline_duration_called).to_list(length=None)
    except Exception as e:
        print(f"Error in most_duration_called aggregation: {e}")
        most_duration_called = []

    # Longest duration calls
    pipeline_duration = [
        {"$match": {"suspect_name": suspect_name, "duration_seconds": {"$exists": True, "$ne": None}}},
        {"$sort": {"duration_seconds": -1}},
        {"$limit": 20},
        {"$project": {
            "called_number": 1,
            "calling_number": 1,
            "call_start_time": 1,
            "duration_seconds": 1,
            "call_type": 1,
            "direction": 1
        }}
    ]

    try:
        longest_calls = await db.cdr_records.aggregate(pipeline_duration).to_list(length=None)
    except Exception as e:
        print(f"Error in longest_calls aggregation: {e}")
        longest_calls = []

    # Convert ObjectId and datetime to serializable format
    def serialize_record(record):
        if isinstance(record, dict):
            result = {}
            for k, v in record.items():
                if k == "_id":
                    continue
                if isinstance(v, datetime):
                    result[k] = v.isoformat()
                elif hasattr(v, '__dict__'):
                    result[k] = str(v)
                else:
                    result[k] = v
            return result
        return record

    longest_calls_serialized = [serialize_record(call) for call in longest_calls]

    most_called_serialized = []
    for item in most_called:
        calls_serialized = []
        for call in item.get("calls", []):
            call_dict = {}
            for k, v in call.items():
                if isinstance(v, datetime):
                    call_dict[k] = v.isoformat()
                else:
                    call_dict[k] = v
            calls_serialized.append(call_dict)

        first_contact = item.get("first_contact")
        last_contact = item.get("last_contact")

        most_called_serialized.append({
            "number": item["_id"],
            "call_count": item["call_count"],
            "total_duration_seconds": item.get("total_duration", 0) or 0,
            "first_contact": first_contact.isoformat() if first_contact and isinstance(first_contact, datetime) else (first_contact if first_contact else None),
            "last_contact": last_contact.isoformat() if last_contact and isinstance(last_contact, datetime) else (last_contact if last_contact else None),
            "calls": calls_serialized
        })

    most_duration_serialized = []
    for item in most_duration_called:
        calls_serialized = []
        for call in item.get("calls", []):
            call_dict = {}
            for k, v in call.items():
                if isinstance(v, datetime):
                    call_dict[k] = v.isoformat()
                else:
                    call_dict[k] = v
            calls_serialized.append(call_dict)

        first_contact = item.get("first_contact")
        last_contact = item.get("last_contact")

        most_duration_serialized.append({
            "number": item["_id"],
            "call_count": item["call_count"],
            "total_duration_seconds": item.get("total_duration", 0) or 0,
            "first_contact": first_contact.isoformat() if first_contact and isinstance(first_contact, datetime) else (first_contact if first_contact else None),
            "last_contact": last_contact.isoformat() if last_contact and isinstance(last_contact, datetime) else (last_contact if last_contact else None),
            "calls": calls_serialized
        })

    return {
        "suspect_name": suspect_name,
        "most_called": most_called_serialized,
        "most_duration_called": most_duration_serialized,
        "longest_calls": longest_calls_serialized
    }

async def analyze_sms_services(suspect_name: str) -> Dict:
    """Detect services from SMS patterns"""
    db = await get_database()

    # SMS service patterns
    service_patterns = {
        "WhatsApp": ["whatsapp", "wa.me", "whatsapp.com"],
        "Uber": ["uber", "uber.com"],
        "Swiggy": ["swiggy", "swiggy.com"],
        "Zomato": ["zomato", "zomato.com"],
        "Paytm": ["paytm", "paytm.com"],
        "Bank": ["bank", "otp", "pin", "verification", "transaction"],
        "PayPal": ["paypal"],
        "Amazon": ["amazon", "aws"],
        "Google": ["google", "gmail", "goog"],
        "Facebook": ["facebook", "fb.com", "messenger"],
        "Telegram": ["telegram"],
        "Instagram": ["instagram", "ig"],
        "Twitter": ["twitter", "x.com"]
    }

    pipeline = [
        {"$match": {
            "suspect_name": suspect_name,
            "call_type": "sms",
            "$or": [
                {"sms_content": {"$exists": True, "$ne": None}},
                {"called_number": {"$exists": True, "$ne": None}}
            ]
        }},
        {"$project": {
            "sms_content": 1,
            "called_number": 1,
            "call_start_time": 1
        }}
    ]

    sms_records = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    service_detections = defaultdict(list)

    for record in sms_records:
        content = str(record.get("sms_content", "")).lower()
        number = str(record.get("called_number", "")).lower()
        combined = f"{content} {number}"

        for service, patterns in service_patterns.items():
            if any(pattern in combined for pattern in patterns):
                service_detections[service].append({
                    "timestamp": record.get("call_start_time"),
                    "called_number": record.get("called_number"),
                    "sms_content": record.get("sms_content", "")[:100]  # First 100 chars
                })
                break

    return {
        "suspect_name": suspect_name,
        "services_detected": {
            service: {
                "count": len(detections),
                "detections": detections
            }
            for service, detections in service_detections.items()
        }
    }

async def analyze_international_calls(suspect_name: str) -> Dict:
    """Analyze international calls by country"""
    db = await get_database()

    pipeline = [
        {"$match": {"suspect_name": suspect_name}},
        {"$project": {
            "called_number": 1,
            "calling_number": 1,
            "call_start_time": 1,
            "duration_seconds": 1,
            "call_type": 1,
            "direction": 1
        }}
    ]

    records = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    country_stats = defaultdict(lambda: {"count": 0, "total_duration": 0, "calls": []})

    for record in records:
        number = record.get("called_number") if record.get("direction") == "outgoing" else record.get("calling_number")

        if not number:
            continue

        try:
            # Parse phone number
            parsed = phonenumbers.parse(number, None)
            country_code = phonenumbers.region_code_for_number(parsed)

            if country_code:
                country_name = pycountry.countries.get(alpha_2=country_code)
                country = country_name.name if country_name else country_code

                country_stats[country]["count"] += 1
                country_stats[country]["total_duration"] += record.get("duration_seconds", 0)
                country_stats[country]["calls"].append({
                    "number": number,
                    "timestamp": record.get("call_start_time"),
                    "duration": record.get("duration_seconds"),
                    "type": record.get("call_type")
                })
        except:
            continue

    return {
        "suspect_name": suspect_name,
        "countries": {
            country: {
                "call_count": stats["count"],
                "total_duration_seconds": stats["total_duration"],
                "calls": stats["calls"][:10]  # Limit to 10 calls per country
            }
            for country, stats in sorted(country_stats.items(), key=lambda x: x[1]["count"], reverse=True)
        }
    }

async def find_common_numbers(suspect_names: List[str]) -> Dict:
    """Find common numbers between multiple suspects (network graph) with detailed metrics"""
    db = await get_database()

    # Get detailed information for each suspect-number pair
    pipeline = [
        {"$match": {"suspect_name": {"$in": suspect_names}}},
        {"$group": {
            "_id": {
                "suspect": "$suspect_name",
                "number": "$called_number"
            },
            "call_count": {"$sum": 1},
            "total_duration": {"$sum": "$duration_seconds"},
            "first_contact": {"$min": "$call_start_time"},
            "last_contact": {"$max": "$call_start_time"},
            "calls": {"$push": {
                "timestamp": "$call_start_time",
                "duration": "$duration_seconds",
                "type": "$call_type"
            }}
        }},
        {"$group": {
            "_id": "$_id.number",
            "suspects": {"$push": {
                "name": "$_id.suspect",
                "call_count": "$call_count",
                "total_duration": "$total_duration",
                "first_contact": "$first_contact",
                "last_contact": "$last_contact"
            }},
            "total_calls": {"$sum": "$call_count"},
            "total_duration_all": {"$sum": "$total_duration"},
            "global_first_contact": {"$min": "$first_contact"},
            "global_last_contact": {"$max": "$last_contact"}
        }},
        {"$match": {"$expr": {"$gt": [{"$size": "$suspects"}, 1]}}},
        {"$sort": {"total_calls": -1}}
    ]

    results = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    # Build network graph structure
    nodes = []
    edges = []

    # Add suspect nodes
    suspect_nodes = {name: len(nodes) for name in suspect_names}
    suspect_colors = ["#ec4899", "#8b5cf6", "#10b981", "#f59e0b", "#3b82f6"]
    for idx, suspect in enumerate(suspect_names):
        nodes.append({
            "id": suspect,
            "label": suspect,
            "type": "suspect",
            "color": suspect_colors[idx % len(suspect_colors)]
        })

    # Add common number nodes and edges with detailed info
    for result in results:
        number = result["_id"]
        node_id = f"number_{len(nodes)}"

        nodes.append({
            "id": node_id,
            "label": number,
            "type": "number",
            "color": "#6366f1",
            "title": f"Number: {number}\nTotal Calls: {result['total_calls']}\nFirst Contact: {result.get('global_first_contact')}\nLast Contact: {result.get('global_last_contact')}"
        })

        # Create edges to all suspects who called this number with detailed metrics
        for suspect_data in result["suspects"]:
            suspect = suspect_data["name"]
            if suspect in suspect_nodes:
                edges.append({
                    "from": suspect,
                    "to": node_id,
                    "value": suspect_data["call_count"],
                    "label": str(suspect_data["call_count"]),
                    "title": f"Calls: {suspect_data['call_count']}\nDuration: {suspect_data.get('total_duration', 0)}s\nFirst: {suspect_data.get('first_contact')}\nLast: {suspect_data.get('last_contact')}"
                })

    return {
        "suspects": suspect_names,
        "common_numbers_count": len([r for r in results]),
        "network": {
            "nodes": nodes,
            "edges": edges
        },
        "detailed_numbers": [
            {
                "number": r["_id"],
                "total_calls": r["total_calls"],
                "total_duration_seconds": r.get("total_duration_all", 0),
                "first_contact": r.get("global_first_contact").isoformat() if r.get("global_first_contact") else None,
                "last_contact": r.get("global_last_contact").isoformat() if r.get("global_last_contact") else None,
                "suspects": [
                    {
                        "name": s["name"],
                        "call_count": s["call_count"],
                        "total_duration": s.get("total_duration", 0),
                        "first_contact": s.get("first_contact").isoformat() if s.get("first_contact") else None,
                        "last_contact": s.get("last_contact").isoformat() if s.get("last_contact") else None
                    }
                    for s in r["suspects"]
                ]
            }
            for r in results
        ]
    }

async def find_common_towers(suspect_names: List[str]) -> Dict:
    """Find common cell towers between multiple suspects with color coding"""
    db = await get_database()

    pipeline = [
        {"$match": {
            "suspect_name": {"$in": suspect_names},
            "cell_tower_id": {"$exists": True, "$ne": None}
        }},
        {"$group": {
            "_id": {
                "suspect": "$suspect_name",
                "tower": "$cell_tower_id"
            },
            "lat": {"$first": "$location_lat"},
            "lon": {"$first": "$location_lon"},
            "usage_count": {"$sum": 1},
            "first_seen": {"$min": "$call_start_time"},
            "last_seen": {"$max": "$call_start_time"}
        }},
        {"$group": {
            "_id": "$_id.tower",
            "suspects": {"$push": {
                "name": "$_id.suspect",
                "usage_count": "$usage_count",
                "first_seen": "$first_seen",
                "last_seen": "$last_seen"
            }},
            "lat": {"$first": "$lat"},
            "lon": {"$first": "$lon"},
            "total_usage": {"$sum": "$usage_count"}
        }},
        {"$sort": {"total_usage": -1}}
    ]

    results = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    # Color mapping for suspects
    suspect_colors = {
        suspect_names[i]: ["#ec4899", "#8b5cf6", "#10b981", "#f59e0b", "#3b82f6", "#ef4444", "#14b8a6"][i % 7]
        for i in range(len(suspect_names))
    }

    # Organize by suspect
    suspect_towers = {name: [] for name in suspect_names}
    co_locations = []
    all_towers = []  # All towers for each suspect (for map display)

    # Separate common towers (shared) from individual towers
    for result in results:
        tower_id = result["_id"]
        lat = result.get("lat")
        lon = result.get("lon")

        # If no lat/lon, try to decode
        if not lat or not lon:
            decoded = await decode_cell_id(tower_id)
            if decoded:
                lat = decoded.get("lat")
                lon = decoded.get("lon")

        is_shared = len(result["suspects"]) > 1

        tower_info = {
            "tower_id": tower_id,
            "location": {"lat": lat, "lon": lon},
            "suspects": result["suspects"],
            "shared_with": [s["name"] for s in result["suspects"] if s["name"] != tower_id] if is_shared else [],
            "total_usage": result["total_usage"],
            "is_shared": is_shared,
            "first_seen": result["suspects"][0].get("first_seen") if result["suspects"] else None,
            "last_seen": result["suspects"][0].get("last_seen") if result["suspects"] else None
        }

        if is_shared:
            co_locations.append(tower_info)

        for suspect_data in result["suspects"]:
            suspect = suspect_data["name"]
            if suspect in suspect_towers:
                suspect_towers[suspect].append({
                    **tower_info,
                    "color": suspect_colors.get(suspect, "#6366f1"),
                    "suspect_usage": suspect_data["usage_count"]
                })
                all_towers.append({
                    **tower_info,
                    "suspect": suspect,
                    "color": suspect_colors.get(suspect, "#6366f1")
                })

    return {
        "suspects": suspect_names,
        "suspect_colors": suspect_colors,
        "co_locations": co_locations,
        "suspect_towers": suspect_towers,
        "all_towers": all_towers  # For map visualization with colors
    }

async def find_common_imei(suspect_names: List[str]) -> Dict:
    """Find common IMEI devices between multiple suspects"""
    db = await get_database()

    pipeline = [
        {"$match": {
            "suspect_name": {"$in": suspect_names},
            "imei": {"$exists": True, "$ne": None}
        }},
        {"$group": {
            "_id": {
                "suspect": "$suspect_name",
                "imei": "$imei"
            },
            "usage_count": {"$sum": 1},
            "first_seen": {"$min": "$call_start_time"},
            "last_seen": {"$max": "$call_start_time"}
        }},
        {"$group": {
            "_id": "$_id.imei",
            "suspects": {"$push": {
                "name": "$_id.suspect",
                "usage_count": "$usage_count",
                "first_seen": "$first_seen",
                "last_seen": "$last_seen"
            }},
            "total_usage": {"$sum": "$usage_count"}
        }},
        {"$match": {"$expr": {"$gt": [{"$size": "$suspects"}, 1]}}},
        {"$sort": {"total_usage": -1}}
    ]

    results = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    common_devices = []
    for result in results:
        device_info = await decode_imei(result["_id"])
        common_devices.append({
            "imei": result["_id"],
            "device_info": device_info,
            "shared_by": result["suspects"],
            "total_usage": result["total_usage"]
        })

    return {
        "suspects": suspect_names,
        "common_devices_count": len(common_devices),
        "common_devices": common_devices
    }
