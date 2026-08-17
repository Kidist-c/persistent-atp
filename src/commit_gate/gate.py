"""The commit gate orchestrator.

The gate validates a proposal against a view of committed state, and if accepted,
returns a chained hash. The caller is responsible for appending the ops to the
journal and projecting them into the graph database.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canon import chain_hash, content_hash
from .proposal import Proposal
from .reasons import Rejection
from .state import ReadView
from .validate import validate_proposal

__all__ = ["CommitResult", "CommitGate"]


@dataclass(frozen=True, slots=True)
class CommitResult:
    """The outcome of submitting a proposal to the gate."""

    accepted: bool
    rejections: tuple[Rejection, ...]
    event_hash: str | None
    revision: int | None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "accepted": self.accepted,
            "rejections": [r.to_dict() for r in self.rejections],
        }
        if self.event_hash is not None:
            payload["event_hash"] = self.event_hash
        if self.revision is not None:
            payload["revision"] = self.revision
        return payload


class CommitGate:
    """Orchestrates proposal validation and cryptographic chaining."""

    def __init__(self, view: ReadView, head_hash: str, head_revision: int):
        self._view = view
        self._head_hash = head_hash
        self._head_revision = head_revision

    def validate(self, proposal: Proposal) -> list[Rejection]:
        """Run all validators against the current view."""
        return validate_proposal(proposal, self._view)

    def commit(self, proposal: Proposal) -> CommitResult:
        """Validate, and if accepted, compute the cryptographic chain."""
        rejections = self.validate(proposal)
        if rejections:
            return CommitResult(
                accepted=False,
                rejections=tuple(rejections),
                event_hash=None,
                revision=None,
            )

        # Build the event payload exactly as it will be journaled
        body = proposal.to_dict()
        event_hash = chain_hash(self._head_hash, body)
        next_revision = self._head_revision + 1
        
        return CommitResult(
            accepted=True,
            rejections=(),
            event_hash=event_hash,
            revision=next_revision,
        )
