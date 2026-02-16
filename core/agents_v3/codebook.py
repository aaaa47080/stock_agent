"""
Codebook System for Agent V3

Stores successful query-plan mappings to allow the agent to "learn" from past interactions.
"""
import json
import os
import difflib
from typing import List, Dict, Optional, Any
from datetime import datetime

class Codebook:
    def __init__(self, storage_path: str = "data/codebook_v3.json"):
        self.storage_path = storage_path
        self.entries = []
        self._load()

    def _load(self):
        """Load codebook from disk."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.entries = json.load(f)
            except Exception as e:
                print(f"Error loading codebook: {e}")
                self.entries = []
        else:
            self.entries = []

    def _save(self):
        """Save codebook to disk."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.entries, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving codebook: {e}")

    def find_similar(self, query: str, intent: str = None, threshold: float = 0.6) -> Optional[Dict[str, Any]]:
        """
        Find a similar past query.
        Returns the best matching entry if similarity > threshold.
        If intent is provided, only matches entries with the same intent.
        """
        if not self.entries:
            return None

        # Simple similarity based on sequence matching ratio
        best_ratio = 0.0
        best_entry = None

        # Normalize query
        query_norm = query.lower().strip()

        for entry in self.entries:
            # Intent filtering
            if intent and entry.get('intent') and entry.get('intent') != intent:
                continue

            entry_query_norm = entry['query'].lower().strip()
            ratio = difflib.SequenceMatcher(None, query_norm, entry_query_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_entry = entry

        if best_ratio >= threshold:
            # Return a copy to avoid mutation
            return best_entry.copy()

        return None

    def add_entry(self, query: str, plan: List[Dict[str, Any]], reasoning: str = "", intent: str = None):
        """
        Add a new successful query-plan pair or update existing one.
        """
        # Check if already exists (exact match)
        for entry in self.entries:
            if entry['query'] == query:
                entry['plan'] = plan
                entry['reasoning'] = reasoning
                entry['intent'] = intent
                entry['timestamp'] = datetime.now().isoformat()
                entry['usage_count'] += 1
                self._save()
                return

        # New entry
        entry = {
            "query": query,
            "plan": plan,
            "reasoning": reasoning,
            "intent": intent,
            "timestamp": datetime.now().isoformat(),
            "usage_count": 1
        }
        self.entries.append(entry)
        self._save()

    def get_all_patterns(self) -> List[Dict[str, Any]]:
        """Return all stored patterns."""
        return self.entries
