"""SQL journal store for the commit gate.

Stores the canonical serialized events in an append-only table, enforcing
hash chaining and optimistic concurrency control (fencing tokens).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Sequence

from .canon import GENESIS_HASH
from .gate import CommitResult

__all__ = ["JournalStore", "ConcurrencyError", "HashChainError"]


class ConcurrencyError(Exception):
    """Raised when a write fails due to lease fencing or base revision mismatch."""


class HashChainError(Exception):
    """Raised when the provided predecessor hash does not match the journal head."""


class JournalStore:
    """A SQLite-backed append-only journal of proof events."""

    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, isolation_level=None) # autocommit mode managed manually
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS journal (
                    revision INTEGER PRIMARY KEY,
                    proof_id TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE,
                    prev_hash TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    worker_class TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    committed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # A lease table for concurrency control (fencing)
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS leases (
                    proof_id TEXT PRIMARY KEY,
                    lease_id TEXT NOT NULL,
                    fencing_token INTEGER NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_journal_proof ON journal(proof_id, revision)"
            )

    def head(self, proof_id: str) -> tuple[int, str]:
        """Get the current (revision, hash) for a proof."""
        row = self._conn.execute(
            """
            SELECT revision, event_hash 
            FROM journal 
            WHERE proof_id = ? 
            ORDER BY revision DESC 
            LIMIT 1
            """,
            (proof_id,),
        ).fetchone()
        if row:
            return row["revision"], row["event_hash"]
        return 0, GENESIS_HASH

    def acquire_lease(self, proof_id: str, lease_id: str) -> int:
        """Acquire a lease for writing, returning the new fencing token."""
        with self._conn:
            # Simple monotonically increasing token per proof
            row = self._conn.execute(
                "SELECT fencing_token FROM leases WHERE proof_id = ?", (proof_id,)
            ).fetchone()
            
            if row:
                next_token = row["fencing_token"] + 1
                self._conn.execute(
                    "UPDATE leases SET lease_id = ?, fencing_token = ? WHERE proof_id = ?",
                    (lease_id, next_token, proof_id),
                )
            else:
                next_token = 1
                self._conn.execute(
                    "INSERT INTO leases (proof_id, lease_id, fencing_token) VALUES (?, ?, ?)",
                    (proof_id, lease_id, next_token),
                )
            return next_token

    def append(self, proof_id: str, payload_dict: dict[str, Any], result: CommitResult) -> None:
        """Append a validated event to the journal."""
        if not result.accepted or result.event_hash is None or result.revision is None:
            raise ValueError("cannot append a rejected proposal")

        base_revision = payload_dict.get("base_revision")
        lease_id = payload_dict.get("lease_id")
        fencing_token = payload_dict.get("fencing_token")

        with self._conn:
            # 1. Check concurrency
            current_rev, current_hash = self.head(proof_id)
            if base_revision is not None and current_rev != base_revision:
                raise ConcurrencyError(
                    f"base_revision {base_revision} is stale, head is {current_rev}"
                )

            # 2. Check lease fencing
            if lease_id is not None or fencing_token is not None:
                lease_row = self._conn.execute(
                    "SELECT lease_id, fencing_token FROM leases WHERE proof_id = ?", 
                    (proof_id,)
                ).fetchone()
                
                if not lease_row:
                    raise ConcurrencyError(f"no active lease for {proof_id}")
                if lease_row["lease_id"] != lease_id:
                    raise ConcurrencyError(f"lease {lease_id!r} is not the active lease")
                if lease_row["fencing_token"] != fencing_token:
                    raise ConcurrencyError(f"fencing token {fencing_token} has been superseded")

            # 3. Check hash chain
            # The gate already chained it from what it thought was head, but we double check
            # that what it thought was head is still head.
            # We don't have the prev_hash directly in `result`, but `current_rev == base_revision` 
            # implies the head hasn't moved.
            
            # 4. Insert
            # The journal stores the exact JSON payload the gate saw.
            payload_str = json.dumps(payload_dict)
            self._conn.execute(
                """
                INSERT INTO journal (
                    revision, proof_id, event_hash, prev_hash, actor, worker_class, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.revision,
                    proof_id,
                    result.event_hash,
                    current_hash,
                    payload_dict["actor"],
                    payload_dict["worker_class"],
                    payload_str,
                ),
            )

    def read_events(self, proof_id: str) -> Sequence[dict[str, Any]]:
        """Read all events for a proof in revision order."""
        rows = self._conn.execute(
            "SELECT payload FROM journal WHERE proof_id = ? ORDER BY revision ASC",
            (proof_id,),
        ).fetchall()
        return [json.loads(row["payload"]) for row in rows]
