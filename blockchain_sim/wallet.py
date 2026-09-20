"""Wallets: ECDSA keypairs, address derivation, and transaction signing.

We use the real, audited `cryptography` package for the elliptic-curve
digital-signature primitive (ECDSA over SECP256K1) rather than hand-rolling
elliptic-curve math -- the same principle as leaning on a vetted library for
AES instead of writing your own block cipher.
"""

import hashlib

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .transaction import Transaction


class Wallet:
    """An ECDSA keypair plus a derived address, able to sign transactions."""

    CURVE = ec.SECP256K1()

    def __init__(self, private_key=None):
        self.private_key = private_key or ec.generate_private_key(self.CURVE)
        self.public_key = self.private_key.public_key()

    @property
    def public_key_pem(self) -> str:
        """PEM-encoded public key -- this is the 'sender/recipient public key'
        that goes into transactions."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    @property
    def address(self) -> str:
        """Deterministic wallet address: SHA-256 hash of the public key."""
        return self.address_from_public_key_pem(self.public_key_pem)

    @staticmethod
    def address_from_public_key_pem(public_key_pem: str) -> str:
        return hashlib.sha256(public_key_pem.encode("ascii")).hexdigest()

    def sign(self, data: bytes) -> str:
        """Sign raw bytes with this wallet's private key. Returns hex signature."""
        signature = self.private_key.sign(data, ec.ECDSA(hashes.SHA256()))
        return signature.hex()

    def create_transaction(self, recipient_public_key_pem: str, amount: float) -> Transaction:
        """Build and sign a transaction sending `amount` to a recipient."""
        tx = Transaction(
            sender_public_key=self.public_key_pem,
            recipient_public_key=recipient_public_key_pem,
            amount=amount,
        )
        tx.sign(self)
        return tx
