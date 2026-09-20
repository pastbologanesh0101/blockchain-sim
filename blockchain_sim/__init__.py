"""Blockchain Simulator.

A from-scratch blockchain implementation featuring:
- SHA-256 block hashing and chain-linking
- Proof-of-work mining with configurable difficulty
- ECDSA-signed transactions (via the audited `cryptography` package)
- Wallets with address derivation
- Full chain validation (hashes, links, proof-of-work, signatures)
- A simple balance model with double-spend rejection
"""

from .wallet import Wallet
from .transaction import Transaction
from .block import Block
from .blockchain import Blockchain

__all__ = ["Wallet", "Transaction", "Block", "Blockchain"]
