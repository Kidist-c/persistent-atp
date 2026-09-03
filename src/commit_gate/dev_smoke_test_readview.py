"""Manual smoke test for Neo4jReadView against a REAL, running Neo4j.

Not a pytest test (that's next, gated by env var). This is just for you to
run once by hand and eyeball the output, to catch anything only a real
server would reveal -- wrong Cypher, a driver version quirk, auth issues.

Usage:
    cd src
    python -m commit_gate.dev_smoke_test_readview

Assumes NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD env vars are set (or the
defaults: bolt://localhost:7687, user "neo4j"). WARNING: this writes and
then deletes two throwaway nodes/edges under a "smoketest/" id prefix in
whatever database you point it at -- don't run it against anything you
care about.
"""

from __future__ import annotations

from commit_gate.neo4j_readview import Neo4jReadView


def _bootstrap_fixture(view: Neo4jReadView) -> None:
    """Write two nodes and one edge directly, bypassing the (not-yet-built)
    projector, so we have something real to read back."""
    with view._driver.session(database=view._database) as session:
        session.run(
            "MERGE (a:GateNode {gate_id: $id}) "
            "SET a.gate_label = $label, a.status = $status",
            id="smoketest/claim1", label="Claim", status="formally-closed",
        )
        session.run(
            "MERGE (b:GateNode {gate_id: $id}) "
            "SET b.gate_label = $label, b.actor = $actor",
            id="smoketest/cert1", label="Certificate", actor="producer-1",
        )
        session.run(
            "MATCH (a:GateNode {gate_id: $src}), (b:GateNode {gate_id: $dst}) "
            "MERGE (a)-[r:PROVED_BY {gate_edge_id: $eid}]->(b)",
            src="smoketest/claim1", dst="smoketest/cert1", eid="smoketest/e1",
        )


def _cleanup_fixture(view: Neo4jReadView) -> None:
    with view._driver.session(database=view._database) as session:
        session.run(
            "MATCH (n:GateNode) WHERE n.gate_id STARTS WITH 'smoketest/' "
            "DETACH DELETE n"
        )


def main() -> None:
    view = Neo4jReadView()
    try:
        print("Connected OK.")
        _bootstrap_fixture(view)

        claim = view.node("smoketest/claim1")
        print("node('smoketest/claim1') ->", claim)
        assert claim is not None
        assert claim.label == "Claim"
        assert claim.fields["status"] == "formally-closed"

        missing = view.node("smoketest/does-not-exist")
        print("node(missing) ->", missing)
        assert missing is None

        edges = view.edges_from("smoketest/claim1", "PROVED_BY")
        print("edges_from(claim1, PROVED_BY) ->", edges)
        assert len(edges) == 1
        assert edges[0].dst_id == "smoketest/cert1"

        edge = view.edge(edges[0].edge_id)
        print("edge(that edge's id) ->", edge)
        assert edge is not None
        assert edge.rel_type == "PROVED_BY"

        back = view.edges_to("smoketest/cert1", "PROVED_BY")
        print("edges_to(cert1, PROVED_BY) ->", back)
        assert len(back) == 1
        assert back[0].src_id == "smoketest/claim1"

        wrong_type = view.edges_from("smoketest/claim1", "REPLAYED_BY")
        print("edges_from(claim1, REPLAYED_BY) [should be empty] ->", wrong_type)
        assert wrong_type == ()

        print("\nAll checks passed.")
    finally:
        _cleanup_fixture(view)
        view.close()
        print("Cleaned up smoketest/* nodes.")


if __name__ == "__main__":
    main()