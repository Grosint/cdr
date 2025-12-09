"""
KML Export Module for CDR Data
Converts CDR records to KML format for Google Earth visualization
"""
from typing import List, Dict
from datetime import datetime
from database import get_database
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom


def prettify_xml(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


async def lookup_cell_tower_coordinates(mcc: int, mnc: int, lac: int, cell_id: int, api_key: str = None) -> Dict:
    """
    Lookup cell tower coordinates using OpenCellID API or similar service

    Args:
        mcc: Mobile Country Code
        mnc: Mobile Network Code
        lac: Location Area Code
        cell_id: Cell ID
        api_key: Optional API key for OpenCellID

    Returns:
        Dict with 'lat' and 'lon' keys, or None if not found
    """
    import httpx

    # Try OpenCellID API first
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # OpenCellID API endpoint
                url = "https://opencellid.org/cell/get"
                params = {
                    "key": api_key,
                    "mcc": mcc,
                    "mnc": mnc,
                    "lac": lac,
                    "cellid": cell_id,
                    "format": "json"
                }
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "ok" and "lat" in data and "lon" in data:
                        return {
                            "lat": float(data["lat"]),
                            "lon": float(data["lon"]),
                            "range": data.get("range", 0),
                            "source": "opencellid"
                        }
        except Exception as e:
            print(f"OpenCellID API error: {e}")

    # Try alternative: Mozilla Location Service (no API key required)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = "https://location.services.mozilla.com/v1/geolocate"
            payload = {
                "cellTowers": [{
                    "mobileCountryCode": mcc,
                    "mobileNetworkCode": mnc,
                    "locationAreaCode": lac,
                    "cellId": cell_id
                }]
            }
            response = await client.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                if "location" in data:
                    return {
                        "lat": float(data["location"]["lat"]),
                        "lon": float(data["location"]["lng"]),
                        "accuracy": data.get("accuracy", 0),
                        "source": "mozilla"
                    }
    except Exception as e:
        print(f"Mozilla Location Service error: {e}")

    return None


async def export_to_kml(suspect_name: str, api_key: str = None, lookup_coordinates: bool = True) -> str:
    """
    Export CDR data to KML format for Google Earth visualization

    Args:
        suspect_name: Name of the suspect
        api_key: Optional OpenCellID API key for cell tower lookup

    Returns:
        Path to the generated KML file
    """
    db = await get_database()

    # Get all records for suspect, ordered by time
    cursor = db.cdr_records.find(
        {"suspect_name": suspect_name}
    ).sort("call_start_time", 1)

    records = await cursor.to_list(length=None)

    if not records:
        raise ValueError(f"No records found for suspect: {suspect_name}")

    # Create KML root element
    kml = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    document = ET.SubElement(kml, "Document")

    # Document name
    name = ET.SubElement(document, "name")
    name.text = f"CDR Path - {suspect_name}"

    # Description
    description = ET.SubElement(document, "description")
    description.text = f"Call Detail Records visualization for {suspect_name}. Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    # Style for path line
    style = ET.SubElement(document, "Style", id="pathStyle")
    line_style = ET.SubElement(style, "LineStyle")
    color = ET.SubElement(line_style, "color")
    color.text = "ff00ffff"  # Yellow color (ABGR format)
    width = ET.SubElement(line_style, "width")
    width.text = "3"

    # Style for markers
    marker_style = ET.SubElement(document, "Style", id="markerStyle")
    icon_style = ET.SubElement(marker_style, "IconStyle")
    icon = ET.SubElement(icon_style, "Icon")
    href = ET.SubElement(icon, "href")
    href.text = "http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"
    scale = ET.SubElement(icon_style, "scale")
    scale.text = "1.2"

    # Collect coordinates for path
    coordinates = []
    placemarks = []

    # Process records and get coordinates
    for idx, record in enumerate(records):
        lat = record.get("location_lat")
        lon = record.get("location_lon")

        # If no coordinates, try to lookup using cell tower info
        if lookup_coordinates and (not lat or not lon) and record.get("mcc") and record.get("mnc") and record.get("lac") and record.get("cell_tower_id"):
            try:
                mcc = int(record.get("mcc"))
                mnc = int(record.get("mnc"))
                lac = int(record.get("lac"))
                cell_id_str = str(record.get("cell_tower_id"))
                # Try to extract numeric cell ID
                cell_id = None
                if cell_id_str.isdigit():
                    cell_id = int(cell_id_str)
                else:
                    # Try to extract numbers from string
                    import re
                    numbers = re.findall(r'\d+', cell_id_str)
                    if numbers:
                        cell_id = int(numbers[0])

                if cell_id:
                    coords = await lookup_cell_tower_coordinates(mcc, mnc, lac, cell_id, api_key)
                    if coords:
                        lat = coords["lat"]
                        lon = coords["lon"]
                        # Update record in database for future use
                        await db.cdr_records.update_one(
                            {"_id": record["_id"]},
                            {"$set": {"location_lat": lat, "location_lon": lon}}
                        )
            except (ValueError, TypeError) as e:
                print(f"Error parsing cell tower data for record {idx}: {e}")
                continue
            except Exception as e:
                print(f"Error looking up coordinates for record {idx}: {e}")
                continue

        if lat and lon:
            coordinates.append(f"{lon},{lat},0")

            # Create placemark for this location
            placemark = ET.SubElement(document, "Placemark")
            pm_name = ET.SubElement(placemark, "name")
            pm_name.text = f"Call {idx + 1}"

            pm_description = ET.SubElement(placemark, "description")
            call_time = record.get("call_start_time")
            if isinstance(call_time, datetime):
                time_str = call_time.strftime("%Y-%m-%d %H:%M:%S")
            else:
                time_str = str(call_time)

            pm_description.text = f"""
            <![CDATA[
            <table>
                <tr><td><b>Time:</b></td><td>{time_str}</td></tr>
                <tr><td><b>Type:</b></td><td>{record.get('call_type', 'N/A')}</td></tr>
                <tr><td><b>Direction:</b></td><td>{record.get('direction', 'N/A')}</td></tr>
                <tr><td><b>Called:</b></td><td>{record.get('called_number', 'N/A')}</td></tr>
                <tr><td><b>Duration:</b></td><td>{record.get('duration_seconds', 0)}s</td></tr>
                <tr><td><b>Cell ID:</b></td><td>{record.get('cell_tower_id', 'N/A')}</td></tr>
                <tr><td><b>LAC:</b></td><td>{record.get('lac', 'N/A')}</td></tr>
            </table>
            ]]>
            """

            pm_style = ET.SubElement(placemark, "styleUrl")
            pm_style.text = "#markerStyle"

            point = ET.SubElement(placemark, "Point")
            pm_coords = ET.SubElement(point, "coordinates")
            pm_coords.text = f"{lon},{lat},0"

            # Add timestamp
            time_span = ET.SubElement(placemark, "TimeSpan")
            begin = ET.SubElement(time_span, "begin")
            if isinstance(call_time, datetime):
                begin.text = call_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                begin.text = str(call_time)

            placemarks.append(placemark)

    # Create path line if we have coordinates
    if len(coordinates) > 1:
        path_placemark = ET.SubElement(document, "Placemark")
        path_name = ET.SubElement(path_placemark, "name")
        path_name.text = f"Path - {suspect_name}"

        path_style = ET.SubElement(path_placemark, "styleUrl")
        path_style.text = "#pathStyle"

        line_string = ET.SubElement(path_placemark, "LineString")
        tessellate = ET.SubElement(line_string, "tessellate")
        tessellate.text = "1"
        path_coords = ET.SubElement(line_string, "coordinates")
        path_coords.text = " ".join(coordinates)

    # Create exports directory
    exports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")
    os.makedirs(exports_dir, exist_ok=True)

    # Save KML file
    filename = os.path.join(
        exports_dir,
        f"{suspect_name}_cdr_path_{datetime.now().strftime('%Y%m%d_%H%M%S')}.kml"
    )

    # Write KML file
    kml_string = prettify_xml(kml)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(kml_string)

    return filename
