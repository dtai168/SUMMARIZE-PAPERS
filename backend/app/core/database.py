from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings

settings = get_settings()
client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=10000)
database: AsyncIOMotorDatabase = client[settings.mongo_db_name]


def get_database() -> AsyncIOMotorDatabase:
    return database


async def ping_database() -> None:
    await client.admin.command("ping")
