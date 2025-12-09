# Quick Start Guide

## Prerequisites

- Python 3.8 or higher
- MongoDB Atlas account (or local MongoDB instance)
- Modern web browser

## Setup Steps

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure MongoDB

1. Copy `.env.example` to `.env`
2. Edit `.env` and add your MongoDB Atlas connection string:
3
   ```

   MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
   DATABASE_NAME=cdr_intelligence
   PORT=8000
   ```

### 3. Start Backend Server

```bash
cd backend
python main.py
```

The server will start on `http://localhost:8000`

### 4. Open Frontend

Option 1: Open directly in browser

- Navigate to `frontend/index.html` and open it

Option 2: Serve with HTTP server

```bash
cd frontend
python -m http.server 8080

```

Then open `http://localhost:8080` in your browser

## First Steps

1. **Test Connection**: Check the connection status in the sidebar (should show "Connected")

2. **Generate Sample Data**:
   - Go to Utilities
   - Enter a suspect name (e.g., "John Doe")
   - Click "Generate" to create 100 sample records

3. **View Analysis**:
   - Go to Single Analysis
   - Select the suspect you created
   - Click "Analyze"
   - Explore different analysis tabs

4. **Upload Real CDR Data**:
   - Go to Upload CDR
   - Drag and drop your CDR file (CSV, XLS, or XLSX)
   - Enter suspect name (optional)
   - The system will auto-detect the format

## Troubleshooting

### MongoDB Connection Issues

- Verify your connection string in `.env`
- Check if your IP is whitelisted in MongoDB Atlas
- Ensure the database name is correct

### Frontend Not Loading

- Make sure the backend server is running
- Check browser console for errors
- Verify CORS is enabled (it should be by default)

### File Upload Errors

- Ensure file format is supported (CSV, XLS, XLSX)
- Check file size (very large files may take time)
- Verify file has required columns

## API Testing

You can test the API directly:

```bash
# Health check
curl http://localhost:8000/health

# List suspects
curl http://localhost:8000/api/suspects
```

## Next Steps

- Upload your CDR files
- Analyze individual suspects
- Compare multiple suspects
- Export data for reporting
