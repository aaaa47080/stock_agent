"""
Agent V4 — Codebook

Self-correcting knowledge base with TTL, 3-layer matching,
and correction tracking.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from datetime import datetime
from uuid import uuid4
import json
import os
import difflib
try:
    import psycopg
    from psycopg.rows import dict_row
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

# TTL by agent name (intent field now stores agent name)


# TTL by agent name (intent field now stores agent name)
DEFAULT_TTL = 14
TTL_BY_INTENT = {"news": 3, "technical": 14, "chat": 90}


@dataclass
class CodebookEntry:
    id: str
    query: str
    intent: str
    symbols: List[str]
    plan: List[dict]
    complexity: str
    created_at: str             # ISO datetime string
    ttl_days: int
    use_count: int = 0
    fail_count: int = 0
    replaced_by: Optional[str] = None       # id of correction entry
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


class BaseCodebook:
    """Base interface for Codebook storage."""
    def find_match(self, query: str, intent: str, symbols: List[str]) -> Optional[CodebookEntry]:
        raise NotImplementedError
    def save(self, context) -> str:
        raise NotImplementedError
    def record_feedback(self, entry_id: str, satisfied: bool, reason: str = "") -> None:
        raise NotImplementedError
    def save_correction(self, original_entry_id: str, context, correction_reason: str) -> str:
        raise NotImplementedError

class FileCodebook(BaseCodebook):
    def __init__(self, storage_path: str = "data/codebook_v4.json"):
        self._storage_path = storage_path
        self._entries: Dict[str, CodebookEntry] = {}
        self._load()

    # ── Persistence ──

    def _load(self) -> None:
        if not os.path.exists(self._storage_path):
            return
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for item in raw:
                entry = CodebookEntry(**item)
                self._entries[entry.id] = entry
        except Exception as e:
            print(f"[Codebook] load error: {e}")

    def _persist(self) -> None:
        os.makedirs(os.path.dirname(self._storage_path) or ".", exist_ok=True)
        data = [asdict(e) for e in self._entries.values()]
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── 3-Layer Matching ──

    def find_match(self, query: str, intent: str, symbols: List[str]) -> Optional[CodebookEntry]:
        candidates = [
            e for e in self._entries.values()
            if not e.is_expired
            and not e.is_unreliable
            and e.replaced_by is None          # skip superseded
            and e.intent == intent             # Layer 1: intent exact
            and self._symbols_overlap(e.symbols, symbols)  # Layer 2: symbols
        ]
        return self._find_most_similar(query, candidates, threshold=0.85)  # Layer 3: difflib

    def _symbols_overlap(self, entry_symbols: List[str], query_symbols: List[str]) -> bool:
        if not entry_symbols or not query_symbols:
            return True  # if either is empty, skip symbol filter
        return bool(set(s.upper() for s in entry_symbols) & set(s.upper() for s in query_symbols))

    def _find_most_similar(self, query: str, candidates: List[CodebookEntry], threshold: float) -> Optional[CodebookEntry]:
        query_norm = query.lower().strip()
        best_ratio, best_entry = 0.0, None
        for e in candidates:
            ratio = difflib.SequenceMatcher(None, query_norm, e.query.lower().strip()).ratio()
            if ratio > best_ratio:
                best_ratio, best_entry = ratio, e
        return best_entry if best_ratio >= threshold else None

    # ── Save & Feedback ──

    def save(self, context) -> str:
        """Save execution context as a new codebook entry."""
        # Set result to None before asdict to avoid serializing large results
        plan_data = []
        for task in context.plan:
            task_copy = asdict(task)
            task_copy["result"] = None
            plan_data.append(task_copy)

        entry = CodebookEntry(
            id=str(uuid4()),
            query=context.original_query,
            intent=context.intent,
            symbols=context.symbols,
            plan=plan_data,
            complexity=context.complexity.value,
            created_at=datetime.now().isoformat(),
            ttl_days=TTL_BY_INTENT.get(context.intent, 14),
        )
        self._entries[entry.id] = entry
        self._persist()
        return entry.id

    def record_feedback(self, entry_id: str, satisfied: bool, reason: str = "") -> None:
        entry = self._entries.get(entry_id)
        if not entry:
            return
        entry.use_count += 1
        if not satisfied:
            entry.fail_count += 1
            if entry.is_unreliable:
                entry.ttl_days = 0   # force expiry
        self._persist()

    def save_correction(self, original_entry_id: str, context, correction_reason: str) -> str:
        """Save corrected plan, retire original entry."""
        plan_data = []
        for task in context.plan:
            task_copy = asdict(task)
            task_copy["result"] = None
            plan_data.append(task_copy)

        new_entry = CodebookEntry(
            id=str(uuid4()),
            query=context.original_query,
            intent=context.intent,
            symbols=context.symbols,
            plan=plan_data,
            complexity=context.complexity.value,
            created_at=datetime.now().isoformat(),
            ttl_days=TTL_BY_INTENT.get(context.intent, 14),
            correction_reason=correction_reason,
        )
        self._entries[new_entry.id] = new_entry

        original = self._entries.get(original_entry_id)
        if original:
            original.replaced_by = new_entry.id
            original.ttl_days = 0    # retire immediately

        self._persist()
        return new_entry.id

    def stats(self) -> dict:
        total = len(self._entries)
        active = sum(1 for e in self._entries.values()
                     if not e.is_expired and e.replaced_by is None)
        return {"total": total, "active": active}


class PostgresCodebook(FileCodebook):
    """Postgres-backed Codebook. Inherits FileCodebook for in-memory matching logic."""
    def __init__(self, db_url: str):
        if not HAS_POSTGRES:
            raise ImportError("psycopg2-binary not installed. Please install it to use PostgresCodebook.")
        self.db_url = db_url
        self._entries: Dict[str, CodebookEntry] = {}
        self._ensure_table()
        self._load()

    def _get_conn(self):
        return psycopg.connect(self.db_url, row_factory=dict_row)

    def _ensure_table(self):
        with self._get_conn() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS codebook_v4 (
                id TEXT PRIMARY KEY,
                data JSONB NOT NULL,
                is_active BOOLEAN DEFAULT TRUE
            );
            """)
            conn.commit()

    def _load(self) -> None:
        try:
            with self._get_conn() as conn:
                rows = conn.execute("SELECT data FROM codebook_v4 WHERE is_active = TRUE").fetchall()
                for row in rows:
                    entry = CodebookEntry(**row["data"])
                    self._entries[entry.id] = entry
            print(f"[Codebook] Loaded {len(self._entries)} entries from Postgres ✅")
        except Exception as e:
            print(f"[Codebook] Postgres load error: {e}")

    def _persist(self) -> None:
        """Persist all entries to DB (upsert)."""
        # In a real system, we might optimize to only save changed entries.
        # Here we just save everything for simplicity, or we can rely on save() / record_feedback() calling _persist_entry
        pass # We override save/update methods to write directly

    def _persist_entry(self, entry: CodebookEntry):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO codebook_v4 (id, data, is_active) VALUES (%s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, is_active = EXCLUDED.is_active",
                (entry.id, json.dumps(asdict(entry), default=str), entry.ttl_days > 0)
            )
            conn.commit()

    def save(self, context) -> str:
        entry_id = super().save(context) # updates in-memory _entries
        self._persist_entry(self._entries[entry_id])
        return entry_id

    def record_feedback(self, entry_id: str, satisfied: bool, reason: str = "") -> None:
        super().record_feedback(entry_id, satisfied, reason) # updates in-memory
        if entry_id in self._entries:
            self._persist_entry(self._entries[entry_id])

    def save_correction(self, original_entry_id: str, context, correction_reason: str) -> str:
        new_id = super().save_correction(original_entry_id, context, correction_reason)
        if original_entry_id in self._entries:
            self._persist_entry(self._entries[original_entry_id]) # update original (retired)
        self._persist_entry(self._entries[new_id]) # save new
        return new_id


def Codebook(storage_path: str = "data/codebook_v4.json") -> BaseCodebook:
    """Factory: returns PostgresCodebook if DATABASE_URL present, else FileCodebook."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url and HAS_POSTGRES:
        print("[Codebook] Using PostgresCodebook ✅")
        return PostgresCodebook(db_url)
    print("[Codebook] Using FileCodebook (JSON) ⚠️")
    return FileCodebook(storage_path)
