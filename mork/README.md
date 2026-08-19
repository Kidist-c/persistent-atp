# Unified MORK proof-metagraph examples

This directory contains compact examples for the version 3 dual-loop architecture. The metagraph stores both the long-horizon research program and exact Lean-native proof search while preserving different node types, status systems, and authority boundaries.

The files are illustrative rather than pinned executable claims. MM2 syntax and performance should be tested against the exact PeTTa/MORK revision chosen by a deployment.

## Files

- `unified_proof_atoms.metta` - the preferred version 3 example, including research states, claims, statement alignment, formal runs, exact Lean states, tactic hyperedges, scores, obstructions, certificates, and replay.
- `proof_atoms.metta` - the smaller version 2-compatible research-layer example retained for migration tests.
- `indexes.mm2` - research reverse indexes and frontier projections.
- `formal_indexes.mm2` - formal-state, tactic-edge, and formal-frontier projections.
- `transposition_candidates.mm2` - exact and semantic candidate views; semantic matches never merge automatically.
- `dependency_reachability.mm2` - claim-dependency closure.
- `taint_propagation.mm2` - invalidation propagation after refutation or retraction.
- `route_projection.mm2` - semantic route projection over the research search graph.

## Key invariants

A MORK encoding path is not a mathematical proof route. A formal tactic edge has OR semantics among alternatives and AND semantics across all Lean-produced child goals. Heuristic score atoms are annotations only. Claim promotion to `lean-verified` requires a matching certificate and an accepted independent replay in the pinned environment.

The authoritative conceptual model is in `../docs/UNIFIED_METAGRAPH.md` and `../docs/FORMAL_SOUNDNESS_INVARIANTS.md`.