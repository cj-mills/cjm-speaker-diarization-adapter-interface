"""Standardized SQLite storage for speaker-diarization results with content hashing.

Cache shape follows the VAD-adapter precedent: content-addressed rows upserted
by (file_path, config_hash) with file_hash for content-correctness. Landed
2026-07-26 — full-source diarization (~46s/hour on cuda, multi-hour sources)
made re-runs worth caching, unlike the pysbd-precedent no-cache assessment
this pair was born under."""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from cjm_substrate.core.journal_store import SubstrateEventType
from cjm_substrate.core.wire import record_account
from cjm_substrate.utils.hashing import hash_file


# CR-14 follow-up: storage events are substrate-family accounts. The helpers
# below RECORD them (no-op outside a worker call span); the host journals
# them off the response header with worker_reported=True.


@dataclass
class SpeakerDiarizationRow:
    """A single row from the speaker_diarization_results table."""
    file_path: str       # Path to the analyzed (decoded PCM rendition) audio file
    file_hash: str       # Hash of the analyzed file in "algo:hexdigest" format
    config_hash: str     # Hash of the diarization config (tool config + speaker-count hints)
    turns: Optional[List[Dict[str, Any]]] = None  # Diarized speech turns (serialized SpeakerTurns)
    metadata: Optional[Dict[str, Any]] = None      # Diarization metadata
    created_at: Optional[float] = None             # Unix timestamp


class SpeakerDiarizationStorage:
    """Standardized SQLite storage for speaker-diarization results."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS speaker_diarization_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            turns JSON,
            metadata JSON,
            created_at REAL NOT NULL,
            UNIQUE(file_path, config_hash)
        )
    """

    INDEX = "CREATE INDEX IF NOT EXISTS idx_speaker_diarization_file_path ON speaker_diarization_results(file_path);"

    def __init__(
        self,
        db_path: str  # Absolute path to the SQLite database file
    ):
        """Initialize storage and create table if needed."""
        self.db_path = db_path
        with sqlite3.connect(self.db_path) as con:
            con.execute(self.SCHEMA)
            con.execute(self.INDEX)

    def save(
        self,
        file_path: str,     # Path to the analyzed audio file
        file_hash: str,     # Hash of the analyzed file in "algo:hexdigest" format
        config_hash: str,   # Hash of the diarization config (tool config + hints)
        turns: Optional[List[Dict[str, Any]]] = None,  # Diarized speech turns
        metadata: Optional[Dict[str, Any]] = None       # Diarization metadata
    ) -> None:
        """Save or replace a diarization result (upsert by file_path + config_hash)."""
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                """INSERT OR REPLACE INTO speaker_diarization_results
                   (file_path, file_hash, config_hash, turns, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    file_path,
                    file_hash,
                    config_hash,
                    json.dumps(turns) if turns else None,
                    json.dumps(metadata) if metadata else None,
                    time.time()
                )
            )

    def save_with_logging(
        self,
        *,
        file_path: str,     # Path to the analyzed audio file
        file_hash: str,     # Hash of the analyzed file in "algo:hexdigest" format
        config_hash: str,   # Hash of the diarization config (tool config + hints)
        turns: Optional[List[Dict[str, Any]]] = None,  # Diarized speech turns
        metadata: Optional[Dict[str, Any]] = None,      # Diarization metadata
        logger: Optional[logging.Logger] = None          # Optional logger for success/failure messages
    ) -> bool:  # True if saved; False if the save failed (error logged, not raised)
        """Save a result, logging success/failure. Failures are logged and swallowed (returns False).

        CR-14 follow-up: records a RESULT_SAVED account either way (ok flag +
        file/config references — the journal never carries content) so saves AND
        swallowed save-failures become auditable journal rows."""
        try:
            self.save(
                file_path=file_path,
                file_hash=file_hash,
                config_hash=config_hash,
                turns=turns,
                metadata=metadata,
            )
            record_account(SubstrateEventType.RESULT_SAVED.value, {
                "ok": True, "file_path": file_path, "file_hash": file_hash,
                "config_hash": config_hash,
            })
            if logger:
                logger.info(f"Saved diarization result to DB ({file_path})")
            return True
        except Exception as e:
            record_account(SubstrateEventType.RESULT_SAVED.value, {
                "ok": False, "file_path": file_path, "file_hash": file_hash,
                "config_hash": config_hash, "error": str(e),
            })
            if logger:
                logger.error(f"Failed to save to DB: {e}")
            return False

    def get_cached(
        self,
        file_path: str,   # Path to the audio file
        file_hash: str,   # Content hash of the file (cache miss if the file changed)
        config_hash: str  # Config hash to match
    ) -> Optional[SpeakerDiarizationRow]:  # Cached row or None
        """Retrieve a content-correct cached diarization result.

        Matches on file_path + file_hash + config_hash, so a changed file (new
        file_hash) misses the cache even though a stale row may still exist at the
        same (file_path, config_hash) — the next save() replaces it.

        CR-14 follow-up: a hit records a CACHE_HIT account (the cache-serving
        decision is an account-of-action)."""
        with sqlite3.connect(self.db_path) as con:
            cur = con.execute(
                """SELECT file_path, file_hash, config_hash, turns, metadata, created_at
                   FROM speaker_diarization_results
                   WHERE file_path = ? AND file_hash = ? AND config_hash = ?""",
                (file_path, file_hash, config_hash)
            )
            row = cur.fetchone()
            if not row:
                return None
            record_account(SubstrateEventType.CACHE_HIT.value, {
                "file_path": file_path, "file_hash": file_hash,
                "config_hash": config_hash,
            })
            return SpeakerDiarizationRow(
                file_path=row[0],
                file_hash=row[1],
                config_hash=row[2],
                turns=json.loads(row[3]) if row[3] else None,
                metadata=json.loads(row[4]) if row[4] else None,
                created_at=row[5]
            )

    def list_jobs(
        self,
        limit: int = 100  # Maximum number of rows to return
    ) -> List[SpeakerDiarizationRow]:  # List of diarization rows
        """List diarization results ordered by creation time (newest first)."""
        results = []
        with sqlite3.connect(self.db_path) as con:
            cur = con.execute(
                """SELECT file_path, file_hash, config_hash, turns, metadata, created_at
                   FROM speaker_diarization_results ORDER BY created_at DESC LIMIT ?""",
                (limit,)
            )
            for row in cur:
                results.append(SpeakerDiarizationRow(
                    file_path=row[0],
                    file_hash=row[1],
                    config_hash=row[2],
                    turns=json.loads(row[3]) if row[3] else None,
                    metadata=json.loads(row[4]) if row[4] else None,
                    created_at=row[5]
                ))
        return results

    def verify_file(
        self,
        file_path: str,   # Path to the audio file
        config_hash: str  # Config hash to look up
    ) -> Optional[bool]:  # True if file matches, False if changed, None if not found
        """Verify the analyzed file still matches the hash stored for (file_path, config_hash)."""
        with sqlite3.connect(self.db_path) as con:
            cur = con.execute(
                """SELECT file_hash FROM speaker_diarization_results
                   WHERE file_path = ? AND config_hash = ?""",
                (file_path, config_hash)
            )
            row = cur.fetchone()
        if not row:
            return None
        return hash_file(file_path) == row[0]
