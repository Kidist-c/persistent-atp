import unittest

from commit_gate.canon import GENESIS_HASH
from commit_gate.gate import CommitResult
from commit_gate.store import ConcurrencyError, JournalStore

class TestJournalStore(unittest.TestCase):
    def test_head_on_empty_journal(self):
        store = JournalStore()
        rev, h = store.head("p1")
        self.assertEqual(rev, 0)
        self.assertEqual(h, GENESIS_HASH)

    def test_append_and_read(self):
        store = JournalStore()
        
        result = CommitResult(accepted=True, rejections=(), event_hash="hash1", revision=1)
        payload = {"actor": "test", "worker_class": "test"}
        
        store.append("p1", payload, result)
        
        rev, h = store.head("p1")
        self.assertEqual(rev, 1)
        self.assertEqual(h, "hash1")
        
        events = store.read_events("p1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["actor"], "test")

    def test_base_revision_mismatch(self):
        store = JournalStore()
        result = CommitResult(accepted=True, rejections=(), event_hash="hash1", revision=1)
        payload = {"actor": "test", "worker_class": "test", "base_revision": 99}
        
        with self.assertRaises(ConcurrencyError):
            store.append("p1", payload, result)

    def test_lease_fencing(self):
        store = JournalStore()
        token = store.acquire_lease("p1", "lease1")
        
        result = CommitResult(accepted=True, rejections=(), event_hash="hash1", revision=1)
        
        # Correct token and lease
        payload = {"actor": "test", "worker_class": "test", "lease_id": "lease1", "fencing_token": token}
        store.append("p1", payload, result)
        
        # Wrong token
        payload2 = {"actor": "test", "worker_class": "test", "lease_id": "lease1", "fencing_token": 0}
        result2 = CommitResult(accepted=True, rejections=(), event_hash="hash2", revision=2)
        with self.assertRaises(ConcurrencyError):
            store.append("p1", payload2, result2)

if __name__ == "__main__":
    unittest.main()
