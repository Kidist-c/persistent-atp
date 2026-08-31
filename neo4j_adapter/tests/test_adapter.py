import unittest

from neo4j_adapter.adapter import Neo4jAdapter  


class TestNeo4jAdapter(unittest.TestCase):
    """Integration tests against a live local Neo4j instance.

    Uses a dedicated proof_id so runs never collide with real workspace
    data, and wipes that namespace in tearDown.
    """

    PROOF_ID = "test-proof-adapter"

    def setUp(self):
        self.adapter = Neo4jAdapter()
        self.adapter.init_proof(
            proof_id=self.PROOF_ID,
            theorem_kernel="test kernel",
            theorem_hash="hash-abc",
            event_id="ev-setup",
        )

    def tearDown(self):
        with self.adapter._driver.session() as s:
            s.run("MATCH (n {proof_id: $pid}) DETACH DELETE n", pid=self.PROOF_ID)
        self.adapter.close()

    # -- Proof --------------------------------------------------------

    def test_init_proof_creates_proof_node_with_correct_properties(self):
        with self.adapter._driver.session() as s:
            record = s.run(
                "MATCH (p:Proof {proof_id: $pid, id: $pid}) RETURN p",
                pid=self.PROOF_ID,
            ).single()
        self.assertIsNotNone(record)
        self.assertEqual(record["p"]["theorem_kernel"], "test kernel")
        self.assertEqual(record["p"]["theorem_hash"], "hash-abc")
        self.assertEqual(record["p"]["active_revision"], 0)

    # -- States ---------------------------------------------------------

    def test_add_state_creates_state_and_links_to_proof(self):
        self.adapter.add_state(self.PROOF_ID, "s1", "root goal", event_id="ev1")

        state = self.adapter.get_state("s1", self.PROOF_ID)
        self.assertIsNotNone(state)
        self.assertEqual(state["status"], "open")
        self.assertEqual(state["description"], "root goal")

        with self.adapter._driver.session() as s:
            linked = s.run(
                "MATCH (:Proof {proof_id: $pid, id: $pid})-[:HAS_STATE]->"
                "(st:State {id: 's1'}) RETURN st",
                pid=self.PROOF_ID,
            ).single()
        self.assertIsNotNone(linked)

    def test_add_state_links_child_to_parent_via_child_of(self):
        self.adapter.add_state(self.PROOF_ID, "root", "root goal", event_id="ev1")
        self.adapter.add_state(
            self.PROOF_ID, "child1", "subgoal", parent_id="root", event_id="ev2"
        )
        with self.adapter._driver.session() as s:
            record = s.run(
                "MATCH (c:State {proof_id: $pid, id: 'child1'})"
                "-[:CHILD_OF]->(p:State {proof_id: $pid, id: 'root'}) RETURN c",
                pid=self.PROOF_ID,
            ).single()
        self.assertIsNotNone(record)

    def test_add_state_rejects_invalid_kind(self):
        with self.assertRaises(ValueError):
            self.adapter.add_state(
                self.PROOF_ID, "s1", "goal", kind="not-a-real-kind"
            )

    def test_update_state_status_persists_and_records_reason(self):
        self.adapter.add_state(self.PROOF_ID, "s1", "goal", event_id="ev1")
        self.adapter.update_state_status(
            self.PROOF_ID, "s1", status="closed", reason="proved", event_id="ev2"
        )
        state = self.adapter.get_state("s1", self.PROOF_ID)
        self.assertEqual(state["status"], "formally-closed")  
        self.assertEqual(state["closed_reason"], "proved")

    def test_update_state_status_rejects_invalid_status(self):
        self.adapter.add_state(self.PROOF_ID, "s1", "goal", event_id="ev1")
        with self.assertRaises(ValueError):
            self.adapter.update_state_status(self.PROOF_ID, "s1", status="bogus")

    def test_get_state_returns_none_when_missing(self):
        self.assertIsNone(self.adapter.get_state("nope", self.PROOF_ID))

    # -- Claims -----------------------------------------------------------

    def test_add_claim_creates_claim_and_links_to_proof(self):
        self.adapter.add_claim(self.PROOF_ID, "c1", "n+0=n", event_id="ev1")
        claims = self.adapter.get_all_claims(self.PROOF_ID)
        ids = [c["id"] for c in claims]
        self.assertIn("c1", ids)
        c1 = next(c for c in claims if c["id"] == "c1")
        self.assertEqual(c1["status"], "conjectural")  # documented default

    def test_add_claim_rejects_invalid_status(self):
        with self.assertRaises(ValueError):
            self.adapter.add_claim(self.PROOF_ID, "c1", "stmt", status="bogus")

    def test_update_claim_status_persists(self):
        self.adapter.add_claim(self.PROOF_ID, "c1", "stmt", event_id="ev1")
        self.adapter.update_claim_status(
            "c1", status="critic-accepted", proof_id=self.PROOF_ID, event_id="ev2"
        )
        claim = next(
            c for c in self.adapter.get_all_claims(self.PROOF_ID) if c["id"] == "c1"
        )
        self.assertEqual(claim["status"], "critic-accepted")  

    def test_add_claim_dependency_creates_depends_on_edge(self):
        self.adapter.add_claim(self.PROOF_ID, "c1", "stmt1", event_id="ev1")
        self.adapter.add_claim(self.PROOF_ID, "c2", "stmt2", event_id="ev2")
        self.adapter.add_claim_dependency(
            "c1", "c2", proof_id=self.PROOF_ID, event_id="ev3"
        )
        with self.adapter._driver.session() as s:
            record = s.run(
                "MATCH (:Claim {proof_id: $pid, id: 'c1'})"
                "-[:DEPENDS_ON]->(:Claim {proof_id: $pid, id: 'c2'}) RETURN 1",
                pid=self.PROOF_ID,
            ).single()
        self.assertIsNotNone(record)

    def test_add_claim_dependency_rejects_cycle_when_proof_id_given(self):
        self.adapter.add_claim(self.PROOF_ID, "c1", "stmt1", event_id="ev1")
        self.adapter.add_claim(self.PROOF_ID, "c2", "stmt2", event_id="ev2")
        self.adapter.add_claim_dependency("c1", "c2", proof_id=self.PROOF_ID)

        with self.assertRaises(ValueError):
            # c2 -> c1 would close a cycle since c1 -> c2 already exists
            self.adapter.add_claim_dependency("c2", "c1", proof_id=self.PROOF_ID)

    def test_add_claim_dependency_skips_cycle_check_when_proof_id_omitted(self):
        """Known gap: cycle guard is bypassed if proof_id is left as ''.

        This test documents current behavior rather than asserting it's
        correct — worth raising with the team as a possible follow-up fix.
        """
        self.adapter.add_claim(self.PROOF_ID, "c1", "stmt1", event_id="ev1")
        self.adapter.add_claim(self.PROOF_ID, "c2", "stmt2", event_id="ev2")
        self.adapter.add_claim_dependency("c1", "c2", proof_id=self.PROOF_ID)

        # No proof_id passed here -- does NOT raise, even though it's a cycle.
        try:
            self.adapter.add_claim_dependency("c2", "c1")
        except ValueError:
            self.fail(
                "cycle check unexpectedly ran without proof_id -- "
                "if this now raises, the underlying bug has been fixed; "
                "update this test to assertRaises instead."
            )

    # -- Moves and subgoals -----------------------------------------------

    def test_add_move_creates_move_and_links_via_proposes(self):
        self.adapter.add_state(self.PROOF_ID, "s1", "goal", event_id="ev1")
        self.adapter.add_move(
            self.PROOF_ID, "m1", "s1", "try induction", event_id="ev2"
        )
        moves = self.adapter.get_moves_for_state("s1", self.PROOF_ID)
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0]["move_summary"], "try induction")
        self.assertEqual(moves[0]["status"], "queued")

    def test_add_move_rejects_invalid_status(self):
        self.adapter.add_state(self.PROOF_ID, "s1", "goal", event_id="ev1")
        with self.assertRaises(ValueError):
            self.adapter.add_move(
                self.PROOF_ID, "m1", "s1", "try induction", status="bogus"
            )

    def test_add_required_subgoal_creates_state_and_links_via_requires(self):
        self.adapter.add_state(self.PROOF_ID, "s1", "goal", event_id="ev1")
        self.adapter.add_move(self.PROOF_ID, "m1", "s1", "split into cases", event_id="ev2")
        self.adapter.add_required_subgoal(
            self.PROOF_ID, "m1", "sub1", "base case", event_id="ev3"
        )

        subgoals = self.adapter.get_subgoals_for_move("m1", self.PROOF_ID)
        self.assertEqual(len(subgoals), 1)
        self.assertEqual(subgoals[0]["id"], "sub1")
        self.assertEqual(subgoals[0]["kind"], "and")
        self.assertEqual(subgoals[0]["status"], "open")

    def test_update_move_status_persists(self):
        self.adapter.add_state(self.PROOF_ID, "s1", "goal", event_id="ev1")
        self.adapter.add_move(self.PROOF_ID, "m1", "s1", "induction", event_id="ev2")
        self.adapter.update_move_status("m1", "leased", proof_id=self.PROOF_ID, event_id="ev3")
        move = self.adapter.get_moves_for_state("s1", self.PROOF_ID)[0]
        self.assertEqual(move["status"], "leased")

    # -- context_for --------------------------------------------------

    def test_context_for_returns_complete_dict(self):
        self.adapter.add_state(self.PROOF_ID, "s1", "goal", event_id="ev1")
        self.adapter.add_move(self.PROOF_ID, "m1", "s1", "induction", event_id="ev2")
        self.adapter.add_required_subgoal(self.PROOF_ID, "m1", "sub1", "base case", event_id="ev3")
        self.adapter.add_claim(self.PROOF_ID, "c1", "stmt", event_id="ev4")
        self.adapter.add_attempt(
            self.PROOF_ID, "a1", "s1", "tried induction", event_id="ev5"
        )

        ctx = self.adapter.context_for(self.PROOF_ID, "s1")

        self.assertEqual(ctx["state"]["id"], "s1")
        self.assertEqual(len(ctx["moves"]), 1)
        self.assertEqual(len(ctx["attempts"]), 1)
        self.assertEqual(len(ctx["claims"]), 1)
        self.assertEqual(len(ctx["subgoals"]), 1)
        self.assertIn("frontier", ctx)  # exercises eligible_frontier() indirectly

    # -- add_relation whitelist -------------------------------------------

    def test_add_relation_accepts_whitelisted_type(self):
        self.adapter.add_claim(self.PROOF_ID, "c1", "stmt1", event_id="ev1")
        self.adapter.add_claim(self.PROOF_ID, "c2", "stmt2", event_id="ev2")
        # SUPERSEDES is in REL_WHITELIST
        self.adapter.add_relation(self.PROOF_ID, "SUPERSEDES", "c1", "c2", event_id="ev3")

        with self.adapter._driver.session() as s:
            record = s.run(
                "MATCH (:Claim {proof_id: $pid, id: 'c1'})"
                "-[:SUPERSEDES]->(:Claim {proof_id: $pid, id: 'c2'}) RETURN 1",
                pid=self.PROOF_ID,
            ).single()
        self.assertIsNotNone(record)

    def test_add_relation_rejects_non_whitelisted_type(self):
        self.adapter.add_claim(self.PROOF_ID, "c1", "stmt1", event_id="ev1")
        self.adapter.add_claim(self.PROOF_ID, "c2", "stmt2", event_id="ev2")
        with self.assertRaises(ValueError):
            # DROP TABLE isn't a real Cypher risk here since it's an f-string
            # relationship *type*, not a full query -- but it's still not
            # whitelisted, which is what we're actually testing.
            self.adapter.add_relation(self.PROOF_ID, "NOT_A_REAL_REL", "c1", "c2")


if __name__ == "__main__":
    unittest.main()