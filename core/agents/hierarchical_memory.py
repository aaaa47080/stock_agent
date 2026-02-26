"""
Hierarchical Memory Module.

Implements a knowledge base structured as:
    Intent -> Topic -> Item

Supports:
- FileSystem: `data/memory/{intent}/{topic}/{id}.json`
- Postgres: Table `codebook_v4` (JSONB)
"""
import os
import json
import difflib
from glob import glob
from uuid import uuid4
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict
from datetime import datetime
from abc import ABC, abstractmethod

try:
    import psycopg2
    from psycopg2.extras import DictCursor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

from .models import ExecutionContext, SubTask


@dataclass
class MemoryEntry:
    id: str
    query: str
    intent: str
    topics: List[str]
    plan: List[dict]
    complexity: str
    created_at: str
    ttl_days: int
    use_count: int = 0
    fail_count: int = 0
    replaced_by: Optional[str] = None
    correction_reason: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        try:
            return (datetime.now() - datetime.fromisoformat(self.created_at)).days > self.ttl_days
        except Exception:
            return False

    @property
    def is_unreliable(self) -> bool:
        if self.use_count < 3:
            return False
        return (self.fail_count / self.use_count) > 0.5


class BaseHierarchicalCodebook(ABC):
    def __init__(self):
        self._cache: Dict[str, MemoryEntry] = {}
        self._index: Dict[str, Dict[str, List[str]]] = {}  # {intent: {topic: [ids]}}
        self._load_entries()
        self._build_index()

    @abstractmethod
    def _load_entries(self):
        """Load all active entries into self._cache."""
        pass

    @abstractmethod
    def _persist_entry(self, entry: MemoryEntry, primary_topic: str):
        """Persist a single entry to storage."""
        pass

    def _build_index(self):
        """Build in-memory hierarchical index from _cache."""
        self._index = {}
        for entry in self._cache.values():
            if entry.intent not in self._index:
                self._index[entry.intent] = {}
            
            for topic in entry.topics:
                topic_norm = topic.upper()
                if topic_norm not in self._index[entry.intent]:
                    self._index[entry.intent][topic_norm] = []
                self._index[entry.intent][topic_norm].append(entry.id)



    def _is_invalid(self, entry: MemoryEntry) -> bool:
        return entry.is_expired or entry.is_unreliable or entry.replaced_by is not None

    def find_similar_entries(self, query: str, intent: str, topics: List[str], limit: int = 3) -> List[MemoryEntry]:
        """Retrieve top k similar entries."""
        if intent not in self._index:
            return []
        
        candidate_ids = set()
        topics_to_check = [t.upper() for t in topics] + ["DEFAULT"]
        
        for topic in topics_to_check:
            if topic in self._index[intent]:
                candidate_ids.update(self._index[intent][topic])
        
        if not candidate_ids:
            return []
            
        candidates = [self._cache[cid] for cid in candidate_ids 
                      if cid in self._cache and not self._is_invalid(self._cache[cid])]
        
        if not candidates:
            return []

        return self._find_top_k_similar(query, candidates, limit)

    def _find_top_k_similar(self, query: str, candidates: List[MemoryEntry], k: int) -> List[MemoryEntry]:
        query_norm = query.lower().strip()
        scored = []
        for e in candidates:
            ratio = difflib.SequenceMatcher(None, query_norm, e.query.lower().strip()).ratio()
            if ratio > 0.5: # Lower threshold for candidates
                scored.append((ratio, e))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:k]]

    def save(self, context: ExecutionContext) -> str:
        plan_data = []
        for task in context.plan:
            task_copy = asdict(task)
            task_copy["result"] = None
            plan_data.append(task_copy)

        primary_topic = context.topics[0].upper() if context.topics else "DEFAULT"
        
        entry = MemoryEntry(
            id=str(uuid4()),
            query=context.original_query,
            intent=context.intent,
            topics=context.topics,
            plan=plan_data,
            complexity=context.complexity.value,
            created_at=datetime.now().isoformat(),
            ttl_days=14,
        )
        
        self._persist_entry(entry, primary_topic)
        self._cache[entry.id] = entry
        self._update_index(entry)
        return entry.id

    def _update_index(self, entry: MemoryEntry):
        if entry.intent not in self._index:
            self._index[entry.intent] = {}
        for topic in entry.topics:
            topic_norm = topic.upper()
            if topic_norm not in self._index[entry.intent]:
                self._index[entry.intent][topic_norm] = []
            if entry.id not in self._index[entry.intent][topic_norm]:
                self._index[entry.intent][topic_norm].append(entry.id)

    def record_feedback(self, entry_id: str, satisfied: bool, reason: str = "") -> None:
        if entry_id not in self._cache:
            return
        entry = self._cache[entry_id]
        entry.use_count += 1
        if not satisfied:
            entry.fail_count += 1
            if entry.is_unreliable:
                entry.ttl_days = 0
        
        primary_topic = entry.topics[0].upper() if entry.topics else "DEFAULT"
        self._persist_entry(entry, primary_topic)

    def stats(self) -> dict:
        return {
            "total_entries": len(self._cache),
            "intents": list(self._index.keys())
        }


class FileSystemCodebook(BaseHierarchicalCodebook):
    def __init__(self, base_path: str = "data/memory"):
        self.base_path = base_path
        super().__init__()

    def _load_entries(self):
        pattern = os.path.join(self.base_path, "*", "*", "*.json")
        for filepath in glob(pattern):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Compat
                    if "symbols" in data and "topics" not in data:
                        data["topics"] = data.pop("symbols")
                    entry = MemoryEntry(**data)
                    self._cache[entry.id] = entry
            except Exception as e:
                print(f"[Memory] Failed to load {filepath}: {e}")

    def _persist_entry(self, entry: MemoryEntry, primary_topic: str):
        dir_path = os.path.join(self.base_path, entry.intent, primary_topic)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, f"{entry.id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(asdict(entry), f, ensure_ascii=False, indent=2)


class PostgresCodebook(BaseHierarchicalCodebook):
    def __init__(self, db_url: str):
        if not HAS_POSTGRES:
            raise ImportError("psycopg not installed")
        self.db_url = db_url
        self._ensure_table()
        super().__init__()

    def _get_conn(self):
        return psycopg2.connect(self.db_url)

    def _ensure_table(self):
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_codebook (
                    id TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE
                );
                """)
                
                # Auto-Migration: Ensure 'data' column exists (for old schema compatibility)
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'agent_codebook' AND column_name = 'data'")
                if not cur.fetchone():
                    print("[Codebook] Migrating schema: Adding 'data' column...")
                    cur.execute("ALTER TABLE agent_codebook ADD COLUMN data JSONB DEFAULT '{}'::jsonb")
                
                # Auto-Migration: Ensure 'is_active' column exists
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'agent_codebook' AND column_name = 'is_active'")
                if not cur.fetchone():
                    print("[Codebook] Migrating schema: Adding 'is_active' column...")
                    cur.execute("ALTER TABLE agent_codebook ADD COLUMN is_active BOOLEAN DEFAULT TRUE")

            conn.commit()

    def _load_entries(self):
        try:
            with self._get_conn() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT data FROM agent_codebook WHERE is_active = TRUE")
                    rows = cur.fetchall()
                    for row in rows:
                        data = row["data"]
                        # Compat
                        if "symbols" in data and "topics" not in data:
                            data["topics"] = data.pop("symbols")
                        entry = MemoryEntry(**data)
                        self._cache[entry.id] = entry
            print(f"[Codebook] Loaded {len(self._cache)} entries from Postgres (agent_codebook) ✅")
        except Exception as e:
            print(f"[Codebook] Postgres load error: {e}")

    def _persist_entry(self, entry: MemoryEntry, primary_topic: str):
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO agent_codebook (id, data, is_active) VALUES (%s, %s, %s) "
                    "ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, is_active = EXCLUDED.is_active",
                    (entry.id, json.dumps(asdict(entry), default=str), entry.ttl_days > 0)
                )
            conn.commit()


def CodebookFactory(base_path: str = "data/memory") -> BaseHierarchicalCodebook:
    db_url = os.environ.get("DATABASE_URL")
    if db_url and HAS_POSTGRES:
        print("[Codebook] Using PostgresCodebook ✅")
        try:
            return PostgresCodebook(db_url)
        except Exception as e:
            print(f"[Codebook] Connection failed, falling back to FileSystem: {e}")
            
    print("[Codebook] Using FileSystemCodebook (JSON) ⚠️")
    return FileSystemCodebook(base_path)
