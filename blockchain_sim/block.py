"""Block structure and proof-of-work mining.

Each block hashes its own contents (index, timestamp, transactions,
previous_hash, nonce) with SHA-256. Mining searches for a `nonce` such that
the resulting hash has at least `difficulty` leading hexadecimal zero
characters -- each hex character is 4 bits, so difficulty N means the hash
must fall below 16^-N of the hash space, and average mining attempts scale
as roughly 16^N.
"""

import hashlib
import json


class Block:
    def __init__(self, index, timestamp, transactions, previous_hash, nonce=0):
        self.index = index
        self.timestamp = timestamp
        self.transactions = list(transactions)  # list[Transaction]
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        """SHA-256 hash of the block's contents. Deterministic: identical
        fields always produce the identical hash, and changing any field
        (even a single transaction's amount) changes the hash."""
        block_content = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
        block_string = json.dumps(block_content, sort_keys=True, default=repr)
        return hashlib.sha256(block_string.encode("utf-8")).hexdigest()

    def mine(self, difficulty: int) -> str:
        """Proof-of-work: increment nonce until compute_hash() has
        `difficulty` leading hex zeros. Returns the winning hash."""
        target_prefix = "0" * difficulty
        self.nonce = 0
        self.hash = self.compute_hash()
        while not self.hash.startswith(target_prefix):
            self.nonce += 1
            self.hash = self.compute_hash()
        return self.hash

    def meets_difficulty(self, difficulty: int) -> bool:
        return self.hash.startswith("0" * difficulty)

    def __repr__(self) -> str:
        return (
            f"Block(index={self.index}, hash={self.hash[:12]}..., "
            f"prev={self.previous_hash[:12]}..., nonce={self.nonce}, "
            f"txs={len(self.transactions)})"
        )
