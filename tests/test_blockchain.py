"""Unit tests for the Blockchain Simulator.

Difficulty is kept low (1-2 hex zeros) so the whole suite mines quickly,
both locally and in CI.
"""

import statistics
import unittest

from blockchain_sim import Block, Blockchain, Transaction, Wallet

LOW_DIFFICULTY = 2


class BlockHashTests(unittest.TestCase):
    def test_block_hash_is_deterministic(self):
        block_a = Block(index=1, timestamp=1000.0, transactions=[], previous_hash="a" * 64, nonce=5)
        block_b = Block(index=1, timestamp=1000.0, transactions=[], previous_hash="a" * 64, nonce=5)
        self.assertEqual(block_a.compute_hash(), block_b.compute_hash())

    def test_block_hash_changes_if_any_field_changes(self):
        base = Block(index=1, timestamp=1000.0, transactions=[], previous_hash="a" * 64, nonce=5)
        base_hash = base.compute_hash()

        variant_index = Block(index=2, timestamp=1000.0, transactions=[], previous_hash="a" * 64, nonce=5)
        variant_time = Block(index=1, timestamp=1234.0, transactions=[], previous_hash="a" * 64, nonce=5)
        variant_prev = Block(index=1, timestamp=1000.0, transactions=[], previous_hash="b" * 64, nonce=5)
        variant_nonce = Block(index=1, timestamp=1000.0, transactions=[], previous_hash="a" * 64, nonce=6)

        for variant in (variant_index, variant_time, variant_prev, variant_nonce):
            self.assertNotEqual(base_hash, variant.compute_hash())

    def test_block_hash_changes_if_transaction_amount_changes(self):
        wallet = Wallet()
        tx = wallet.create_transaction(Wallet().public_key_pem, 5.0)
        block = Block(index=1, timestamp=1000.0, transactions=[tx], previous_hash="a" * 64, nonce=0)
        original_hash = block.compute_hash()

        block.transactions[0].amount = 999.0
        self.assertNotEqual(original_hash, block.compute_hash())


class MiningTests(unittest.TestCase):
    def test_mining_produces_hash_meeting_difficulty(self):
        block = Block(index=1, timestamp=1000.0, transactions=[], previous_hash="0" * 64)
        block.mine(LOW_DIFFICULTY)
        self.assertTrue(block.hash.startswith("0" * LOW_DIFFICULTY))
        self.assertEqual(block.hash, block.compute_hash())

    def test_mining_hash_matches_recomputed_hash(self):
        block = Block(index=2, timestamp=2000.0, transactions=[], previous_hash="1" * 64)
        mined_hash = block.mine(LOW_DIFFICULTY)
        self.assertEqual(mined_hash, block.compute_hash())

    def test_higher_difficulty_requires_more_attempts_on_average(self):
        """Statistical sanity check: mining at a higher difficulty should take
        substantially more attempts on average than a lower one. Not a strict
        timing assertion -- just checks the expected exponential trend holds
        across several independent trials."""
        low_attempts = []
        high_attempts = []
        for i in range(6):
            low_block = Block(index=i, timestamp=1000.0 + i, transactions=[], previous_hash="0" * 64)
            low_block.mine(1)
            low_attempts.append(low_block.nonce + 1)

            high_block = Block(index=i, timestamp=2000.0 + i, transactions=[], previous_hash="0" * 64)
            high_block.mine(3)
            high_attempts.append(high_block.nonce + 1)

        avg_low = statistics.mean(low_attempts)
        avg_high = statistics.mean(high_attempts)
        self.assertGreater(
            avg_high, avg_low,
            f"expected difficulty=3 to need more attempts on average than difficulty=1 "
            f"(got avg_high={avg_high}, avg_low={avg_low})",
        )


class ChainValidationTests(unittest.TestCase):
    def setUp(self):
        self.chain = Blockchain(difficulty=LOW_DIFFICULTY)
        self.alice = Wallet()
        self.bob = Wallet()
        self.miner = Wallet()

    def _fund_alice(self, amount=100.0):
        self.chain.mine_pending_transactions(self.alice.public_key_pem, reward=amount)

    def test_valid_chain_passes_validation(self):
        self._fund_alice()
        tx = self.alice.create_transaction(self.bob.public_key_pem, 10.0)
        self.chain.add_transaction(tx)
        self.chain.mine_pending_transactions(self.miner.public_key_pem)

        valid, _ = self.chain.is_chain_valid()
        self.assertTrue(valid)

    def test_tampering_with_past_transaction_fails_validation(self):
        """The key security property: mutating a past block's transaction
        data directly (without recomputing hashes) must be caught."""
        self._fund_alice()
        tx = self.alice.create_transaction(self.bob.public_key_pem, 10.0)
        self.chain.add_transaction(tx)
        self.chain.mine_pending_transactions(self.miner.public_key_pem)

        valid_before, _ = self.chain.is_chain_valid()
        self.assertTrue(valid_before)

        # Tamper: directly edit a past block's transaction amount.
        self.chain.chain[1].transactions[0].amount = 1_000_000.0

        valid_after, reason = self.chain.is_chain_valid()
        self.assertFalse(valid_after)
        self.assertIn("hash", reason.lower())

    def test_broken_previous_hash_link_fails_validation(self):
        self._fund_alice()
        self.chain.mine_pending_transactions(self.miner.public_key_pem)
        last_block = self.chain.chain[-1]
        last_block.previous_hash = "f" * 64
        # Re-mine so the stored hash is internally consistent (hash check
        # passes) and difficulty is met -- isolating the broken-link check.
        last_block.mine(self.chain.difficulty)
        valid, reason = self.chain.is_chain_valid()
        self.assertFalse(valid)
        self.assertIn("previous_hash", reason)

    def test_block_not_meeting_difficulty_fails_validation(self):
        self._fund_alice()
        block = self.chain.chain[-1]
        # Force the stored hash/nonce to something that doesn't meet difficulty,
        # while keeping compute_hash() consistent with the stored hash.
        block.nonce = 0
        block.hash = block.compute_hash()
        if block.hash.startswith("0" * LOW_DIFFICULTY):
            block.nonce = 1
            block.hash = block.compute_hash()
        valid, reason = self.chain.is_chain_valid()
        self.assertFalse(valid)
        self.assertIn("difficulty", reason)


class TransactionSignatureTests(unittest.TestCase):
    def setUp(self):
        self.alice = Wallet()
        self.bob = Wallet()

    def test_valid_signature_is_accepted(self):
        tx = self.alice.create_transaction(self.bob.public_key_pem, 5.0)
        self.assertTrue(tx.is_valid())

    def test_forged_signature_is_rejected(self):
        tx = self.alice.create_transaction(self.bob.public_key_pem, 5.0)
        forger = Wallet()
        # Forger signs the same payload with their own (wrong) key.
        tx.signature = forger.sign(tx.signing_payload())
        self.assertFalse(tx.is_valid())

    def test_unsigned_transaction_is_rejected(self):
        tx = Transaction(self.alice.public_key_pem, self.bob.public_key_pem, 5.0)
        self.assertIsNone(tx.signature)
        self.assertFalse(tx.is_valid())

    def test_tampered_amount_after_signing_is_rejected(self):
        tx = self.alice.create_transaction(self.bob.public_key_pem, 5.0)
        self.assertTrue(tx.is_valid())
        tx.amount = 5000.0
        self.assertFalse(tx.is_valid())

    def test_tampered_recipient_after_signing_is_rejected(self):
        tx = self.alice.create_transaction(self.bob.public_key_pem, 5.0)
        mallory = Wallet()
        tx.recipient_public_key = mallory.public_key_pem
        self.assertFalse(tx.is_valid())

    def test_coinbase_transaction_valid_without_signature(self):
        coinbase = Transaction(sender_public_key=None, recipient_public_key=self.alice.public_key_pem, amount=100.0)
        self.assertTrue(coinbase.is_valid())


class BalanceAndDoubleSpendTests(unittest.TestCase):
    def setUp(self):
        self.chain = Blockchain(difficulty=LOW_DIFFICULTY)
        self.alice = Wallet()
        self.bob = Wallet()
        self.carol = Wallet()
        self.miner = Wallet()

    def test_balance_correct_across_multiple_transactions(self):
        self.chain.mine_pending_transactions(self.alice.public_key_pem, reward=100.0)
        tx1 = self.alice.create_transaction(self.bob.public_key_pem, 30.0)
        tx2 = self.alice.create_transaction(self.carol.public_key_pem, 20.0)
        self.chain.add_transaction(tx1)
        self.chain.add_transaction(tx2)
        self.chain.mine_pending_transactions(self.miner.public_key_pem, reward=100.0)

        self.assertEqual(self.chain.get_balance(self.alice.address), 50.0)
        self.assertEqual(self.chain.get_balance(self.bob.address), 30.0)
        self.assertEqual(self.chain.get_balance(self.carol.address), 20.0)
        self.assertEqual(self.chain.get_balance(self.miner.address), 100.0)

    def test_double_spend_rejected_for_insufficient_balance(self):
        self.chain.mine_pending_transactions(self.alice.public_key_pem, reward=10.0)
        overdraft_tx = self.alice.create_transaction(self.bob.public_key_pem, 999.0)
        with self.assertRaises(ValueError):
            self.chain.add_transaction(overdraft_tx)

    def test_double_spend_rejected_against_own_pending_transactions(self):
        self.chain.mine_pending_transactions(self.alice.public_key_pem, reward=10.0)
        tx1 = self.alice.create_transaction(self.bob.public_key_pem, 8.0)
        self.chain.add_transaction(tx1)
        # Alice only has 2 left; trying to spend another 8 should fail even
        # though the mined chain alone would say she has 10.
        tx2 = self.alice.create_transaction(self.carol.public_key_pem, 8.0)
        with self.assertRaises(ValueError):
            self.chain.add_transaction(tx2)

    def test_non_positive_amount_rejected(self):
        self.chain.mine_pending_transactions(self.alice.public_key_pem, reward=10.0)
        bad_tx = self.alice.create_transaction(self.bob.public_key_pem, -5.0)
        with self.assertRaises(ValueError):
            self.chain.add_transaction(bad_tx)

    def test_invalid_signature_transaction_rejected_by_chain(self):
        self.chain.mine_pending_transactions(self.alice.public_key_pem, reward=10.0)
        tx = self.alice.create_transaction(self.bob.public_key_pem, 5.0)
        tx.amount = 6.0  # tamper after signing -> invalid signature
        with self.assertRaises(ValueError):
            self.chain.add_transaction(tx)


class WalletTests(unittest.TestCase):
    def test_address_deterministic_for_same_keypair(self):
        wallet = Wallet()
        same_key_wallet = Wallet(private_key=wallet.private_key)
        self.assertEqual(wallet.address, same_key_wallet.address)
        self.assertEqual(wallet.public_key_pem, same_key_wallet.public_key_pem)

    def test_address_differs_for_different_keypairs(self):
        wallet_a = Wallet()
        wallet_b = Wallet()
        self.assertNotEqual(wallet_a.address, wallet_b.address)

    def test_address_matches_static_derivation_helper(self):
        wallet = Wallet()
        derived = Wallet.address_from_public_key_pem(wallet.public_key_pem)
        self.assertEqual(wallet.address, derived)


if __name__ == "__main__":
    unittest.main()
