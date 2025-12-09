# CDR Intelligence Platform

A comprehensive Call Detail Record (CDR) Intelligence Platform for telecom data analysis with advanced analytics, visualizations, and multi-vendor format support.

## Features

### Core Capabilities
- **Format Auto-Detection**: Automatically detects and normalizes CDR formats from various telecom vendors (Ericsson, Nokia, Huawei, and standard formats)
- **Single CDR Analysis**: Deep dive into individual suspect data
  - IMEI Analysis with device decoding
  - Cell Tower Analysis with interactive maps
  - Contact Analysis (most called numbers, longest duration calls)
  - SMS Service Detection (WhatsApp, Uber, banks, etc.)
  - International Calls Analysis by country
- **Multiple CDR Analysis**: Compare and find connections between suspects
  - Common Numbers Network Graph
  - Common Cell Towers Map with co-locations
  - Common IMEI Device Detection
- **Modern UI**: Glass morphism design with purple/pink gradients
- **Interactive Visualizations**:
  - MapLibre GL maps with OpenStreetMap tiles
  - Plotly charts for trends
  - Vis.js network graphs

## Tech Stack

- **Backend**: Python FastAPI
- **Database**: MongoDB Atlas (cloud database)
- **Frontend**: HTML5, CSS3, JavaScript (vanilla)
- **Visualizations**: MapLibre GL, Plotly, Vis.js

## Installation

1. **Clone the repository**
   ```bash
   cd cdr
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your MongoDB Atlas connection string:
   ```
   MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
   DATABASE_NAME=cdr_intelligence
   PORT=8000
   OPENCELLID_API_KEY=your_opencellid_api_key_here  # Optional: for cell tower coordinate lookup
   ```

5. **Start the backend server**
   ```bash
   cd backend
   python main.py
   ```
   Or using uvicorn:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

6. **Open the frontend**
   - Open `frontend/index.html` in a web browser
   - Or serve it using a local server:
     ```bash
     cd frontend
     python -m http.server 8080
     ```
     Then navigate to `http://localhost:8080`

## Usage

### Uploading CDR Files

1. Navigate to the "Upload CDR" section
2. Drag and drop CDR files (CSV, XLS, XLSX) or click "Browse Files"
3. Optionally enter a suspect name
4. The system will auto-detect the file format and process it

### Single Analysis

1. Go to "Single Analysis"
2. Select a suspect from the dropdown
3. Click "Analyze"
4. Explore different analysis tabs:
   - **IMEI Analysis**: View unique devices, usage patterns, and timelines
   - **Cell Towers**: Interactive map showing tower locations
   - **Contacts**: Most called numbers and longest duration calls
   - **SMS Services**: Detected services from SMS patterns
   - **International**: Calls by country with charts

### Multiple Analysis

1. Go to "Multiple Analysis"
2. Select 2 or more suspects using checkboxes
3. Click "Analyze"
4. View:
   - **Common Numbers**: Network graph showing connections
   - **Common Towers**: Map with co-location markers
   - **Common IMEI**: Shared devices between suspects

### Utilities

- **Generate Sample Data**: Create realistic sample CDR records for testing
  - Available in the Utilities section of the UI
  - Or use the API: `POST /api/utils/generate-sample`
- **Export Data**: Export suspect data to multiple formats:
  - **JSON**: Structured data export
  - **CSV**: Spreadsheet-compatible format
  - **KML**: Google Earth visualization file
    - Automatically looks up cell tower coordinates using MCC, MNC, LAC, and Cell ID
    - Creates a path visualization showing the suspect's movement over time
    - Can be opened directly in Google Earth to view the trajectory
- **Connection Tester**: Test MongoDB connection
  ```bash
  python test_connection.py
  ```
- **SQLite Migration**: Migrate existing SQLite CDR databases to MongoDB
  ```bash
  python backend/migrate_sqlite.py <sqlite_file> [suspect_name]
  ```
- **Excel Format Generator**: Generate sample CDR files in various vendor formats
  ```bash
  python backend/generate_excel_samples.py
  ```
  Creates sample files in `samples/` directory for testing format auto-detection

## Data Model

CDR records include:
- `call_id`: Unique call identifier
- `calling_number`: Phone number of caller
- `called_number`: Phone number of recipient
- `call_start_time`: Call start timestamp
- `call_end_time`: Call end timestamp
- `duration_seconds`: Call duration
- `call_type`: voice/sms/data
- `direction`: incoming/outgoing
- `cell_tower_id`: Cell tower identifier
- `location_lat`/`location_lon`: GPS coordinates
- `lac`: Location Area Code
- `mnc`: Mobile Network Code
- `mcc`: Mobile Country Code
- `imei`: Device IMEI
- `imsi`: Subscriber IMSI
- `cost`: Call cost
- `data_volume_mb`: Data usage (for data calls)
- `call_status`: completed/failed/missed/busy
- `sms_content`: SMS message content
- `suspect_name`: Associated suspect name

## Supported File Formats

- CSV (Comma-separated values)
- XLS (Excel 97-2003)
- XLSX (Excel 2007+)

## Vendor Format Support

The platform automatically detects and maps columns from:
- Ericsson
- Nokia
- Huawei
- Standard CDR formats

## API Endpoints

- `GET /health` - Health check
- `POST /api/upload` - Upload CDR file
- `GET /api/suspects` - List all suspects
- `GET /api/analytics/single/imei` - IMEI analysis
- `GET /api/analytics/single/cell-towers` - Cell tower analysis
- `GET /api/analytics/single/contacts` - Contact analysis
- `GET /api/analytics/single/sms-services` - SMS analysis
- `GET /api/analytics/single/international` - International calls
- `GET /api/analytics/multiple/common-numbers` - Common numbers
- `GET /api/analytics/multiple/common-towers` - Common towers
- `GET /api/analytics/multiple/common-imei` - Common IMEI
- `GET /api/export/{suspect_name}?format=json|csv|kml` - Export data (JSON, CSV, or KML for Google Earth)
- `POST /api/utils/generate-sample` - Generate sample data

## Database Indexes

The platform automatically creates indexes for:
- Single field indexes: suspect_name, calling_number, called_number, imei, imsi, cell_tower_id, call_start_time
- Compound indexes: (suspect_name, call_start_time), (suspect_name, imei), etc.
- Geospatial index: (location_lat, location_lon)

## Development

### Project Structure
```
cdr/
├── backend/
│   ├── main.py                  # FastAPI application
│   ├── database.py              # MongoDB connection
│   ├── models.py                # Data models
│   ├── cdr_processor.py         # File processing
│   ├── analytics.py             # Analysis functions
│   ├── utils.py                 # Utilities
│   ├── migrate_sqlite.py        # SQLite to MongoDB migration
│   └── generate_excel_samples.py # Excel format generator
├── frontend/
│   ├── index.html               # Main HTML
│   ├── styles.css               # Styles
│   └── app.js                   # Frontend logic
├── uploads/                     # Uploaded files directory
├── exports/                     # Exported JSON files directory
├── test_connection.py           # MongoDB connection tester
├── requirements.txt             # Python dependencies
└── README.md                    # This file
├── frontend/
│   ├── index.html        # Main HTML
│   ├── styles.css        # Styles
│   └── app.js            # Frontend logic
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## License

This project is designed for law enforcement and telecom operators for legitimate CDR analysis purposes.

## Support

For issues or questions, please check the codebase or contact the development team.
