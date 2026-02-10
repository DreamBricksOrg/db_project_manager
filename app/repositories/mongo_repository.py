from typing import Any, List, Optional
from app.database import get_db
from app.models.entities import generate_id

class MongoRepository:
    def __init__(self, collection_name: str, fieldnames: List[str] = None):
        self.collection_name = collection_name
        self.fieldnames = fieldnames  # Kept for compatibility, not strictly used

    @property
    def collection(self):
        return get_db()[self.collection_name]

    def get_all(self) -> List[dict]:
        """Get all documents from the collection"""
        # Exclude internal _id from results to match CSV behavior
        # But we need to be careful: if we exclude _id, we rely on 'id' field being present.
        return list(self.collection.find({}, {'_id': 0}))

    def get_by_id(self, id: str) -> Optional[dict]:
        """Get a document by its ID"""
        return self.collection.find_one({'id': id}, {'_id': 0})

    def create(self, data: dict) -> dict:
        """Create a new document"""
        if 'id' not in data or not data['id']:
            data['id'] = generate_id()
        
        # Insert a copy to avoid mutating the original data with _id if we wanted to return it
        # insert_one modifies the dict to add _id
        insert_data = data.copy()
        insert_data['_id'] = insert_data['id']  # Use custom ID as MongoDB _id
        self.collection.insert_one(insert_data)
        return data

    def update(self, id: str, data: dict) -> Optional[dict]:
        """Update a document by its ID"""
        # $set will only update specified fields
        result = self.collection.update_one({'id': id}, {'$set': data})
        
        # Return the updated document
        return self.get_by_id(id)

    def delete(self, id: str) -> bool:
        """Delete a document by its ID"""
        result = self.collection.delete_one({'id': id})
        return result.deleted_count > 0

    def search(self, field: str, query: str, limit: int = 10) -> List[dict]:
        """Search for documents where field matches query (case-insensitive)"""
        if not query:
            return []
        
        # Case-insensitive search using regex
        # Note: This might be slow on large datasets without text index
        regex = {'$regex': query, '$options': 'i'}
        cursor = self.collection.find({field: regex}, {'_id': 0}).limit(limit)
        return list(cursor)

    def get_unique_values(self, field: str) -> List[str]:
        """Get all unique values for a field"""
        # distinct() returns a list of unique values
        values = self.collection.distinct(field)
        # Filter out None/Empty and sort
        return sorted([v for v in values if v])

