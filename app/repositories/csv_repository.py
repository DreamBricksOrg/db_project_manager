"""CSV Repository - Generic CRUD operations for CSV files"""

import csv
import json
from pathlib import Path
from typing import Any
from flask import current_app

from app.models import generate_id


class CSVRepository:
    def __init__(self, filename: str, fieldnames: list[str]):
        self.filename = filename
        self.fieldnames = fieldnames

    @property
    def filepath(self) -> Path:
        return current_app.config['DATA_DIR'] / self.filename

    def _ensure_file(self):
        if not self.filepath.exists():
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()

    def get_all(self) -> list[dict]:
        self._ensure_file()
        with open(self.filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            # Parse JSON fields
            for row in rows:
                for key, value in row.items():
                    if value.startswith('[') or value.startswith('{'):
                        try:
                            row[key] = json.loads(value)
                        except json.JSONDecodeError:
                            pass
            return rows

    def get_by_id(self, id: str) -> dict | None:
        for item in self.get_all():
            if item.get('id') == id:
                return item
        return None

    def create(self, data: dict) -> dict:
        self._ensure_file()
        if 'id' not in data or not data['id']:
            data['id'] = generate_id()
        
        # Serialize lists/dicts to JSON
        row = {}
        for key in self.fieldnames:
            value = data.get(key, '')
            if isinstance(value, (list, dict)):
                row[key] = json.dumps(value, ensure_ascii=False)
            else:
                row[key] = value

        with open(self.filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writerow(row)
        
        return data

    def update(self, id: str, data: dict) -> dict | None:
        items = self.get_all()
        updated = False
        
        for i, item in enumerate(items):
            if item.get('id') == id:
                items[i] = {**item, **data, 'id': id}
                updated = True
                break
        
        if not updated:
            return None

        # Rewrite file
        with open(self.filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writeheader()
            for item in items:
                row = {}
                for key in self.fieldnames:
                    value = item.get(key, '')
                    if isinstance(value, (list, dict)):
                        row[key] = json.dumps(value, ensure_ascii=False)
                    else:
                        row[key] = value
                writer.writerow(row)
        
        return items[i]

    def delete(self, id: str) -> bool:
        items = self.get_all()
        original_len = len(items)
        items = [item for item in items if item.get('id') != id]
        
        if len(items) == original_len:
            return False

        with open(self.filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writeheader()
            for item in items:
                row = {}
                for key in self.fieldnames:
                    value = item.get(key, '')
                    if isinstance(value, (list, dict)):
                        row[key] = json.dumps(value, ensure_ascii=False)
                    else:
                        row[key] = value
                writer.writerow(row)
        
        return True

    def search(self, field: str, query: str, limit: int = 10) -> list[dict]:
        """Search for items where field contains query (case-insensitive)"""
        if not query:
            return []
        
        query = query.lower()
        results = []
        
        for item in self.get_all():
            value = str(item.get(field, '')).lower()
            if query in value:
                results.append(item)
                if len(results) >= limit:
                    break
        
        return results

    def get_unique_values(self, field: str) -> list[str]:
        """Get all unique values for a field (useful for autocomplete)"""
        values = set()
        for item in self.get_all():
            value = item.get(field, '')
            if value:
                if isinstance(value, list):
                    values.update(value)
                else:
                    values.add(value)
        return sorted(values)
