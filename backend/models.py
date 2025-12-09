from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class CallType(str, Enum):
    VOICE = "voice"
    SMS = "sms"
    DATA = "data"

class CallDirection(str, Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"

class CallStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    MISSED = "missed"
    BUSY = "busy"

class CDRRecord(BaseModel):
    """CDR Record Model"""
    call_id: Optional[str] = None
    calling_number: str
    called_number: str
    call_start_time: datetime
    call_end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    call_type: CallType = CallType.VOICE
    direction: CallDirection = CallDirection.OUTGOING
    cell_tower_id: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    lac: Optional[int] = None  # Location Area Code
    mnc: Optional[int] = None  # Mobile Network Code
    mcc: Optional[int] = None  # Mobile Country Code
    imei: Optional[str] = None
    imsi: Optional[str] = None
    cost: Optional[float] = None
    data_volume_mb: Optional[float] = None
    call_status: CallStatus = CallStatus.COMPLETED
    sms_content: Optional[str] = None
    suspect_name: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# Vendor format mappings
VENDOR_FORMATS = {
    "ericsson": {
        "calling_number": ["a_number", "msisdn_a", "calling_party", "caller_id"],
        "called_number": ["b_number", "msisdn_b", "called_party", "callee_id"],
        "call_start_time": ["start_time", "event_time", "timestamp", "date_time"],
        "duration_seconds": ["duration", "call_duration", "talk_time"],
        "cell_tower_id": ["cell_id", "tower_id", "lac", "location_area_code"],
        "imei": ["imei", "device_id"],
        "imsi": ["imsi", "subscriber_id"]
    },
    "nokia": {
        "calling_number": ["a_party", "originating_number", "msisdn_a"],
        "called_number": ["b_party", "terminating_number", "msisdn_b"],
        "call_start_time": ["event_time", "start_timestamp"],
        "duration_seconds": ["duration", "call_length"],
        "cell_tower_id": ["cell_identity", "ci", "cell_id"],
        "imei": ["equipment_id", "imei"],
        "imsi": ["imsi"]
    },
    "huawei": {
        "calling_number": ["calling_number", "a_number", "msisdn_a"],
        "called_number": ["called_number", "b_number", "msisdn_b"],
        "call_start_time": ["start_time", "event_time"],
        "duration_seconds": ["duration", "call_duration"],
        "cell_tower_id": ["cell_id", "lac", "ci"],
        "imei": ["imei"],
        "imsi": ["imsi"]
    },
    "standard": {
        "calling_number": ["calling_number", "caller", "from_number"],
        "called_number": ["called_number", "callee", "to_number"],
        "call_start_time": ["call_start_time", "start_time", "timestamp"],
        "call_end_time": ["call_end_time", "end_time"],
        "duration_seconds": ["duration_seconds", "duration", "call_duration"],
        "call_type": ["call_type", "type", "service_type"],
        "direction": ["direction", "call_direction"],
        "cell_tower_id": ["cell_tower_id", "tower_id", "cell_id", "ci", "cell_identity"],
        "location_lat": ["location_lat", "latitude", "lat"],
        "location_lon": ["location_lon", "longitude", "lon"],
        "lac": ["lac", "location_area_code", "location_area"],
        "mnc": ["mnc", "mobile_network_code", "network_code"],
        "mcc": ["mcc", "mobile_country_code", "country_code"],
        "imei": ["imei", "device_imei"],
        "imsi": ["imsi", "subscriber_imsi"],
        "cost": ["cost", "charge", "amount"],
        "data_volume_mb": ["data_volume_mb", "data_volume", "volume_mb"],
        "call_status": ["call_status", "status"],
        "sms_content": ["sms_content", "message", "text"]
    }
}
