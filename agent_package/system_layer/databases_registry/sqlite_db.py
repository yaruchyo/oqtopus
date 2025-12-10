import json
import os
import sqlite3
import uuid
from typing import Any, Dict, List, Optional


class SQLiteDB:
    """
    A SQLite adapter that mimics the MongoDB interface used in this project.
    Stores documents as JSON in a generic structure.
    """

    def __init__(self, db_path: str = "local_orchestrator.db"):
        self.db_path = db_path
        self._init_connection()

    def _init_connection(self):
        """Initialize the connection and ensure it's valid."""
        # Check if we can connect
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")

    def _get_conn(self):
        """Get a new connection. Recommended to not share connections across threads if using Flask."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self, collection_name: str):
        """Ensure a table exists for the given 'collection'."""
        # Sanitize collection name to prevent SQL injection (simple alphanumeric check)
        if not collection_name.replace("_", "").isalnum():
            raise ValueError(f"Invalid collection name: {collection_name}")

        with self._get_conn() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {collection_name} (
                    id TEXT PRIMARY KEY,
                    data JSON
                )
            """
            )
            conn.commit()

    def insert_document(self, collection_name: str, document: dict):
        """
        Inserts a single document.
        Mimics: mongodb.insert_document(collection, doc) -> inserted_id
        """
        self._ensure_table(collection_name)

        # Generate an ID if not present (MongoDB usually does this)
        if "_id" not in document:
            document["_id"] = str(uuid.uuid4())

        doc_id = document["_id"]
        # Also ensure the ID in the dict matches what we will use as PK

        with self._get_conn() as conn:
            conn.execute(
                f"INSERT INTO {collection_name} (id, data) VALUES (?, ?)",
                (doc_id, json.dumps(document)),
            )
            conn.commit()

        return doc_id

    def insert_many_documents(self, collection_name: str, documents: list):
        """
        Inserts multiple documents.
        Mimics: mongodb.insert_many_documents(collection, docs) -> list of ids
        """
        self._ensure_table(collection_name)
        inserted_ids = []

        with self._get_conn() as conn:
            for doc in documents:
                if "_id" not in doc:
                    doc["_id"] = str(uuid.uuid4())
                inserted_ids.append(doc["_id"])
                conn.execute(
                    f"INSERT INTO {collection_name} (id, data) VALUES (?, ?)",
                    (doc["_id"], json.dumps(doc)),
                )
            conn.commit()

        return inserted_ids

    def _build_where_clause(self, query: dict) -> (str, list):
        """
        Constructs a simplistic WHERE clause for JSON data.
        Only supports simple key-value equality matches for now.
        """
        if not query:
            return "1=1", []

        conditions = []
        params = []
        for key, value in query.items():
            if key == "_id":
                conditions.append("id = ?")
                params.append(value)
            else:
                # Use json_extract to get the value
                # Note: This is sensitive to types (strings usually need quotes in JSON path, but here we extract value)
                conditions.append(f"json_extract(data, '$.{key}') = ?")
                params.append(value)

        return " AND ".join(conditions), params

    def find_document(self, collection_name: str, query: dict):
        """
        Finds a single document.
        Mimics: mongodb.find_document(collection, query) -> dict or None
        """
        self._ensure_table(collection_name)
        where_clause, params = self._build_where_clause(query)

        with self._get_conn() as conn:
            cursor = conn.execute(
                f"SELECT data FROM {collection_name} WHERE {where_clause} LIMIT 1",
                params,
            )
            row = cursor.fetchone()

            if row:
                return json.loads(row[0])
            return None

    def find_documents(self, collection_name: str, query: dict, limit: int = 0):
        """
        Finds multiple documents.
        Mimics: mongodb.find_documents(collection, query, limit) -> list[dict]
        """
        self._ensure_table(collection_name)
        where_clause, params = self._build_where_clause(query)

        sql = f"SELECT data FROM {collection_name} WHERE {where_clause}"
        if limit > 0:
            sql += f" LIMIT {limit}"

        with self._get_conn() as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            return [json.loads(row[0]) for row in rows]

    def update_document(self, collection_name: str, query: dict, update_data: dict):
        """
        Updates a single document.
        Mimics: mongodb.update_document(collection, query, update_data) -> modified_count

        Note: The MongoDB implementation does an update_one.
        SQLite JSON update is tricky. We'll read, update in python, write back.
        This is not atomic in the same way, but suffices for local dev.
        """
        self._ensure_table(collection_name)

        # 1. Find the document
        doc = self.find_document(collection_name, query)
        if not doc:
            return 0

        # 2. Update the dict
        # verify if update_data has $set (standard mongo) or is just the data
        # The existing code in mongo_db.py passes the update_data directly to $set
        # result = self.db[collection_name].update_one(query, {'$set': update_data})
        # So update_data is the dict of fields to change.

        doc.update(update_data)

        # 3. Write back
        # We need the ID to update the specific row
        doc_id = doc.get("_id")
        if not doc_id:
            # Should not happen given insert implementation, but fallback
            return 0

        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE {collection_name} SET data = ? WHERE id = ?",
                (json.dumps(doc), doc_id),
            )
            conn.commit()

        return 1

    def delete_document(self, collection_name: str, query: dict):
        """
        Delete a single document.
        Mimics: mongodb.delete_document(collection, query) -> deleted_count
        """
        self._ensure_table(collection_name)

        # We need to find the ID first to ensure we only delete one?
        # Or just delete match. existing implementation uses delete_one

        # To strictly follow delete_one, we should find one first.
        doc = self.find_document(collection_name, query)
        if not doc:
            return 0

        doc_id = doc["_id"]
        with self._get_conn() as conn:
            conn.execute(f"DELETE FROM {collection_name} WHERE id = ?", (doc_id,))
            conn.commit()
        return 1

    def delete_documents(self, collection_name: str, query: dict):
        """
        Delete multiple documents.
        Mimics: mongodb.delete_documents(collection, query) -> deleted_count
        """
        self._ensure_table(collection_name)
        where_clause, params = self._build_where_clause(query)

        with self._get_conn() as conn:
            # First count for return value (simplistic)
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {collection_name} WHERE {where_clause}", params
            )
            count = cursor.fetchone()[0]

            if count > 0:
                conn.execute(
                    f"DELETE FROM {collection_name} WHERE {where_clause}", params
                )
                conn.commit()

            return count

    # Other validation methods not strictly needed for basic flow but kept for compatibility if called
    def count_documents(self, collection_name: str, query: dict = {}):
        self._ensure_table(collection_name)
        where_clause, params = self._build_where_clause(query)
        with self._get_conn() as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {collection_name} WHERE {where_clause}", params
            )
            return cursor.fetchone()[0]
