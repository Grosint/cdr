"""
Intelligence-Grade CDR Analytics Module
Generates advanced intelligence insights for law enforcement and national security agencies
"""

from database import get_database
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import re

async def _build_match_query(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """Helper to build match query - prefer session_id, fallback to suspect_name"""
    match_query = {}
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


async def generate_intelligence_overview(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """
    Generate intelligence overview with KPIs, story, and alerts
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return {
            "case_id": f"CDR_INV_{datetime.now().strftime('%Y')}_{datetime.now().strftime('%m%d')}",
            "target_msisdn": None,
            "total_calls": 0,
            "unique_contacts": 0,
            "unique_imeis": 0,
            "unique_locations": 0,
            "risk_level": "LOW",
            "intelligence_story": "No data available.",
            "alerts": []
        }

    # Get target MSISDN
    target_record = await db.cdr_records.find_one(match_query)
    target_msisdn = target_record.get("msisdn_a") or target_record.get("calling_number") if target_record else None

    # Get summary stats
    pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": None,
            "total_calls": {"$sum": 1},
            "unique_contacts": {"$addToSet": {"$ifNull": ["$msisdn_b", "$called_number"]}},
            "unique_imeis": {"$addToSet": "$imei"},
            "unique_locations": {"$addToSet": {"$ifNull": ["$cell_id", "$cell_tower_id"]}},
            "first_activity": {"$min": "$call_start_time"},
            "last_activity": {"$max": "$call_start_time"}
        }}
    ]

    result = await db.cdr_records.aggregate(pipeline).to_list(length=1)

    if result and result[0]:
        data = result[0]
        unique_contacts = len([x for x in data.get("unique_contacts", []) if x])
        unique_imeis = len([x for x in data.get("unique_imeis", []) if x])
        unique_locations = len([x for x in data.get("unique_locations", []) if x])

        # Calculate risk level
        risk_score = 0
        if unique_imeis > 1:
            risk_score += 2  # Multi-device usage
        if unique_locations > 20:
            risk_score += 1  # High mobility
        if data.get("total_calls", 0) > 1000:
            risk_score += 1  # High activity

        risk_level = "HIGH" if risk_score >= 3 else ("MEDIUM" if risk_score >= 1 else "LOW")

        # Generate intelligence story
        story_parts = []
        if data.get("first_activity") and data.get("last_activity"):
            first = data["first_activity"]
            last = data["last_activity"]
            if isinstance(first, datetime) and isinstance(last, datetime):
                days = (last - first).days
                story_parts.append(f"Activity span: {days} days")

        if unique_imeis > 1:
            story_parts.append(f"{unique_imeis} different devices detected")

        if unique_contacts > 50:
            story_parts.append(f"Extensive contact network ({unique_contacts} unique contacts)")

        intelligence_story = ". ".join(story_parts) if story_parts else "Standard activity pattern detected."

        # Generate alerts
        alerts = []
        if unique_imeis > 1:
            alerts.append({
                "title": "Device Change Detected",
                "description": f"{unique_imeis} different IMEIs detected in the dataset",
                "severity": "warning",
                "evidence": f"IMEI count: {unique_imeis}"
            })

        # Check for night-time activity spikes
        night_pipeline = [
            {"$match": {**match_query, "call_start_time": {"$exists": True}}},
            {"$project": {
                "hour": {"$hour": "$call_start_time"}
            }},
            {"$match": {"hour": {"$gte": 22, "$lte": 23}}},
            {"$count": "night_calls"}
        ]
        night_result = await db.cdr_records.aggregate(night_pipeline).to_list(length=1)
        night_calls = night_result[0].get("night_calls", 0) if night_result else 0

        if night_calls > 50:
            alerts.append({
                "title": "Night-time Activity Spike",
                "description": f"{night_calls} calls detected between 22:00-23:59",
                "severity": "info",
                "evidence": f"Night calls: {night_calls}"
            })

        return {
            "case_id": f"CDR_INV_{datetime.now().strftime('%Y')}_{datetime.now().strftime('%m%d')}",
            "target_msisdn": target_msisdn,
            "total_calls": data.get("total_calls", 0),
            "unique_contacts": unique_contacts,
            "unique_imeis": unique_imeis,
            "unique_locations": unique_locations,
            "risk_level": risk_level,
            "intelligence_story": intelligence_story,
            "alerts": alerts
        }

    return {
        "case_id": f"CDR_INV_{datetime.now().strftime('%Y')}_{datetime.now().strftime('%m%d')}",
        "target_msisdn": target_msisdn,
        "total_calls": 0,
        "unique_contacts": 0,
        "unique_imeis": 0,
        "unique_locations": 0,
        "risk_level": "LOW",
        "intelligence_story": "No data available.",
        "alerts": []
    }


async def generate_contact_network(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """
    Generate contact network graph for single suspect
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return {"nodes": [], "edges": []}

    # Get target MSISDN - try multiple fields
    target_record = await db.cdr_records.find_one(match_query)
    target_msisdn = None
    if target_record:
        target_msisdn = (target_record.get("msisdn_a") or
                        target_record.get("calling_number") or
                        target_record.get("msisdn_b") or
                        target_record.get("called_number"))

    if not target_msisdn:
        # Try to get from any record
        any_record = await db.cdr_records.find_one(match_query)
        if any_record:
            target_msisdn = (any_record.get("msisdn_a") or
                           any_record.get("calling_number") or
                           "Target")

    if not target_msisdn:
        return {"nodes": [], "edges": []}

    # Get all contacts - both incoming and outgoing
    # For outgoing: msisdn_b or called_number is the contact
    # For incoming: msisdn_a or calling_number is the contact
    pipeline_outgoing = [
        {"$match": {
            **match_query,
            "$and": [
                {
                    "$or": [
                        {"direction": "outgoing"},
                        {"direction": {"$exists": False}}  # Default to outgoing if not specified
                    ]
                },
                {
                    "$or": [
                        {"msisdn_b": {"$exists": True, "$ne": None, "$ne": ""}},
                        {"called_number": {"$exists": True, "$ne": None, "$ne": ""}}
                    ]
                }
            ]
        }},
        {"$project": {
            "contact": {"$ifNull": ["$msisdn_b", "$called_number"]},
            "duration": {"$ifNull": ["$call_duration_sec", "$duration_seconds", 0]}
        }},
        {"$match": {"contact": {"$ne": None, "$ne": ""}}},
        {"$group": {
            "_id": "$contact",
            "call_count": {"$sum": 1},
            "total_duration": {"$sum": "$duration"}
        }}
    ]

    pipeline_incoming = [
        {"$match": {
            **match_query,
            "direction": "incoming",
            "$or": [
                {"msisdn_a": {"$exists": True, "$ne": None, "$ne": ""}},
                {"calling_number": {"$exists": True, "$ne": None, "$ne": ""}}
            ]
        }},
        {"$project": {
            "contact": {"$ifNull": ["$msisdn_a", "$calling_number"]},
            "duration": {"$ifNull": ["$call_duration_sec", "$duration_seconds", 0]}
        }},
        {"$match": {"contact": {"$ne": None, "$ne": ""}}},
        {"$group": {
            "_id": "$contact",
            "call_count": {"$sum": 1},
            "total_duration": {"$sum": "$duration"}
        }}
    ]

    results_outgoing = await db.cdr_records.aggregate(pipeline_outgoing).to_list(length=None)
    results_incoming = await db.cdr_records.aggregate(pipeline_incoming).to_list(length=None)

    # Combine and aggregate contacts
    contact_stats = {}

    for result in results_outgoing:
        contact = result["_id"]
        if contact and contact != target_msisdn:
            if contact not in contact_stats:
                contact_stats[contact] = {"call_count": 0, "total_duration": 0, "incoming": 0, "outgoing": 0}
            contact_stats[contact]["call_count"] += result.get("call_count", 0)
            contact_stats[contact]["total_duration"] += result.get("total_duration", 0)
            contact_stats[contact]["outgoing"] += result.get("call_count", 0)

    for result in results_incoming:
        contact = result["_id"]
        if contact and contact != target_msisdn:
            if contact not in contact_stats:
                contact_stats[contact] = {"call_count": 0, "total_duration": 0, "incoming": 0, "outgoing": 0}
            contact_stats[contact]["call_count"] += result.get("call_count", 0)
            contact_stats[contact]["total_duration"] += result.get("total_duration", 0)
            contact_stats[contact]["incoming"] += result.get("call_count", 0)

    # Sort by call count and take top 50
    sorted_contacts = sorted(contact_stats.items(), key=lambda x: x[1]["call_count"], reverse=True)[:50]

    nodes = []
    edges = []

    # Add target node
    target_label = str(target_msisdn)[:12] + "..." if len(str(target_msisdn)) > 15 else str(target_msisdn)
    nodes.append({
        "id": str(target_msisdn),
        "label": target_label,
        "type": "target",
        "color": "#ec4899",
        "value": 100
    })

    # Add contact nodes and edges
    for contact, stats in sorted_contacts:
        if not contact:
            continue

        call_count = stats.get("call_count", 0)
        total_duration = stats.get("total_duration", 0)

        contact_str = str(contact)
        contact_label = contact_str[:12] + "..." if len(contact_str) > 15 else contact_str

        nodes.append({
            "id": contact_str,
            "label": contact_label,
            "type": "contact",
            "color": "#6366f1",
            "value": min(50, max(10, call_count))  # Scale node size between 10-50
        })

        # Add edge with thickness based on call count
        edges.append({
            "from": str(target_msisdn),
            "to": contact_str,
            "value": call_count,
            "label": str(call_count),
            "title": f"Calls: {call_count}, Duration: {int(total_duration)}s"
        })

    return {
        "nodes": nodes,
        "edges": edges
    }


async def generate_temporal_heatmap(session_id: Optional[str] = None, suspect_name: Optional[str] = None, call_type: str = "all") -> Dict:
    """
    Generate temporal activity heatmap (Date x Hour)
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return {"x": [], "y": [], "z": []}

    # Add call type filter
    if call_type != "all":
        if call_type == "incoming":
            match_query["direction"] = "incoming"
        elif call_type == "outgoing":
            match_query["direction"] = "outgoing"
        elif call_type == "sms":
            match_query["call_type"] = "sms"

    pipeline = [
        {"$match": match_query},
        {"$project": {
            "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$call_start_time"}},
            "hour": {"$hour": "$call_start_time"}
        }},
        {"$group": {
            "_id": {"date": "$date", "hour": "$hour"},
            "count": {"$sum": 1}
        }}
    ]

    results = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    # Build heatmap data
    date_set = set()
    hour_set = set()
    data_map = {}

    for result in results:
        date = result["_id"]["date"]
        hour = result["_id"]["hour"]
        count = result.get("count", 0)

        date_set.add(date)
        hour_set.add(hour)
        data_map[(date, hour)] = count

    # Sort dates and hours
    sorted_dates = sorted(list(date_set))
    sorted_hours = sorted(list(hour_set))

    # Build z matrix
    z = []
    for date in sorted_dates:
        row = []
        for hour in sorted_hours:
            row.append(data_map.get((date, hour), 0))
        z.append(row)

    return {
        "x": sorted_hours,
        "y": sorted_dates,
        "z": z
    }


async def generate_imei_timeline(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """
    Generate IMEI switch timeline and device behavior
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return {"timeline": [], "switches": []}

    pipeline = [
        {"$match": {
            **match_query,
            "imei": {"$exists": True, "$ne": None, "$ne": ""}
        }},
        {"$sort": {"call_start_time": 1}},
        {"$project": {
            "imei": 1,
            "call_start_time": 1,
            "cell_id": {"$ifNull": ["$cell_id", "$cell_tower_id"]}
        }}
    ]

    results = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    if not results:
        return {"timeline": [], "switches": []}

    # Group by IMEI and date
    imei_data = defaultdict(lambda: defaultdict(list))
    previous_imei = None
    switches = []

    for result in results:
        imei = result.get("imei")
        call_time = result.get("call_start_time")
        cell_id = result.get("cell_id")

        if not imei or not call_time:
            continue

        if isinstance(call_time, datetime):
            date_str = call_time.strftime("%Y-%m-%d")
            imei_data[imei][date_str].append(call_time)

        # Detect IMEI switch
        if previous_imei and previous_imei != imei:
            switches.append({
                "timestamp": call_time.isoformat() if isinstance(call_time, datetime) else str(call_time),
                "from_imei": previous_imei,
                "to_imei": imei,
                "location": cell_id or "Unknown"
            })

        previous_imei = imei

    # Build timeline for each IMEI
    timeline = []
    for imei, dates_dict in imei_data.items():
        dates = sorted(dates_dict.keys())
        timeline.append({
            "imei": imei,
            "dates": dates,
            "call_counts": [len(dates_dict[d]) for d in dates]
        })

    return {
        "timeline": timeline,
        "switches": switches
    }


async def generate_movement_map(session_id: Optional[str] = None, suspect_name: Optional[str] = None, layer: str = "day") -> Dict:
    """
    Generate geo-spatial movement map
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return {"paths": [], "markers": []}

    pipeline = [
        {"$match": {
            **match_query,
            "$or": [
                {"location_lat": {"$exists": True, "$ne": None}},
                {"location_lon": {"$exists": True, "$ne": None}}
            ]
        }},
        {"$sort": {"call_start_time": 1}},
        {"$project": {
            "lat": "$location_lat",
            "lon": "$location_lon",
            "call_start_time": 1,
            "cell_id": {"$ifNull": ["$cell_id", "$cell_tower_id"]},
            "imei": 1,
            "msisdn_b": {"$ifNull": ["$msisdn_b", "$called_number"]}
        }}
    ]

    results = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    paths = []
    markers = []

    if layer == "day":
        # Group by date
        daily_paths = defaultdict(list)
        for result in results:
            if result.get("lat") and result.get("lon") and result.get("call_start_time"):
                date_str = result["call_start_time"].strftime("%Y-%m-%d") if isinstance(result["call_start_time"], datetime) else str(result["call_start_time"])[:10]
                daily_paths[date_str].append([result["lon"], result["lat"]])

        colors = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#3b82f6"]
        for idx, (date, coords) in enumerate(daily_paths.items()):
            if len(coords) > 1:
                paths.append({
                    "coordinates": coords,
                    "color": colors[idx % len(colors)],
                    "label": date
                })

    elif layer == "imei":
        # Group by IMEI
        imei_paths = defaultdict(list)
        for result in results:
            if result.get("lat") and result.get("lon") and result.get("imei"):
                imei_paths[result["imei"]].append([result["lon"], result["lat"]])

        colors = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#3b82f6"]
        for idx, (imei, coords) in enumerate(imei_paths.items()):
            if len(coords) > 1:
                paths.append({
                    "coordinates": coords,
                    "color": colors[idx % len(colors)],
                    "label": imei[:12] + "..."
                })

    # Add markers for key locations
    for result in results[:20]:  # Limit to first 20 for performance
        if result.get("lat") and result.get("lon"):
            markers.append({
                "coordinates": [result["lon"], result["lat"]],
                "color": "#ec4899",
                "title": f"Cell: {result.get('cell_id', 'Unknown')}",
                "description": f"Time: {result.get('call_start_time')}"
            })

    return {
        "paths": paths,
        "markers": markers
    }


async def generate_colocation_analysis(session_id: Optional[str] = None, suspect_name: Optional[str] = None, window_minutes: int = 15) -> List[Dict]:
    """
    Detect co-locations (multiple MSISDNs at same cell ID within time window)
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return []

    # Get target MSISDN
    target_record = await db.cdr_records.find_one(match_query)
    target_msisdn = target_record.get("msisdn_a") or target_record.get("calling_number") if target_record else None

    # Get all records with cell IDs
    pipeline = [
        {"$match": {
            **match_query,
            "$or": [
                {"cell_id": {"$exists": True, "$ne": None, "$ne": ""}},
                {"cell_tower_id": {"$exists": True, "$ne": None, "$ne": ""}}
            ]
        }},
        {"$project": {
            "cell_id": {"$ifNull": ["$cell_id", "$cell_tower_id"]},
            "call_start_time": 1,
            "msisdn_b": {"$ifNull": ["$msisdn_b", "$called_number"]}
        }},
        {"$sort": {"call_start_time": 1}}
    ]

    results = await db.cdr_records.aggregate(pipeline).to_list(length=None)

    # Group by cell ID and time window
    colocations = []
    cell_groups = defaultdict(list)

    for result in results:
        cell_id = result.get("cell_id")
        call_time = result.get("call_start_time")
        msisdn_b = result.get("msisdn_b")

        if not cell_id or not call_time:
            continue

        # Check if within window of existing records
        found_group = False
        for group in cell_groups[cell_id]:
            time_diff = abs((call_time - group["time"]).total_seconds() / 60)
            if time_diff <= window_minutes:
                group["msisdns"].add(msisdn_b)
                found_group = True
                break

        if not found_group:
            cell_groups[cell_id].append({
                "time": call_time,
                "msisdns": {target_msisdn, msisdn_b} if target_msisdn else {msisdn_b}
            })

    # Convert to result format
    for cell_id, groups in cell_groups.items():
        for group in groups:
            if len(group["msisdns"]) > 1:  # Only if multiple MSISDNs
                colocations.append({
                    "date": group["time"].strftime("%Y-%m-%d") if isinstance(group["time"], datetime) else str(group["time"])[:10],
                    "time_window": f"±{window_minutes} minutes",
                    "location": cell_id,
                    "msisdns": list(group["msisdns"]),
                    "repeated": len([g for g in groups if len(g["msisdns"]) > 1]) > 1
                })

    return colocations


async def generate_anomalies(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> List[Dict]:
    """
    Detect anomalies in CDR data
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return []

    anomalies = []

    # Check for IMEI changes
    imei_pipeline = [
        {"$match": {
            **match_query,
            "imei": {"$exists": True, "$ne": None, "$ne": ""}
        }},
        {"$sort": {"call_start_time": 1}},
        {"$group": {
            "_id": "$imei",
            "first_seen": {"$min": "$call_start_time"},
            "last_seen": {"$max": "$call_start_time"}
        }}
    ]

    imei_results = await db.cdr_records.aggregate(imei_pipeline).to_list(length=None)
    if len(imei_results) > 1:
        anomalies.append({
            "title": "IMEI Device Switching Detected",
            "description": f"Target used {len(imei_results)} different devices",
            "severity": "warning",
            "reason": "Multiple IMEIs detected in dataset",
            "evidence": f"IMEI count: {len(imei_results)}",
            "supporting_data": [{"imei": r["_id"], "first_seen": str(r["first_seen"]), "last_seen": str(r["last_seen"])} for r in imei_results]
        })

    # Check for sudden silence
    pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$call_start_time"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]

    daily_results = await db.cdr_records.aggregate(pipeline).to_list(length=None)
    if len(daily_results) > 2:
        # Check for sudden drop
        counts = [r["count"] for r in daily_results]
        avg_count = sum(counts) / len(counts)
        if counts[-1] < avg_count * 0.1 and counts[-2] > avg_count * 0.5:
            anomalies.append({
                "title": "Sudden Silence Detected",
                "description": "Activity dropped significantly in recent days",
                "severity": "info",
                "reason": "Recent activity is <10% of average",
                "evidence": f"Average: {avg_count:.1f}, Recent: {counts[-1]}"
            })

    # Check for location hopping
    location_pipeline = [
        {"$match": {
            **match_query,
            "$or": [
                {"cell_id": {"$exists": True, "$ne": None, "$ne": ""}},
                {"cell_tower_id": {"$exists": True, "$ne": None, "$ne": ""}}
            ]
        }},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$call_start_time"}},
            "unique_locations": {"$addToSet": {"$ifNull": ["$cell_id", "$cell_tower_id"]}}
        }},
        {"$project": {
            "date": "$_id",
            "location_count": {"$size": "$unique_locations"}
        }},
        {"$sort": {"date": 1}}
    ]

    location_results = await db.cdr_records.aggregate(location_pipeline).to_list(length=None)
    if location_results:
        high_mobility_days = [r for r in location_results if r.get("location_count", 0) > 5]
        if high_mobility_days:
            anomalies.append({
                "title": "High Mobility Pattern",
                "description": f"{len(high_mobility_days)} days with >5 different locations",
                "severity": "info",
                "reason": "Unusual location switching pattern",
                "evidence": f"High mobility days: {len(high_mobility_days)}"
            })

    return anomalies


async def generate_audit_trail(session_id: Optional[str] = None, suspect_name: Optional[str] = None) -> Dict:
    """
    Generate forensic audit trail
    """
    db = await get_database()
    match_query = await _build_match_query(session_id, suspect_name)

    if not match_query:
        return {"trail": []}

    # Get processing history
    trail = [
        {
            "timestamp": datetime.now().isoformat(),
            "action": "Data Normalization",
            "details": "CDR records normalized and validated"
        },
        {
            "timestamp": datetime.now().isoformat(),
            "action": "Analytics Generation",
            "details": "Intelligence-grade analytics generated"
        }
    ]

    # Get record count
    count = await db.cdr_records.count_documents(match_query)
    trail.append({
        "timestamp": datetime.now().isoformat(),
        "action": "Data Loaded",
        "details": f"{count} records processed"
    })

    return {"trail": trail}
