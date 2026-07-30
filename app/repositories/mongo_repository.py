import re
from typing import Any, List, Optional

from app.database import get_db
from app.models.entities import generate_id

# Documents are returned without Mongo's internal _id; callers rely on 'id'.
_NO_INTERNAL_ID = {'_id': 0}


class MongoRepository:
    def __init__(self, collection_name: str, fieldnames: List[str] = None):
        self.collection_name = collection_name
        self.fieldnames = fieldnames  # Kept for compatibility, not strictly used

    @property
    def collection(self):
        return get_db()[self.collection_name]

    def get_all(self) -> List[dict]:
        """Get all documents from the collection.

        Prefer :meth:`find` for anything user-facing — this loads the entire
        collection into memory.
        """
        return list(self.collection.find({}, _NO_INTERNAL_ID))

    def get_by_id(self, id: str) -> Optional[dict]:
        """Get a document by its ID"""
        return self.collection.find_one({'id': id}, _NO_INTERNAL_ID)

    def find_one_by(self, field: str, value: Any) -> Optional[dict]:
        """Get the first document whose ``field`` equals ``value``."""
        return self.collection.find_one({field: value}, _NO_INTERNAL_ID)

    def find(
        self,
        filters: Optional[dict] = None,
        sort: Optional[List[tuple]] = None,
        skip: int = 0,
        limit: int = 0,
    ) -> List[dict]:
        """Query the collection, letting MongoDB do the filtering and sorting."""
        cursor = self.collection.find(filters or {}, _NO_INTERNAL_ID)
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def count(self, filters: Optional[dict] = None) -> int:
        """Count documents matching ``filters`` without loading them."""
        return self.collection.count_documents(filters or {})

    def create(self, data: dict) -> dict:
        """Create a new document"""
        if 'id' not in data or not data['id']:
            data['id'] = generate_id()

        # Insert a copy so the caller's dict is not mutated with _id.
        insert_data = data.copy()
        insert_data['_id'] = insert_data['id']  # Use custom ID as MongoDB _id
        self.collection.insert_one(insert_data)
        return data

    def update(self, id: str, data: dict) -> Optional[dict]:
        """Update a document by its ID"""
        # Callers often pass the whole document back; never let the payload
        # rewrite the immutable key fields.
        payload = {k: v for k, v in data.items() if k not in ('_id', 'id')}
        if payload:
            self.collection.update_one({'id': id}, {'$set': payload})
        return self.get_by_id(id)

    def delete(self, id: str) -> bool:
        """Delete a document by its ID"""
        result = self.collection.delete_one({'id': id})
        return result.deleted_count > 0

    def search(self, field: str, query: str, limit: int = 10) -> List[dict]:
        """Search for documents where field matches query (case-insensitive).

        The query is escaped before it reaches the regex engine: raw user input
        inside ``$regex`` lets a caller inject a catastrophically backtracking
        pattern and stall the server.
        """
        if not query:
            return []

        regex = {'$regex': re.escape(query), '$options': 'i'}
        cursor = self.collection.find({field: regex}, _NO_INTERNAL_ID).limit(limit)
        return list(cursor)

    def get_by_project(self, project_id: str) -> List[dict]:
        """Get all documents for a given project_id"""
        return list(self.collection.find({'project_id': project_id}, _NO_INTERNAL_ID))

    def get_unique_values(self, field: str) -> List[str]:
        """Get all unique values for a field"""
        values = self.collection.distinct(field)
        return sorted([v for v in values if v])
