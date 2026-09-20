# Blockchain Simulator

A small, from-scratch blockchain implementation in Python: proof-of-work
mining, ECDSA-signed transactions, wallets, and a full-chain validator that
detects tampering. The blockchain, mining, and consensus logic are all
hand-built here; the one piece intentionally *not* hand-rolled is the
elliptic-curve digital-signature math, which uses the real, audited
[`cryptography`](https://cryptography.io) package's ECDSA support — the same
principle as reaching for a vetted library for AES instead of writing your
own block cipher.

## Concepts

### Blocks and hashing

Each `Block` (see `blockchain_sim/block.py`) stores:

- `index` — position in the chain
- `timestamp` — when it was created
- `transactions` — the list of transactions it contains
- `previous_hash` — the hash of the block before it
- `nonce` — the number tweaked during mining
- `hash` — SHA-256 of everything above

`Block.compute_hash()` serializes those fields to canonical JSON and hashes
them with SHA-256. Because the hash covers *every* field, changing anything —
even one transaction's amount deep inside the block — produces a completely
different hash. Blocks link into a chain because each block's `previous_hash`
equals the prior block's `hash`; that link is what makes editing history
expensive: change a past block's data and its hash changes, which breaks the
link to the next block, and so on for every block after it.

### Proof-of-work mining

`Block.mine(difficulty)` repeatedly increments `nonce` and recomputes the
hash until the hash starts with `difficulty` hexadecimal zero characters.
Each hex character is 4 bits, so requiring `N` leading hex zeros means the
hash must land in the top `1 / 16^N` slice of the hash space. Since SHA-256
output is effectively random with respect to its input, there's no shortcut —
you have to search, and the *expected* number of attempts grows roughly as
`16^N`. That's why difficulty is the knob that controls how much real
computational work ("proof of work") went into producing a block, and why
this repo keeps difficulty low (2-4) for demos and tests: at difficulty 6+ a
single CPU core can take a very long time.

### Wallets and digital signatures

A `Wallet` (see `blockchain_sim/wallet.py`) generates an ECDSA keypair on the
SECP256K1 curve via `cryptography`. Its address is `SHA-256(public_key_pem)`
— deterministic and derivable by anyone who has the public key, but not
reversible to the private key.

A `Transaction` carries the sender's public key, the recipient's public key,
an amount, and a signature. Signing computes ECDSA-SHA256 over the exact
byte-serialization of `(sender, recipient, amount, timestamp)`; verifying
does the reverse. If *any* of those fields change after signing — amount,
recipient, timestamp — the signature no longer matches and `Transaction.is_valid()`
returns `False`. Transactions with no sender (`sender_public_key is None`)
are "coinbase" mining-reward transactions minted by the network and are only
ever created internally by `Blockchain.mine_pending_transactions()`.

### Chain validation (tamper detection)

`Blockchain.is_chain_valid()` walks every block and checks, in order:

1. The block's stored `hash` matches a fresh `compute_hash()` — catches any
   direct edit to a block's contents.
2. The block's hash meets the configured proof-of-work difficulty.
3. The block's `previous_hash` matches the actual hash of the prior block —
   catches a broken chain link.
4. Every transaction in the block has a valid signature.

If someone edits a past transaction's amount directly in memory (or in a
persisted chain file) without redoing the proof-of-work, check (1) fails
immediately at that block, and the chain is reported invalid from that point
on. `demo.py` shows exactly this.

### Balances and double-spend protection

There's no UTXO set here — balances are computed on demand:

```
balance(address) = sum(amounts received) - sum(amounts sent)
```

computed by scanning every transaction in every block of the (valid) chain.
`Blockchain.add_transaction()` rejects a transaction if the sender's
computed balance (minus anything they already have pending) can't cover the
amount — this is the double-spend check.

## Project layout

```
blockchain_sim/
  block.py        Block structure + proof-of-work mining
  transaction.py  Transactions + ECDSA sign/verify
  wallet.py        Keypair generation, address derivation, signing
  blockchain.py    Chain, balances, mining, full validation
demo.py            CLI demo (see below)
tests/             unittest suite
.github/workflows/tests.yml   CI (Python 3.11 & 3.12)
```

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the demo

```bash
python demo.py
```

The demo:

1. Creates four wallets (Alice, Bob, Carol, Miner).
2. Mines a block with Alice as the miner (she earns the block reward).
3. Has Alice send signed transactions to Bob and Carol, then mines a block
   including them.
4. Attempts an over-balance ("double-spend") transaction from Bob and shows
   it get rejected, then submits a legitimate one instead.
5. Validates the chain (passes).
6. **Tamper-detection demo:** directly mutates a past block's transaction
   amount in memory, *without* recomputing that block's hash — exactly what
   an attacker editing a stored chain would do — and re-validates the chain,
   which now correctly fails.

### Example output (abridged)

```
== Wallets created ==
  Alice    address = 73141b6135f560ea5f02fc49a2de67c031111795fe00cc8592d177f58d5df1a
  Bob      address = d5cf69bfd20c7122dc03dc10c8a34cb82a85c3cbcfe63773591eac72857866f
  ...

== Block 1: mined by Alice (earns the mining reward) ==
  Block(index=1, hash=0000c342c087..., prev=000058eb65c4..., nonce=300655, txs=1)
  Alice    : 100.00
  Bob      : 0.00
  ...

== Bob tries to send 1000 to Carol (double-spend attempt) ==
  Rejected as expected: Cannot add transaction: insufficient balance
  (available 30.0, requested 1000.0) -- double-spend rejected

== Validating the chain BEFORE tampering ==
  valid=True (Chain is valid)

== Tampering: directly editing a past transaction's amount ==
  Mutated block 1's first transaction amount from 100.0 to 9999999.0
  WITHOUT recomputing the block hash (exactly what an attacker would do).

== Validating the chain AFTER tampering ==
  valid=False (Block 1: stored hash does not match recomputed hash (data tampered))
  Tamper detection worked: the chain is correctly rejected.
```

## Running the tests

```bash
pip install pytest
pytest tests/ -v
```

The suite (24 tests) covers block hashing determinism, proof-of-work meeting
the difficulty target, valid and tampered chain validation (including the
key tamper-detection property), valid/forged/tampered-after-signing
signature rejection, double-spend rejection, multi-transaction balance
correctness, deterministic wallet-address derivation, and a statistical
check that mining at a higher difficulty needs more attempts on average than
a lower one. Test difficulty is kept at 1-3 hex zeros so the whole suite
runs in well under a second, both locally and in CI (`.github/workflows/tests.yml`,
which runs on Python 3.11 and 3.12).

## License

MIT — see [LICENSE](LICENSE).
