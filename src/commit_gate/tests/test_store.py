import unittest

from commit_gate.canon import GENESIS_HASH
from commit_gate.reasons import Reason
from commit_gate.store import ConcurrencyError, JournalStore


def payload(**overrides):
    """A minimal well-formed event payload, as `Proposal.to_dict` produces."""
    base = {"proof_id": "p1", "actor": "test", "worker_class": "test"}
    base.update(overrides)
    return base


class TestJournalStore(unittest.TestCase):
    def test_head_on_empty_journal(self):
        store = JournalStore()
        self.assertEqual(store.head("p1"), (0, GENESIS_HASH))

    def test_append_and_read(self):
        store = JournalStore()
        revision, event_hash = store.append(payload())

        self.assertEqual(revision, 1)
        self.assertEqual(store.head("p1"), (1, event_hash))

        events = store.read_events("p1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["actor"], "test")

    def test_append_chains_onto_the_head(self):
        store = JournalStore()
        _, first = store.append(payload())
        _, second = store.append(payload())

        self.assertEqual(
            store.read_chain("p1"),
            [(1, first, GENESIS_HASH), (2, second, first)],
        )

    def test_revisions_are_numbered_per_proof(self):
        store = JournalStore()
        store.append(payload(proof_id="p1"))
        revision, _ = store.append(payload(proof_id="p2"))
        self.assertEqual(revision, 1)

    def test_base_revision_mismatch(self):
        store = JournalStore()
        with self.assertRaises(ConcurrencyError) as caught:
            store.append(payload(base_revision=99))
        self.assertEqual(caught.exception.reason, Reason.STALE_BASE_REVISION)

    def test_failed_append_leaves_the_journal_untouched(self):
        store = JournalStore()
        _, first = store.append(payload())

        with self.assertRaises(ConcurrencyError):
            store.append(payload(base_revision=99))

        self.assertEqual(store.head("p1"), (1, first))
        self.assertEqual(len(store.read_events("p1")), 1)

    def test_lease_fencing(self):
        store = JournalStore()
        token = store.acquire_lease("p1", "lease1")

        store.append(payload(lease_id="lease1", fencing_token=token))

        with self.assertRaises(ConcurrencyError) as caught:
            store.append(payload(lease_id="lease1", fencing_token=0))
        self.assertEqual(caught.exception.reason, Reason.FENCING_TOKEN_SUPERSEDED)

    def test_reacquiring_the_lease_locks_out_the_old_holder(self):
        store = JournalStore()
        old = store.acquire_lease("p1", "lease1")
        new = store.acquire_lease("p1", "lease2")
        self.assertGreater(new, old)

        with self.assertRaises(ConcurrencyError) as caught:
            store.append(payload(lease_id="lease1", fencing_token=old))
        self.assertEqual(caught.exception.reason, Reason.LEASE_NOT_HELD)

    def test_lease_claimed_but_never_acquired(self):
        store = JournalStore()
        with self.assertRaises(ConcurrencyError) as caught:
            store.append(payload(lease_id="lease1", fencing_token=1))
        self.assertEqual(caught.exception.reason, Reason.LEASE_NOT_HELD)


if __name__ == "__main__":
    unittest.main()
