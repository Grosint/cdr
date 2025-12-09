#!/usr/bin/env python3
"""
Test MongoDB connection and database setup
"""

import asyncio
import os
from dotenv import load_dotenv
from backend.database import test_connection, get_database

load_dotenv()

async def main():
    print("🔍 Testing MongoDB Connection...")
    print(f"MongoDB URL: {os.getenv('MONGODB_URL', 'Not set')}")
    print(f"Database Name: {os.getenv('DATABASE_NAME', 'cdr_intelligence')}")
    print()

    try:
        result = await test_connection()
        if result:
            print("✅ MongoDB connection successful!")

            # Test database access
            db = await get_database()
            collections = await db.list_collection_names()
            print(f"✅ Database accessible. Collections: {collections}")

            # Test collection
            count = await db.cdr_records.count_documents({})
            print(f"✅ CDR records collection exists. Current records: {count}")

        else:
            print("❌ MongoDB connection failed!")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nPlease check:")
        print("1. MongoDB URL in .env file")
        print("2. Network connectivity")
        print("3. MongoDB Atlas IP whitelist settings")

if __name__ == "__main__":
    asyncio.run(main())
