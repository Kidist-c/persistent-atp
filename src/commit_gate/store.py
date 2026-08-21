"""SQL journal store for the commit gate.

The journal is the durability authority: an event is committed when it is here.
Every mutation runs inside one `BEGIN IMMEDIATE` transaction, so reading the
head and inserting its successor cannot interleave with another writer.

Only the commit gate may call the mutating methods.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

from .canon import GENESIS_HASH, canonical_json, chain_hash
from .reasons import Reason

__all__ = ["JournalStore", "ConcurrencyError", "HashChainError"]


class ConcurrencyError(Exception):
    """A write lost a race against another writer.

    Carries the `Reason` the gate reports back to the proposer, so both layers
    name the failure identically without the store building a `Rejection`.
    """

    def __init__(self, reason: Reason, detail: str):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


class HashChainError(Exception):
    """Raised when a journal's recorded hashes do not chain."""


class JournalStore:
    """A SQLite-backed append-only journal of proof events."""

    def __init__(self, db_path: str = ":memory:"):
        # Autocommit mode: `with conn:` begins no transaction when
        # isolation_level is None, so `_write` opens them explicitly.
        self._conn = sqlite3.connect(db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS journal (
                proof_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                event_hash TEXT NOT NULL UNIQUE,
                prev_hash TEXT NOT NULL,
                actor TEXT NOT NULL,
                worker_class TEXT NOT NULL,
                payload TEXT NOT NULL,
                committed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (proof_id, revision)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leases (
                proof_id TEXT PRIMARY KEY,
                lease_id TEXT NOT NULL,
                fencing_token INTEGER NOT NULL
            )
            """
        )

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        """Hold the database write lock for the whole block, or roll back."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self._conn
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise

    def head(self, proof_id: str) -> tuple[int, str]:
        """The `(revision, event_hash)` of this proof's latest event."""
        row = self._conn.execute(
            """
            SELECT revision, event_hash FROM journal
            WHERE proof_id = ? ORDER BY revision DESC LIMIT 1
            """,
            (proof_id,),
        ).fetchone()
        if row is None:
            return 0, GENESIS_HASH
        return row["revision"], row["event_hash"]

    def acquire_lease(self, proof_id: str, lease_id: str) -> int:
        """Take the write lease on `proof_id`, returning its fencing token.

        Tokens increase monotonically per proof and never repeat, so once a
        newer holder has acquired, an older holder's writes are rejected.
        """
        with self._write() as conn:
            row = conn.execute(
                "SELECT fencing_token FROM leases WHERE proof_id = ?", (proof_id,)
            ).fetchone()
            if row is None:
                token = 1
                conn.execute(
                    "INSERT INTO leases (proof_id, lease_id, fencing_token) VALUES (?, ?, ?)",
                    (proof_id, lease_id, token),
                )
            else:
                token = row["fencing_token"] + 1
                conn.execute(
                    "UPDATE leases SET lease_id = ?, fencing_token = ? WHERE proof_id = ?",
                    (lease_id, token, proof_id),
                )
        return token

    def append(self, payload_dict: dict[str, Any]) -> tuple[int, str]:
        """Append one already-validated proposal; return `(revision, event_hash)`.

        Reads the head, checks the proposal's concurrency expectations against
        it, chains onto it, and inserts — all under one write lock, so the head
        cannot move between the check and the insert.
        """
        proof_id = payload_dict["proof_id"]
        base_revision = payload_dict.get("base_revision")
        lease_id = payload_dict.get("lease_id")
        fencing_token = payload_dict.get("fencing_token")

        with self._write() as conn:
            head_revision, head_hash = self.head(proof_id)

            if base_revision is not None and base_revision != head_revision:
                raise ConcurrencyError(
                    Reason.STALE_BASE_REVISION,
                    f"proposal is based on revision {base_revision}, head is {head_revision}",
                )

            if lease_id is not None or fencing_token is not None:
                self._check_lease(conn, proof_id, lease_id, fencing_token)

            revision = head_revision + 1
            event_hash = chain_hash(head_hash, payload_dict)
            conn.execute(
                """
                INSERT INTO journal (
                    proof_id, revision, event_hash, prev_hash,
                    actor, worker_class, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proof_id,
                    revision,
                    event_hash,
                    head_hash,
                    payload_dict["actor"],
                    payload_dict["worker_class"],
                    canonical_json(payload_dict).decode("utf-8"),
                ),
            )
        return revision, event_hash

    @staticmethod
    def _check_lease(
        conn: sqlite3.Connection,
        proof_id: str,
        lease_id: str | None,
        fencing_token: int | None,
    ) -> None:
        """Confirm the proposer still holds the proof's current lease."""
        row = conn.execute(
            "SELECT lease_id, fencing_token FROM leases WHERE proof_id = ?", (proof_id,)
        ).fetchone()
        if row is None:
            raise ConcurrencyError(
                Reason.LEASE_NOT_HELD, f"no lease is held on {proof_id!r}"
            )
        if row["lease_id"] != lease_id:
            raise ConcurrencyError(
                Reason.LEASE_NOT_HELD,
                f"lease {lease_id!r} is not the lease held on {proof_id!r}",
            )
        if row["fencing_token"] != fencing_token:
            raise ConcurrencyError(
                Reason.FENCING_TOKEN_SUPERSEDED,
                f"fencing token {fencing_token!r} is superseded by {row['fencing_token']!r}",
            )

    def read_events(self, proof_id: str) -> Sequence[dict[str, Any]]:
        """Every event payload for a proof, in revision order."""
        rows = self._conn.execute(
            "SELECT payload FROM journal WHERE proof_id = ? ORDER BY revision ASC",
            (proof_id,),
        ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def read_chain(self, proof_id: str) -> Sequence[tuple[int, str, str]]:
        """Every `(revision, event_hash, prev_hash)` for a proof, in order."""
        rows = self._conn.execute(
            """
            SELECT revision, event_hash, prev_hash FROM journal
            WHERE proof_id = ? ORDER BY revision ASC
            """,
            (proof_id,),
        ).fetchall()
        return [(row["revision"], row["event_hash"], row["prev_hash"]) for row in rows]
