"""Closed vocabularies for committed proof state.

Every status string the commit gate may write is declared here. Section
references are to the Unified Dual-Loop Architecture v3 technical design.
"""

from enum import StrEnum

__all__ = [
    "ClaimStatus",
    "FormalStateStatus",
    "DeclarationStatus",
    "CertificateStatus",
    "AlignmentLifecycle",
    "AlignmentVerdict",
    "RunDisposition",
    "ExecutorResult",
    "TacticStatus",
    "ReplayStatus",
    "ObstructionKind",
    "EvidenceKind",
    "WorkerClass",
    "ANNOTATION_FIELDS",
    "TERMINAL_EXECUTOR_FAILURES",
]


class ClaimStatus(StrEnum):
    """Research claim status (11.1)."""

    CONJECTURAL = "conjectural"
    EMPIRICAL = "empirical"
    PROVISIONAL = "provisional"
    CRITIC_ACCEPTED = "critic-accepted"
    FORMALLY_CLOSED = "formally-closed"
    LEAN_VERIFIED = "lean-verified"
    REFUTED = "refuted"
    RETRACTED = "retracted"
    STALE = "stale"


class FormalStateStatus(StrEnum):
    """Formal state operational status (11.1)."""

    OPEN = "open"
    EXPANDED = "expanded"
    FORMALLY_CLOSED = "formally-closed"
    LEAN_VERIFIED = "lean-verified"
    FAILED = "failed"
    PRUNED = "pruned"
    STALE = "stale"


class DeclarationStatus(StrEnum):
    """Formal declaration lifecycle (11.1)."""

    DRAFT = "draft"
    ALIGNED = "aligned"
    SEARCHING = "searching"
    CERTIFICATE_PRODUCED = "certificate-produced"
    REPLAY_PENDING = "replay-pending"
    REPLAY_ACCEPTED = "replay-accepted"
    REPLAY_REJECTED = "replay-rejected"
    STALE = "stale"


class CertificateStatus(StrEnum):
    """Certificate lifecycle (11.4)."""

    CANDIDATE = "candidate"
    REPLAY_PENDING = "replay-pending"
    REPLAY_ACCEPTED = "replay-accepted"
    REPLAY_REJECTED = "replay-rejected"
    STALE = "stale"


class AlignmentLifecycle(StrEnum):
    """Review stage of an alignment record (5.4)."""

    DRAFT = "draft"
    REVIEW_NEEDED = "review-needed"
    REVIEWED = "reviewed"
    SUPERSEDED = "superseded"
    STALE = "stale"


class AlignmentVerdict(StrEnum):
    """Reviewer's field-by-field conclusion (C.4)."""

    ALIGNED = "aligned"
    WEAKER = "weaker"
    STRONGER = "stronger"
    MISMATCH = "mismatch"
    AMBIGUOUS = "ambiguous"


class RunDisposition(StrEnum):
    """Formal run result disposition (6.10)."""

    SEARCHING = "searching"
    PROVED_PENDING_REPLAY = "proved-pending-replay"
    BUDGET_EXHAUSTED = "budget-exhausted"
    STAGNATED = "stagnated"
    COUNTEREXAMPLE = "counterexample"
    INVALID_REQUEST = "invalid-request"
    ENVIRONMENT_ERROR = "environment-error"
    INTERNAL_ERROR = "internal-error"
    CANCELLED = "cancelled"


class ExecutorResult(StrEnum):
    """What the Lean/Pantograph executor reported (11.3)."""

    LEAN_ACCEPTED = "lean-accepted"
    LEAN_REJECTED = "lean-rejected"
    TIMEOUT = "timeout"
    BACKEND_MISSING = "backend-missing"
    PARSE_FAILURE = "parse-failure"
    CRASH = "crash"
    EMPTY_OUTPUT = "empty-output"


TERMINAL_EXECUTOR_FAILURES = frozenset(
    {
        ExecutorResult.TIMEOUT,
        ExecutorResult.BACKEND_MISSING,
        ExecutorResult.PARSE_FAILURE,
        ExecutorResult.CRASH,
        ExecutorResult.EMPTY_OUTPUT,
    }
)
"""Executor outcomes that are infrastructure failures, not mathematical ones."""


class TacticStatus(StrEnum):
    """Tactic application status, derived from child closure (B.3)."""

    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    DEAD = "dead"


class ReplayStatus(StrEnum):
    """Independent replay outcome (6.11)."""

    VERIFIED = "verified"
    REJECTED = "rejected"


class ObstructionKind(StrEnum):
    """Typed obstruction taxonomy (7.4)."""

    MISSING_LEMMA = "missing-lemma"
    MISSING_PREMISE = "missing-premise"
    REPRESENTATION_MISMATCH = "representation-mismatch"
    STATEMENT_TOO_STRONG = "statement-too-strong"
    STATEMENT_TOO_WEAK = "statement-too-weak"
    LIBRARY_GAP = "library-gap"
    ELABORATION = "elaboration"
    TYPECLASS = "typeclass"
    COERCION = "coercion"
    RESOURCE = "resource"
    SEARCH_POLICY = "search-policy"
    LIKELY_FALSE = "likely-false"
    UNKNOWN = "unknown"


class EvidenceKind(StrEnum):
    """Evidence classes from the 11.5 permitted-conclusion table."""

    LEAN_REPLAY = "lean-replay"
    RANDOM_SAMPLING = "random-sampling"
    EXHAUSTIVE_FINITE_SEARCH = "exhaustive-finite-search"
    EXACT_SYMBOLIC = "exact-symbolic"
    INTERVAL_ARITHMETIC = "interval-arithmetic"
    CHECKABLE_CERTIFICATE = "checkable-certificate"
    HEURISTIC_OPTIMIZER = "heuristic-optimizer"
    MODEL_SCORE = "model-score"
    CRITIC_REVIEW = "critic-review"
    HUMAN_GUIDANCE = "human-guidance"


class WorkerClass(StrEnum):
    """Proposal actors (3.2)."""

    COORDINATOR = "coordinator"
    LLM_RESEARCH = "llm-research"
    HYPERON = "hyperon"
    FORMAL_ATP = "formal-atp"
    REPLAYER = "replayer"
    CRITIC = "critic"
    EXPERIMENT = "experiment"
    ALIGNMENT_REVIEWER = "alignment-reviewer"
    HUMAN = "human"
    MAINTENANCE = "maintenance"


ANNOTATION_FIELDS = frozenset(
    {
        "gnn_tactic_prior",
        "argument_probability",
        "premise_relevance",
        "pln_strength",
        "pln_confidence",
        "proof_number",
        "disproof_number",
        "depth",
        "estimated_execution_cost",
        "state_novelty",
        "transposition_count",
        "failure_family",
        "dependency_centrality",
        "expected_information_gain",
        "verification_value",
        "repeated_failure_risk",
        "derived_priority",
    }
)
"""Heuristic score fields (2.4, A.5). Writes to these are annotation-class."""
