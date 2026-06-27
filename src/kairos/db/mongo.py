"""Async MongoDB client singleton."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from kairos.config import settings

_client: AsyncIOMotorClient | None = None


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
    global _client
    if _client is not None:
        _client.close()
        _client = None
