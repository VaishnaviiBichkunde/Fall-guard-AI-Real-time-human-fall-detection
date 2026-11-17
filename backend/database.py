"""
MongoDB Database Connection and Local Fallback Manager for Fall Guard AI.
Uses PyMongo with indexes on key fields. If MongoDB is unavailable,
transparently falls back to an in-memory/JSON storage engine.
"""

import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "fall_guard_ai")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages connection to MongoDB with seamless local JSON fallback."""

    def __init__(self):
        self.client = None
        self.db = None
        self.is_connected = False
        self._local_cache: Dict[str, List[Dict[str, Any]]] = {
            "incidents": [],
            "caregivers": [],
            "facilities": [],
            "rooms": [],
            "residents": [],
            "local_caretakers": [],
            "caretaker_assignments": [],
            "notifications": [],
            "emergency_timeline": [],
            "users": [],
            "cameras": [],
            "evaluation_trials": [],
            "user_baselines": [],
        }
        self._local_lock = threading.RLock()
        self._file_mtimes: Dict[str, float] = {}
        self._load_local_data()
        self._connect()

    def _connect(self):
        """Attempts to connect to MongoDB and create database indexes."""
        try:
            from pymongo import MongoClient, ASCENDING
            from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

            # Short timeout so app never hangs if MongoDB is not running locally
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            self.client.admin.command("ping")
            self.db = self.client[MONGO_DB_NAME]
            self.is_connected = True
            self._create_indexes()
            logger.info("Successfully connected to MongoDB at %s", MONGO_URI)
        except Exception as err:
            self.is_connected = False
            self.client = None
            self.db = None
            logger.warning(
                "MongoDB not reachable (%s). Operating in local persistent fallback mode.",
                err,
            )

    def _create_indexes(self):
        """Creates indexes for frequently queried fields."""
        if not self.is_connected or self.db is None:
            return
        try:
            from pymongo import ASCENDING

            # Incidents collection indexes
            self.db.incidents.create_index([("incident_id", ASCENDING)], unique=True)
            self.db.incidents.create_index([("timestamp", ASCENDING)])
            self.db.incidents.create_index([("camera_id", ASCENDING)])
            self.db.incidents.create_index([("status", ASCENDING)])
            self.db.incidents.create_index([("room_id", ASCENDING), ("status", ASCENDING)])

            # Caregivers collection indexes
            self.db.caregivers.create_index([("email", ASCENDING)], unique=True)
            self.db.caregivers.create_index([("is_active", ASCENDING)])

            collection_indexes = {
                "facilities": [("facility_id", ASCENDING)],
                "rooms": [("room_id", ASCENDING), ("facility_id", ASCENDING), ("camera_id", ASCENDING)],
                "residents": [("resident_id", ASCENDING), ("room_id", ASCENDING)],
                "local_caretakers": [("caretaker_id", ASCENDING), ("username", ASCENDING), ("email", ASCENDING), ("room_id", ASCENDING), ("availability", ASCENDING)],
                "caretaker_assignments": [("assignment_id", ASCENDING), ("incident_id", ASCENDING), ("room_id", ASCENDING), ("caretaker_id", ASCENDING)],
                "notifications": [("notification_id", ASCENDING), ("incident_id", ASCENDING), ("recipient_id", ASCENDING), ("created_at", ASCENDING)],
                "emergency_timeline": [("event_id", ASCENDING), ("incident_id", ASCENDING), ("timestamp", ASCENDING)],
                "users": [("user_id", ASCENDING), ("username", ASCENDING), ("role", ASCENDING)],
            }
            for collection_name, index_fields in collection_indexes.items():
                for field in index_fields:
                    unique = field[0] in {
                        "facility_id", "room_id", "resident_id", "caretaker_id",
                        "assignment_id", "notification_id", "event_id", "user_id",
                        "username", "email",
                    }
                    self.db[collection_name].create_index([field], unique=unique)

            # Cameras collection indexes
            self.db.cameras.create_index([("camera_id", ASCENDING)], unique=True)

            # Evaluation trials collection indexes
            self.db.evaluation_trials.create_index([("trial_id", ASCENDING)], unique=True)
            self.db.evaluation_trials.create_index([("activity_category", ASCENDING)])

            # User baselines collection indexes
            self.db.user_baselines.create_index([("user_id", ASCENDING)], unique=True)
            logger.info("MongoDB indexes verified successfully.")
        except Exception as err:
            logger.warning("Error creating MongoDB indexes: %s", err)

    def _get_local_file(self, collection_name: str) -> str:
        return os.path.join(DATA_DIR, f"{collection_name}.json")

    def _load_local_data(self):
        collection_names = set(self._local_cache)
        try:
            collection_names.update(
                os.path.splitext(filename)[0]
                for filename in os.listdir(DATA_DIR)
                if filename.endswith(".json")
            )
        except OSError as err:
            logger.error("Unable to list local data directory %s: %s", DATA_DIR, err)

        for coll in collection_names:
            filepath = self._get_local_file(coll)
            if not os.path.exists(filepath):
                continue
            try:
                self._file_mtimes[coll] = os.path.getmtime(filepath)
                with open(filepath, "r", encoding="utf-8") as f:
                    records = json.load(f)
                if not isinstance(records, list):
                    raise ValueError(f"{filepath} must contain a JSON list")
                self._local_cache[coll] = records
            except (OSError, json.JSONDecodeError, ValueError) as err:
                logger.error("Unable to load local collection %s: %s", coll, err)
                self._local_cache[coll] = []

    def _reload_if_modified(self, collection_name: str):
        filepath = self._get_local_file(collection_name)
        if not os.path.exists(filepath):
            return
        try:
            mtime = os.path.getmtime(filepath)
            if self._file_mtimes.get(collection_name) != mtime:
                with open(filepath, "r", encoding="utf-8") as f:
                    records = json.load(f)
                if isinstance(records, list):
                    self._local_cache[collection_name] = records
                    self._file_mtimes[collection_name] = mtime
        except Exception:
            pass

    def _save_local_data(self, collection_name: str):
        filepath = self._get_local_file(collection_name)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self._local_cache[collection_name], f, indent=2, default=str)
            self._file_mtimes[collection_name] = os.path.getmtime(filepath)
        except Exception as err:
            logger.error("Failed to write local backup file %s: %s", filepath, err)

    def insert_one(self, collection_name: str, document: Dict[str, Any]) -> bool:
        """Inserts a document into MongoDB or local fallback."""
        doc = dict(document)
        key_fields_by_collection = {
            "incidents": ("incident_id",),
            "caregivers": ("email",),
            "facilities": ("facility_id",),
            "rooms": ("room_id",),
            "residents": ("resident_id",),
            "local_caretakers": ("caretaker_id", "username", "email"),
            "caretaker_assignments": ("assignment_id",),
            "notifications": ("notification_id",),
            "emergency_timeline": ("event_id",),
            "users": ("user_id", "username"),
            "cameras": ("camera_id",),
            "evaluation_trials": ("trial_id",),
            "user_baselines": ("user_id",),
        }
        key_fields = key_fields_by_collection.get(collection_name)
        if not key_fields:
            raise ValueError(f"No persistence key is configured for collection '{collection_name}'.")
        key_field = next((field for field in key_fields if field in doc), None)
        if key_field is None:
            raise ValueError(
                f"Document for collection '{collection_name}' must include one of {key_fields}."
            )
        query = {key_field: doc[key_field]}

        with self._local_lock:
            records = self._local_cache.setdefault(collection_name, [])
            replaced = False
            for index, record in enumerate(records):
                if record.get(key_field) == doc[key_field]:
                    records[index] = doc
                    replaced = True
                    break
            if not replaced:
                records.insert(0, doc)
            self._save_local_data(collection_name)

        if self.is_connected and self.db is not None:
            try:
                # Remove MongoDB _id if present in document copy
                insert_doc = {k: v for k, v in doc.items() if k != "_id"}
                self.db[collection_name].replace_one(
                    query,
                    insert_doc,
                    upsert=True,
                )
                return True
            except Exception as err:
                logger.warning("MongoDB insert error: %s. Using local fallback.", err)
        return True

    def find(
        self,
        collection_name: str,
        query: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        sort: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Finds documents matching query with optional sort."""
        if self.is_connected and self.db is not None:
            try:
                cursor = self.db[collection_name].find(query or {}, {"_id": 0})
                if sort:
                    cursor = cursor.sort(sort)
                cursor = cursor.limit(limit)
                results = list(cursor)
                if results:
                    return results
            except Exception as err:
                logger.warning("MongoDB find error: %s. Falling back to local cache.", err)

        # Local fallback query matching
        self._reload_if_modified(collection_name)
        records = list(self._local_cache.get(collection_name, []))

        # Handle local sorting
        if sort and isinstance(sort, list) and len(sort) > 0:
            sort_field, sort_dir = sort[0]
            reverse = (sort_dir == -1 or str(sort_dir).upper() == "DESC")
            records.sort(key=lambda d: str(d.get(sort_field, "")), reverse=reverse)

        if not query:
            return records[:limit]

        def _doc_matches(doc, q):
            for k, v in q.items():
                if k == "$or" and isinstance(v, list):
                    if not any(_doc_matches(doc, subq) for subq in v):
                        return False
                elif isinstance(v, dict) and "$in" in v:
                    if doc.get(k) not in v["$in"]:
                        return False
                elif isinstance(v, dict) and "$regex" in v:
                    import re
                    val_str = str(doc.get(k, ""))
                    flags = re.IGNORECASE if v.get("$options") == "i" else 0
                    if not re.search(v["$regex"], val_str, flags):
                        return False
                elif doc.get(k) != v:
                    return False
            return True

        filtered = []
        for doc in records:
            if _doc_matches(doc, query):
                filtered.append(doc)
                if len(filtered) >= limit:
                    break
        return filtered

    def find_one(
        self,
        collection_name: str,
        query: Optional[Dict[str, Any]] = None,
        sort: Optional[Any] = None,
        *args,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        actual_sort = sort or kwargs.get("sort")
        results = self.find(collection_name, query or {}, limit=1, sort=actual_sort)
        return results[0] if results else None

    def update_one(
        self,
        collection_name: str,
        filter_query: Dict[str, Any],
        update_data: Dict[str, Any],
    ) -> bool:
        """Updates document matching filter_query."""
        updated = False
        for doc in self._local_cache.get(collection_name, []):
            match = all(doc.get(k) == v for k, v in filter_query.items())
            if match:
                doc.update(update_data)
                updated = True
                break
        if updated:
            self._save_local_data(collection_name)

        if self.is_connected and self.db is not None:
            try:
                self.db[collection_name].update_one(filter_query, {"$set": update_data})
                return True
            except Exception as err:
                logger.warning("MongoDB update error: %s", err)
        return updated

    def count_documents(self, collection_name: str, query: Optional[Dict[str, Any]] = None) -> int:
        return len(self.find(collection_name, query))

    def delete_many(self, collection_name: str, query: Dict[str, Any]) -> int:
        count = 0
        records = self._local_cache.get(collection_name, [])
        new_records = []
        for doc in records:
            match = all(doc.get(k) == v for k, v in query.items())
            if match:
                count += 1
            else:
                new_records.append(doc)
        self._local_cache[collection_name] = new_records
        self._save_local_data(collection_name)

        if self.is_connected and self.db is not None:
            try:
                res = self.db[collection_name].delete_many(query)
                return res.deleted_count
            except Exception:
                pass
        return count

    def delete_one(self, collection_name: str, query: Dict[str, Any]) -> bool:
        """Deletes one matching document from MongoDB and the local fallback."""
        deleted = False
        records = self._local_cache.get(collection_name, [])
        for index, document in enumerate(records):
            if all(document.get(key) == value for key, value in query.items()):
                del records[index]
                deleted = True
                self._save_local_data(collection_name)
                break

        if self.is_connected and self.db is not None:
            try:
                result = self.db[collection_name].delete_one(query)
                return result.deleted_count > 0
            except Exception as err:
                logger.warning("MongoDB delete error for %s: %s", collection_name, err)
        return deleted


# Global database instance
db_manager = DatabaseManager()
