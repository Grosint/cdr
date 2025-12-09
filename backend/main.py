from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import os
from typing import List, Optional
import json
from datetime import datetime

from database import get_database, test_connection
from models import CDRRecord
from cdr_processor import process_cdr_file, detect_format
from analytics import (
    analyze_imei,
    analyze_cell_towers,
    analyze_contacts,
    analyze_sms_services,
    analyze_international_calls,
    find_common_numbers,
    find_common_towers,
    find_common_imei
)
from utils import generate_sample_data, export_to_json, export_to_csv
from pdf_export import create_pdf_report
from kml_export import export_to_kml

app = FastAPI(title="CDR Intelligence Platform", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Add exception handler for HTTPException to ensure CORS headers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """HTTP exception handler to ensure CORS headers are always present"""
    return JSONResponse(
        content={"success": False, "error": exc.detail},
        status_code=exc.status_code,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Create uploads directory (use absolute path)
uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(uploads_dir, exist_ok=True)

@app.on_event("startup")
async def startup_event():
    """Test database connection on startup"""
    try:
        await test_connection()
        print("✓ MongoDB connection successful")
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}")

@app.get("/")
async def root():
    return {"message": "CDR Intelligence Platform API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        db_status = await test_connection()
        return {
            "status": "healthy",
            "database": "connected" if db_status else "disconnected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.post("/api/upload")
async def upload_cdr(
    file: UploadFile = File(...),
    suspect_name: Optional[str] = None,
    auto_detect: bool = True
):
    """Upload and process CDR file"""
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        # Check file extension
        allowed_extensions = ['.csv', '.xls', '.xlsx', '.json']
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Allowed: {', '.join(allowed_extensions)}"
            )

        # Save uploaded file (use absolute path)
        uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        file_path = os.path.join(uploads_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Detect format if auto_detect is enabled
        format_info = None
        if auto_detect:
            format_info = await detect_format(file_path)

        # Process CDR file
        result = await process_cdr_file(file_path, suspect_name, format_info)

        return {
            "success": True,
            "message": f"Processed {result['records_inserted']} records",
            "suspect_name": result.get("suspect_name"),
            "format_detected": format_info,
            "records_inserted": result["records_inserted"]
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = str(e)
        print(f"Upload error: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {error_detail}"
        )

@app.get("/api/cdr/format-detect")
async def detect_file_format(file_path: str):
    """Detect CDR file format"""
    try:
        format_info = await detect_format(file_path)
        return {"success": True, "format": format_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/single/imei")
async def get_imei_analysis(suspect_name: str):
    """Get IMEI analysis for a single suspect"""
    try:
        result = await analyze_imei(suspect_name)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/single/cell-towers")
async def get_cell_tower_analysis(
    suspect_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get cell tower analysis for a single suspect with optional date filters"""
    try:
        from datetime import datetime
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None
        result = await analyze_cell_towers(suspect_name, start_dt, end_dt)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/single/contacts")
async def get_contact_analysis(suspect_name: str):
    """Get contact analysis for a single suspect"""
    try:
        result = await analyze_contacts(suspect_name)
        return JSONResponse(
            content={"success": True, "data": result},
            status_code=200
        )
    except Exception as e:
        import traceback
        error_detail = str(e)
        print(f"Error in contact analysis: {error_detail}")
        print(traceback.format_exc())
        return JSONResponse(
            content={"success": False, "error": error_detail},
            status_code=500
        )

@app.get("/api/analytics/single/sms-services")
async def get_sms_analysis(suspect_name: str):
    """Get SMS service detection for a single suspect"""
    try:
        result = await analyze_sms_services(suspect_name)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/single/international")
async def get_international_analysis(suspect_name: str):
    """Get international calls analysis for a single suspect"""
    try:
        result = await analyze_international_calls(suspect_name)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/multiple/common-numbers")
async def get_common_numbers(suspect_names: List[str] = Query(...)):
    """Get common numbers network graph for multiple suspects"""
    try:
        result = await find_common_numbers(suspect_names)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/multiple/common-towers")
async def get_common_towers(suspect_names: List[str] = Query(...)):
    """Get common cell towers map for multiple suspects"""
    try:
        result = await find_common_towers(suspect_names)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/multiple/common-imei")
async def get_common_imei(suspect_names: List[str] = Query(...)):
    """Get common IMEI devices for multiple suspects"""
    try:
        result = await find_common_imei(suspect_names)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/suspects")
async def get_all_suspects():
    """Get list of all suspects in database"""
    try:
        db = await get_database()
        suspects = await db.cdr_records.distinct("suspect_name")
        return {"success": True, "suspects": [s for s in suspects if s]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/{suspect_name}")
async def export_suspect_data(suspect_name: str, format: str = "json"):
    """Export suspect data to JSON, CSV, or KML"""
    try:
        if format.lower() == "csv":
            file_path = await export_to_csv(suspect_name)
            return FileResponse(
                file_path,
                media_type="text/csv",
                filename=f"{suspect_name}_cdr_export.csv"
            )
        elif format.lower() == "kml":
            api_key = os.getenv("OPENCELLID_API_KEY")
            file_path = await export_to_kml(suspect_name, api_key)
            return FileResponse(
                file_path,
                media_type="application/vnd.google-earth.kml+xml",
                filename=f"{suspect_name}_cdr_path.kml"
            )
        else:
            file_path = await export_to_json(suspect_name)
            return FileResponse(
                file_path,
                media_type="application/json",
                filename=f"{suspect_name}_cdr_export.json"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/utils/generate-sample")
async def generate_sample(suspect_name: str, record_count: int = 100):
    """Generate sample CDR data"""
    try:
        result = await generate_sample_data(suspect_name, record_count)
        return {
            "success": True,
            "message": f"Generated {result} sample records",
            "records_generated": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export-pdf/{suspect_name}")
async def export_pdf_report(suspect_name: str):
    """Export comprehensive PDF report for suspect"""
    try:
        # Gather all analytics data
        imei_data = await analyze_imei(suspect_name)
        towers_data = await analyze_cell_towers(suspect_name)
        contacts_data = await analyze_contacts(suspect_name)
        sms_data = await analyze_sms_services(suspect_name)
        intl_data = await analyze_international_calls(suspect_name)

        # Calculate summary statistics
        from database import get_database
        db = await get_database()

        total_records = await db.cdr_records.count_documents({"suspect_name": suspect_name})

        date_pipeline = [
            {"$match": {"suspect_name": suspect_name}},
            {"$group": {
                "_id": None,
                "min_date": {"$min": "$call_start_time"},
                "max_date": {"$max": "$call_start_time"},
                "total_duration": {"$sum": "$duration_seconds"}
            }}
        ]
        date_result = await db.cdr_records.aggregate(date_pipeline).to_list(length=1)

        date_range = "N/A"
        total_duration_hours = 0
        if date_result:
            min_date = date_result[0].get('min_date')
            max_date = date_result[0].get('max_date')
            if min_date and max_date:
                date_range = f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
            total_duration_hours = (date_result[0].get('total_duration', 0) or 0) / 3600

        unique_contacts = len(contacts_data.get('most_called', []))

        analytics_data = {
            "summary": {
                "total_records": total_records,
                "date_range": date_range,
                "unique_contacts": unique_contacts,
                "total_duration_hours": total_duration_hours,
                "unique_imeis": imei_data.get('unique_imeis', 0),
                "unique_towers": towers_data.get('unique_towers', 0)
            },
            "imei": imei_data,
            "towers": towers_data,
            "contacts": contacts_data,
            "sms": sms_data,
            "international": intl_data
        }

        # Create PDF
        exports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")
        os.makedirs(exports_dir, exist_ok=True)
        pdf_path = os.path.join(exports_dir, f"{suspect_name}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

        create_pdf_report(suspect_name, analytics_data, pdf_path)

        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"{suspect_name}_cdr_report.pdf"
        )
    except Exception as e:
        import traceback
        print(f"Error generating PDF: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
