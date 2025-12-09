# KML Export and Cell Tower Lookup Guide

## Overview

The CDR Intelligence Platform now supports exporting CDR data to KML (Keyhole Markup Language) format for visualization in Google Earth. This feature automatically looks up cell tower coordinates using MCC, MNC, LAC, and Cell ID parameters.

## Features

### 1. Cell Tower Coordinate Lookup

The system can automatically resolve cell tower locations using:
- **MCC** (Mobile Country Code)
- **MNC** (Mobile Network Code)
- **LAC** (Location Area Code)
- **Cell ID** (Cell Tower ID)

#### Supported APIs

1. **OpenCellID API** (Primary)
   - Requires API key (free tier available)
   - Set `OPENCELLID_API_KEY` in your `.env` file
   - Get your API key from: https://www.opencellid.org/

2. **Mozilla Location Service** (Fallback)
   - No API key required
   - Used automatically if OpenCellID is unavailable

### 2. KML Export

The KML export creates a Google Earth-compatible file that includes:
- **Placemarks**: Individual call locations with detailed information
- **Path Line**: Connected path showing the suspect's movement trajectory
- **Timestamps**: Time information for each location
- **Call Details**: Type, direction, duration, and contact information

## Usage

### Via Web Interface

1. Navigate to **Utilities** section
2. Select a suspect from the dropdown
3. Click **"Export to KML (Google Earth)"** button
4. The KML file will be downloaded automatically

### Via API

```bash
GET /api/export/{suspect_name}?format=kml
```

Example:
```bash
curl http://localhost:8000/api/export/JohnDoe?format=kml -o john_doe_path.kml
```

### Opening in Google Earth

1. **Install Google Earth** (if not already installed)
   - Download from: https://www.google.com/earth/
   - Available for Windows, macOS, and Linux

2. **Open the KML file**
   - Double-click the downloaded `.kml` file, OR
   - Open Google Earth → File → Open → Select the KML file

3. **View the path**
   - The map will automatically zoom to show the suspect's path
   - Click on placemarks to see call details
   - Use the timeline slider to see movement over time

## Data Requirements

For optimal results, your CDR data should include:
- `cell_tower_id`: The cell tower identifier
- `lac`: Location Area Code
- `mnc`: Mobile Network Code
- `mcc`: Mobile Country Code
- `call_start_time`: Timestamp for each call

If coordinates (`location_lat`, `location_lon`) are already present, they will be used directly. Otherwise, the system will attempt to lookup coordinates using the cell tower parameters.

## Configuration

### Setting up OpenCellID API Key

1. Sign up for a free account at https://www.opencellid.org/
2. Get your API key from the dashboard
3. Add to your `.env` file:
   ```
   OPENCELLID_API_KEY=your_api_key_here
   ```

### Environment Variables

```bash
# Required
MONGODB_URL=your_mongodb_connection_string
DATABASE_NAME=cdr_intelligence

# Optional (for cell tower lookup)
OPENCELLID_API_KEY=your_opencellid_api_key
```

## KML File Structure

The generated KML file includes:

```xml
<kml>
  <Document>
    <name>CDR Path - SuspectName</name>
    <Style id="pathStyle">...</Style>
    <Style id="markerStyle">...</Style>
    <Placemark>
      <!-- Individual call locations -->
    </Placemark>
    <Placemark>
      <!-- Connected path line -->
    </Placemark>
  </Document>
</kml>
```

## Troubleshooting

### No coordinates found

- Ensure your CDR data includes MCC, MNC, LAC, and Cell ID
- Check that the values are in the correct format (integers)
- Verify your OpenCellID API key is valid (if using)

### KML file doesn't open

- Ensure Google Earth is installed
- Check that the file extension is `.kml`
- Try opening from within Google Earth (File → Open)

### Missing locations

- Some cell towers may not be in the database
- The system will skip records without coordinates
- Check the console logs for lookup errors

## Example Workflow

1. **Upload CDR file** with suspect name "JohnDoe"
2. **Verify data** includes MCC, MNC, LAC, Cell ID fields
3. **Export to KML** from Utilities section
4. **Open in Google Earth** to visualize the path
5. **Analyze movement** patterns and locations

## API Integration

The cell tower lookup function can also be used programmatically:

```python
from kml_export import lookup_cell_tower_coordinates

# Lookup coordinates
coords = await lookup_cell_tower_coordinates(
    mcc=404,      # India
    mnc=10,       # Airtel
    lac=12345,
    cell_id=67890,
    api_key="your_key"
)

if coords:
    print(f"Latitude: {coords['lat']}, Longitude: {coords['lon']}")
```

## Notes

- The system caches looked-up coordinates in the database for future use
- Multiple API services are tried automatically if one fails
- The KML export includes all records for the suspect, ordered by time
- Large datasets may take time to process due to API rate limits
