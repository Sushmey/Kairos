"""Async MongoDB client singleton."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from kairos.config import settings

_client: AsyncIOMotorClient | None = None
_persist_connection: bool = False


def set_mongo_persist(enabled: bool = True) -> None:
    """Keep the client open across requests (FastAPI / long-running workers)."""
    global _persist_connection
    _persist_connection = enabled


def get_mongo_client() -> AsyncIOMotorClient:
    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is not configured")
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_mongo_client()[settings.mongodb_db_name]


async def close_mongo() -> None:
    """Close the shared client. No-op when persist mode is on (web server)."""
    global _client
    if _persist_connection:
        return
    if _client is not None:
        _client.close()
        _client = None
