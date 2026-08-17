import unittest

from commit_gate.canon import GENESIS_HASH
from commit_gate.gate import CommitGate
from commit_gate.ops import UpsertNode
from commit_gate.proposal import Proposal
from commit_gate.state import MemoryView

class TestCommitGate(unittest.TestCase):
    def test_gate_accepts_valid_proposal(self):
        view = MemoryView()
        gate = CommitGate(view, GENESIS_HASH, 0)
        
        proposal = Proposal(
            proof_id="p1",
            actor="test",
            worker_class="test",
            ops=(UpsertNode("FormalState", "p1/fs1", {"status": "open"}),)
        )
        
        result = gate.commit(proposal)
        self.assertTrue(result.accepted)
        self.assertIsNotNone(result.event_hash)
        self.assertEqual(result.revision, 1)

    def test_gate_rejects_invalid_proposal(self):
        view = MemoryView()
        gate = CommitGate(view, GENESIS_HASH, 0)
        
        # Missing required field `subgoal_count` on TacticApplication
        proposal = Proposal(
            proof_id="p1",
            actor="test",
            worker_class="test",
            ops=(UpsertNode("TacticApplication", "p1/ta1", {"executor_result": "lean-accepted"}),)
        )
        
        result = gate.commit(proposal)
        self.assertFalse(result.accepted)
        self.assertIsNone(result.event_hash)
        self.assertIsNone(result.revision)
        self.assertGreater(len(result.rejections), 0)

if __name__ == "__main__":
    unittest.main()
