from fastapi import FastAPI, UploadFile, File, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
import os
from typing import List, Optional
import json
from datetime import datetime, date

from database import get_database, test_connection
from models import CDRRecord
from cdr_processor import process_cdr_file, detect_format

# Helper function to convert datetime objects to strings for JSON serialization
def convert_datetime_to_str(obj):
    """Recursively convert datetime objects to ISO format strings"""
    # Handle datetime objects
    if isinstance(obj, datetime):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    # Handle date objects (but not datetime, since datetime is a subclass of date)
    elif isinstance(obj, date) and not isinstance(obj, datetime):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    # Handle dictionaries
    elif isinstance(obj, dict):
        return {key: convert_datetime_to_str(value) for key, value in obj.items()}
    # Handle lists
    elif isinstance(obj, list):
        return [convert_datetime_to_str(item) for item in obj]
    # Handle tuples
    elif isinstance(obj, tuple):
        return tuple(convert_datetime_to_str(item) for item in obj)
    # Handle sets
    elif isinstance(obj, set):
        return {convert_datetime_to_str(item) for item in obj}
    # Check for datetime-like objects (has isoformat method)
    elif hasattr(obj, 'isoformat') and callable(getattr(obj, 'isoformat')):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    else:
        return obj
from analytics import (
    analyze_imei,
    analyze_cell_towers,
    analyze_contacts,
    analyze_sms_services,
    analyze_international_calls,
    find_common_numbers,
    find_common_towers,
    find_common_imei,
)
from cdr_analytics import (
    generate_all_analytics,
    generate_summary,
    generate_corrected,
    generate_max_call,
    generate_max_circle_call,
    generate_daily_first_last,
    generate_max_duration,
    generate_max_imei,
    generate_daily_imei_tracking,
    generate_max_location,
    generate_daily_first_last_location
)
from excel_export import export_to_excel
from utils import generate_sample_data, export_to_json, export_to_csv
from pdf_export import create_pdf_report
from kml_export import export_to_kml
from geofencing import router as geofencing_router, manager as geofence_manager
from intelligence_analytics import (
    generate_intelligence_overview,
    generate_contact_network,
    generate_temporal_heatmap,
    generate_imei_timeline,
    generate_movement_map,
    generate_colocation_analysis,
    generate_anomalies,
    generate_audit_trail
)

# Create uploads directory (use absolute path)
uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(uploads_dir, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    try:
        await test_connection()
        print("✓ MongoDB connection successful")
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}")
    yield
    # Shutdown (if needed)
    pass

app = FastAPI(
    title="CDR Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(geofencing_router, prefix="/api", tags=["geofencing"])

# Mount static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

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

# Serve frontend files
@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend index.html"""
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    return FileResponse(os.path.join(frontend_dir, "index.html"))

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
    """Upload and process CDR file - auto-analyzes and returns results"""
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
        result = await process_cdr_file(file_path, suspect_name, format_info, geofence_manager)

        # Auto-generate analytics
        session_id = result.get("session_id")
        try:
            analytics = await generate_all_analytics(session_id=session_id, suspect_name=suspect_name)
            analytics = convert_datetime_to_str(analytics)
        except Exception as analytics_error:
            # If analytics generation fails, return empty analytics but don't fail the upload
            print(f"Analytics generation error: {analytics_error}")
            import traceback
            traceback.print_exc()
            analytics = {}

        # Convert result dictionary as well (might contain datetime objects)
        result_clean = convert_datetime_to_str(result)

        # Convert format_info as well (might contain datetime objects)
        format_info_clean = convert_datetime_to_str(format_info) if format_info else None

        response = {
            "success": True,
            "message": f"Processed {result_clean.get('records_inserted', 0)} records",
            "session_id": session_id,
            "suspect_name": result_clean.get("suspect_name"),
            "format_detected": format_info_clean,
            "records_inserted": result_clean.get("records_inserted", 0),
            "analytics": analytics  # Include analytics in response
        }

        # Ensure entire response is JSON serializable (double-check)
        response = convert_datetime_to_str(response)

        # Use JSONResponse to ensure proper serialization
        return JSONResponse(content=response)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = str(e)
        print(f"Upload error: {error_detail}")
        print(traceback.format_exc())
        # Ensure error response is JSON serializable
        try:
            # Try to convert any datetime objects in the error detail
            if "datetime" in error_detail.lower():
                error_detail = error_detail.replace("Object of type datetime", "Datetime object")
        except:
            pass
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

@app.get("/api/export")
async def export_data(format: str = "json", session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Export data to JSON, CSV, KML, or Excel"""
    try:
        identifier = session_id or suspect_name or "cdr"
        if format.lower() == "csv":
            file_path = await export_to_csv(suspect_name or identifier)
            return FileResponse(
                file_path,
                media_type="text/csv",
                filename=f"{identifier}_cdr_export.csv"
            )
        elif format.lower() == "kml":
            api_key = os.getenv("OPENCELLID_API_KEY")
            file_path = await export_to_kml(suspect_name or identifier, api_key)
            return FileResponse(
                file_path,
                media_type="application/vnd.google-earth.kml+xml",
                filename=f"{identifier}_cdr_path.kml"
            )
        elif format.lower() == "excel" or format.lower() == "xlsx":
            file_path = await export_to_excel(session_id=session_id, suspect_name=suspect_name)
            return FileResponse(
                file_path,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=f"{identifier}_cdr_analysis.xlsx"
            )
        else:
            file_path = await export_to_json(suspect_name or identifier)
            return FileResponse(
                file_path,
                media_type="application/json",
                filename=f"{identifier}_cdr_export.json"
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

# Comprehensive CDR Analytics Endpoints
@app.get("/api/analytics/comprehensive")
async def get_comprehensive_analytics(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get all 10 analytical views at once"""
    try:
        analytics = await generate_all_analytics(session_id=session_id, suspect_name=suspect_name)
        analytics = convert_datetime_to_str(analytics)
        return {"success": True, "data": analytics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/comprehensive/{identifier}")
async def get_comprehensive_analytics_by_id(identifier: str):
    """Get all 10 analytical views by session_id or suspect_name"""
    try:
        # Try as session_id first, fallback to suspect_name
        analytics = await generate_all_analytics(session_id=identifier, suspect_name=identifier)
        analytics = convert_datetime_to_str(analytics)
        return {"success": True, "data": analytics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/summary")
async def get_summary(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get Summary analytics"""
    try:
        data = await generate_summary(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return JSONResponse(content={"success": True, "data": data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/corrected")
async def get_corrected(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get Corrected dataset"""
    try:
        data = await generate_corrected(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/max-call")
async def get_max_call(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get MaxCall analytics"""
    try:
        data = await generate_max_call(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/max-circle-call")
async def get_max_circle_call(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get MaxCircleCall analytics"""
    try:
        data = await generate_max_circle_call(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/daily-first-last")
async def get_daily_first_last(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get DailyFirstLast analytics"""
    try:
        data = await generate_daily_first_last(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/max-duration")
async def get_max_duration(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get MaxDuration analytics"""
    try:
        data = await generate_max_duration(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/max-imei")
async def get_max_imei(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get MaxIMEI analytics"""
    try:
        data = await generate_max_imei(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/daily-imei-tracking")
async def get_daily_imei_tracking(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get DailyIMEIATracking analytics"""
    try:
        data = await generate_daily_imei_tracking(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/max-location")
async def get_max_location(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get MaxLocation analytics"""
    try:
        data = await generate_max_location(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/daily-first-last-location")
async def get_daily_first_last_location(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get DailyFirstLastLocation analytics"""
    try:
        data = await generate_daily_first_last_location(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export-pdf-session")
async def export_pdf_report_session(session_id: Optional[str] = None):
    """Export comprehensive PDF report for session with all analysis tabs"""
    try:
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")

        # Generate all analytics for the session
        from cdr_analytics import generate_all_analytics
        all_analytics = await generate_all_analytics(session_id=session_id)

        # Get summary data
        summary_data = all_analytics.get("Summary", {})

        # Calculate additional statistics
        from database import get_database
        db = await get_database()

        total_records = summary_data.get("total_calls", 0)
        date_range = f"{summary_data.get('first_activity_date', 'N/A')} to {summary_data.get('last_activity_date', 'N/A')}"

        # Get IMEI, towers, contacts, SMS, and international data if available
        # For session-based, we'll use the analytics data we already have
        imei_data = {}
        towers_data = {}
        contacts_data = {}
        sms_data = {}
        intl_data = {}

        # Try to get suspect name from session to fetch detailed analytics
        session_record = await db.cdr_records.find_one({"session_id": session_id})
        suspect_name = session_record.get("suspect_name") if session_record else None

        if suspect_name:
            try:
                imei_data = await analyze_imei(suspect_name)
                towers_data = await analyze_cell_towers(suspect_name)
                contacts_data = await analyze_contacts(suspect_name)
                sms_data = await analyze_sms_services(suspect_name)
                intl_data = await analyze_international_calls(suspect_name)
            except:
                pass  # If detailed analytics fail, use summary data only

        # Calculate total duration
        duration_pipeline = [
            {"$match": {"session_id": session_id}},
            {"$group": {
                "_id": None,
                "total_duration": {"$sum": "$duration_seconds"}
            }}
        ]
        duration_result = await db.cdr_records.aggregate(duration_pipeline).to_list(length=1)
        total_duration_hours = (duration_result[0].get('total_duration', 0) or 0) / 3600 if duration_result else 0

        unique_contacts = len(contacts_data.get('most_called', [])) if contacts_data else summary_data.get("unique_b_numbers", 0)

        analytics_data = {
            "summary": {
                "total_records": total_records,
                "date_range": date_range,
                "unique_contacts": unique_contacts,
                "total_duration_hours": total_duration_hours,
                "unique_imeis": summary_data.get("unique_imeis", 0),
                "unique_towers": summary_data.get("unique_locations", 0)
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
        pdf_path = os.path.join(exports_dir, f"session_{session_id}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

        report_name = f"Session {session_id}" if not suspect_name else suspect_name
        create_pdf_report(report_name, analytics_data, pdf_path)

        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"cdr_analysis_{session_id}_report.pdf"
        )
    except Exception as e:
        import traceback
        print(f"Error generating PDF: {e}")
        print(traceback.format_exc())
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

# Intelligence-Grade Analytics Endpoints
@app.get("/api/analytics/intelligence/overview")
async def get_intelligence_overview(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get intelligence overview with KPIs, story, and alerts"""
    try:
        data = await generate_intelligence_overview(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/intelligence/network")
async def get_intelligence_network(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get contact network graph"""
    try:
        data = await generate_contact_network(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/intelligence/timeline")
async def get_intelligence_timeline(session_id: Optional[str] = None, suspect_name: Optional[str] = None, call_type: str = "all"):
    """Get temporal activity heatmap"""
    try:
        data = await generate_temporal_heatmap(session_id=session_id, suspect_name=suspect_name, call_type=call_type)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/intelligence/imei")
async def get_intelligence_imei(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get IMEI switch timeline"""
    try:
        data = await generate_imei_timeline(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/intelligence/location")
async def get_intelligence_location(session_id: Optional[str] = None, suspect_name: Optional[str] = None, layer: str = "day"):
    """Get geo-spatial movement map"""
    try:
        data = await generate_movement_map(session_id=session_id, suspect_name=suspect_name, layer=layer)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/intelligence/colocation")
async def get_intelligence_colocation(session_id: Optional[str] = None, suspect_name: Optional[str] = None, window_minutes: int = 15):
    """Get co-location analysis"""
    try:
        data = await generate_colocation_analysis(session_id=session_id, suspect_name=suspect_name, window_minutes=window_minutes)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/intelligence/anomalies")
async def get_intelligence_anomalies(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get anomaly detection results"""
    try:
        data = await generate_anomalies(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/intelligence/audit")
async def get_intelligence_audit(session_id: Optional[str] = None, suspect_name: Optional[str] = None):
    """Get forensic audit trail"""
    try:
        data = await generate_audit_trail(session_id=session_id, suspect_name=suspect_name)
        data = convert_datetime_to_str(data)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Catch-all route for frontend files (must be after all API routes)
@app.get("/{path:path}", include_in_schema=False)
async def serve_frontend_files(path: str):
    """Serve frontend static files"""
    # Don't serve API routes through this catch-all
    if path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not found")

    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    file_path = os.path.join(frontend_dir, path)

    # If file exists, serve it
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)

    # Otherwise, serve index.html for client-side routing
    return FileResponse(os.path.join(frontend_dir, "index.html"))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
