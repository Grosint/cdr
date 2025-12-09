import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "cdr_intelligence")

client = None
database = None

async def get_database():
    """Get MongoDB database instance"""
    global client, database

    if database is None:
        try:
            client = AsyncIOMotorClient(MONGODB_URL)
            database = client[DATABASE_NAME]

            # Create indexes for performance
            await create_indexes(database)

        except Exception as e:
            raise ConnectionFailure(f"Failed to connect to MongoDB: {e}")

    return database

async def create_indexes(db):
    """Create database indexes for common query patterns"""
    try:
        # Single field indexes
        await db.cdr_records.create_index("suspect_name")
        await db.cdr_records.create_index("calling_number")
        await db.cdr_records.create_index("called_number")
        await db.cdr_records.create_index("imei")
        await db.cdr_records.create_index("imsi")
        await db.cdr_records.create_index("cell_tower_id")
        await db.cdr_records.create_index("call_start_time")
        await db.cdr_records.create_index("call_type")

        # Compound indexes for common queries
        await db.cdr_records.create_index([("suspect_name", 1), ("call_start_time", -1)])
        await db.cdr_records.create_index([("suspect_name", 1), ("imei", 1)])
        await db.cdr_records.create_index([("calling_number", 1), ("called_number", 1)])
        await db.cdr_records.create_index([("suspect_name", 1), ("cell_tower_id", 1)])

        # Geospatial index for location queries
        await db.cdr_records.create_index([("location_lat", 1), ("location_lon", 1)])

        print("✓ Database indexes created successfully")
    except Exception as e:
        print(f"Warning: Index creation failed: {e}")

async def test_connection():
    """Test MongoDB connection"""
    try:
        db = await get_database()
        await db.command("ping")
        return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False

async def close_connection():
    """Close MongoDB connection"""
    global client
    if client:
        client.close()
