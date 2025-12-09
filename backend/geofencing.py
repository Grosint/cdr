from fastapi import APIRouter, HTTPException, WebSocket
from pydantic import BaseModel, Field
from typing import List, Dict
from geojson import Polygon
from datetime import datetime
from database import get_database
import asyncio
from bson.objectid import ObjectId

router = APIRouter()

class Geofence(BaseModel):
    id: str = Field(..., alias="_id")
    name: str
    description: str
    geometry: Polygon
    suspect_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True

class GeofenceCreate(BaseModel):
    name: str
    description: str
    geometry: Polygon
    suspect_name: str

    class Config:
        arbitrary_types_allowed = True

@router.post("/geofences", response_model=Geofence)
async def create_geofence(geofence: GeofenceCreate):
    db = await get_database()
    geofence_dict = geofence.dict()
    geofence_dict["_id"] = str(ObjectId())
    geofence_dict["created_at"] = datetime.utcnow()
    result = await db.geofences.insert_one(geofence_dict)
    created_geofence = await db.geofences.find_one({"_id": result.inserted_id})
    return created_geofence

@router.get("/geofences", response_model=List[Geofence])
async def get_geofences():
    db = await get_database()
    geofences = await db.geofences.find().to_list(1000)
    return geofences

@router.put("/geofences/{geofence_id}", response_model=Geofence)
async def update_geofence(geofence_id: str, geofence: Geofence):
    db = await get_database()
    await db.geofences.update_one({"_id": geofence_id}, {"$set": geofence.dict(by_alias=True)})
    updated_geofence = await db.geofences.find_one({"_id": geofence_id})
    if updated_geofence is None:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return updated_geofence

@router.delete("/geofences/{geofence_id}")
async def delete_geofence(geofence_id: str):
    db = await get_database()
    result = await db.geofences.delete_one({"_id": geofence_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return {"message": "Geofence deleted successfully"}

# WebSocket for real-time alerts
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@router.websocket("/ws/geofence-alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)
