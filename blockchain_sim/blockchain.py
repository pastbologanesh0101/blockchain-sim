"""The chain itself: genesis block, mining, balances, and full validation."""

import time

from .block import Block
from .transaction import Transaction


class Blockchain:
    def __init__(self, difficulty: int = 4):
        self.difficulty = difficulty
        self.pending_transactions = []
        self.chain = [self._create_genesis_block()]

    def _create_genesis_block(self) -> Block:
        genesis = Block(index=0, timestamp=time.time(), transactions=[], previous_hash="0" * 64)
        genesis.mine(self.difficulty)
        return genesis

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    # -- Balances / double-spend protection --------------------------------

    def get_balance(self, address: str) -> float:
        """balance = sum(received) - sum(sent), across every block in the
        chain. No UTXO set -- just a running tally derived from history."""
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx.recipient_address == address:
                    balance += tx.amount
                if tx.sender_public_key is not None and tx.sender_address == address:
                    balance -= tx.amount
        return balance

    def add_transaction(self, transaction: Transaction) -> Transaction:
        """Validate and queue a transaction. Rejects: unsigned/forged/tampered
        signatures, non-positive amounts, and double-spends (sender's
        confirmed balance minus already-pending outgoing amounts can't cover
        this transaction)."""
        if transaction.sender_public_key is None:
            raise ValueError("Coinbase transactions cannot be submitted manually")

        if not transaction.is_valid():
            raise ValueError("Cannot add transaction: invalid or missing signature")

        if transaction.amount <= 0:
            raise ValueError("Transaction amount must be positive")

        balance = self.get_balance(transaction.sender_address)
        already_pending = sum(
            t.amount for t in self.pending_transactions
            if t.sender_public_key is not None and t.sender_address == transaction.sender_address
        )
        if balance - already_pending < transaction.amount:
            raise ValueError(
                f"Cannot add transaction: insufficient balance "
                f"(available {balance - already_pending}, requested {transaction.amount}) "
                f"-- double-spend rejected"
            )

        self.pending_transactions.append(transaction)
        return transaction

    # -- Mining -------------------------------------------------------------

    def mine_pending_transactions(self, miner_public_key_pem: str, reward: float = 10.0) -> Block:
        """Mine a new block containing all pending transactions plus a
        coinbase reward transaction paid to the miner."""
        reward_tx = Transaction(
            sender_public_key=None,
            recipient_public_key=miner_public_key_pem,
            amount=reward,
        )
        block_transactions = self.pending_transactions + [reward_tx]
        block = Block(
            index=len(self.chain),
            timestamp=time.time(),
            transactions=block_transactions,
            previous_hash=self.last_block.hash,
        )
        block.mine(self.difficulty)
        self.chain.append(block)
        self.pending_transactions = []
        return block

    # -- Validation -----------------------------------------------------------

    def is_chain_valid(self):
        """Full validation: every block's hash matches its recomputed hash,
        every block links to the previous block's hash, every block's
        proof-of-work meets difficulty, and every transaction's signature is
        valid. Returns (bool, reason)."""
        for i, block in enumerate(self.chain):
            if block.hash != block.compute_hash():
                return False, f"Block {i}: stored hash does not match recomputed hash (data tampered)"

            if not block.meets_difficulty(self.difficulty):
                return False, f"Block {i}: proof-of-work does not meet difficulty {self.difficulty}"

            if i > 0 and block.previous_hash != self.chain[i - 1].hash:
                return False, f"Block {i}: previous_hash does not match hash of block {i - 1}"

            for j, tx in enumerate(block.transactions):
                if not tx.is_valid():
                    return False, f"Block {i}, transaction {j}: invalid signature"

        return True, "Chain is valid"
