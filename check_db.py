import asyncio
import motor.motor_asyncio
import json
import os

async def check_db():
    mongodb_uri = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017')
    client = motor.motor_asyncio.AsyncIOMotorClient(mongodb_uri)
    db = client.pvp_stats
    
    # Check servers collection
    print("=== Servers Collection ===")
    servers = await db.servers.find({}).to_list(length=100)
    print(json.dumps(servers, default=str, indent=2))
    
    # Check guilds collection
    print("\n=== Guilds Collection ===")
    guilds = await db.guilds.find({}).to_list(length=100)
    print(json.dumps(guilds, default=str, indent=2))

asyncio.run(check_db())
