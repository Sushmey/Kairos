"""MongoDB access layer."""

from kairos.db.mongo import close_mongo, get_database, get_mongo_client

__all__ = ["close_mongo", "get_database", "get_mongo_client"]
