"""Transactions: sender/recipient public keys, amount, and an ECDSA signature.

Signature verification uses the `cryptography` package's ECDSA support. A
transaction with `sender_public_key is None` is a "coinbase" (mining-reward)
transaction minted by the network itself, and is valid by definition as long
as it carries no signature -- there is no private key to sign with.
"""

import hashlib
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


class Transaction:
    def __init__(self, sender_public_key, recipient_public_key, amount,
                 timestamp=None, signature=None):
        self.sender_public_key = sender_public_key  # PEM str, or None for coinbase
        self.recipient_public_key = recipient_public_key  # PEM str
        self.amount = float(amount)
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.signature = signature  # hex str, or None

    # -- Addresses -----------------------------------------------------

    @property
    def sender_address(self) -> str:
        if self.sender_public_key is None:
            return "NETWORK"
        return hashlib.sha256(self.sender_public_key.encode("ascii")).hexdigest()

    @property
    def recipient_address(self) -> str:
        return hashlib.sha256(self.recipient_public_key.encode("ascii")).hexdigest()

    # -- Signing / verification -----------------------------------------

    def signing_payload(self) -> bytes:
        """Canonical bytes that get signed -- everything except the signature
        itself. Changing any of these fields after signing invalidates the
        signature."""
        payload = f"{self.sender_public_key}|{self.recipient_public_key}|{self.amount!r}|{self.timestamp!r}"
        return payload.encode("utf-8")

    def sign(self, wallet) -> None:
        if wallet.public_key_pem != self.sender_public_key:
            raise ValueError("Wallet's public key does not match transaction sender")
        self.signature = wallet.sign(self.signing_payload())

    def is_valid(self) -> bool:
        """Coinbase transactions (no sender) are valid iff unsigned. Regular
        transactions are valid iff the signature verifies against the
        sender's public key over the exact current contents of the
        transaction -- so any post-signing tampering (amount, recipient,
        timestamp) is caught here."""
        if self.sender_public_key is None:
            return self.signature is None

        if not self.signature:
            return False

        try:
            public_key = serialization.load_pem_public_key(
                self.sender_public_key.encode("ascii")
            )
            public_key.verify(
                bytes.fromhex(self.signature),
                self.signing_payload(),
                ec.ECDSA(hashes.SHA256()),
            )
            return True
        except (InvalidSignature, ValueError):
            return False

    # -- Serialization ----------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "sender_public_key": self.sender_public_key,
            "recipient_public_key": self.recipient_public_key,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "signature": self.signature,
        }

    @staticmethod
    def from_dict(data: dict) -> "Transaction":
        return Transaction(
            sender_public_key=data["sender_public_key"],
            recipient_public_key=data["recipient_public_key"],
            amount=data["amount"],
            timestamp=data["timestamp"],
            signature=data["signature"],
        )

    def __repr__(self) -> str:
        sender = self.sender_address[:8] if self.sender_public_key else "NETWORK"
        return f"Transaction({sender}->{self.recipient_address[:8]}, amount={self.amount})"
