#!/usr/bin/env python3
"""Blockchain Simulator demo.

Creates a few wallets, mines several blocks with transactions between them,
prints balances, then tampers with a past block's transaction directly and
shows that full-chain validation correctly detects it.

Run with:  python demo.py
"""

from blockchain_sim import Blockchain, Wallet


def line(title=""):
    print()
    print(f"== {title} ==" if title else "-" * 60)


def print_balances(chain, wallets):
    for name, wallet in wallets.items():
        print(f"  {name:8s} ({wallet.address[:12]}...): {chain.get_balance(wallet.address):.2f}")


def main():
    DIFFICULTY = 4  # 4 leading hex zeros -- fast enough for a live demo
    chain = Blockchain(difficulty=DIFFICULTY)

    alice = Wallet()
    bob = Wallet()
    carol = Wallet()
    miner = Wallet()
    wallets = {"Alice": alice, "Bob": bob, "Carol": carol, "Miner": miner}

    line("Wallets created")
    for name, w in wallets.items():
        print(f"  {name:8s} address = {w.address}")

    line("Block 1: mined by Alice (earns the mining reward)")
    block1 = chain.mine_pending_transactions(alice.public_key_pem, reward=100.0)
    print(f"  {block1}")
    print_balances(chain, wallets)

    line("Alice sends 30 to Bob and 20 to Carol")
    tx1 = alice.create_transaction(bob.public_key_pem, 30.0)
    tx2 = alice.create_transaction(carol.public_key_pem, 20.0)
    chain.add_transaction(tx1)
    chain.add_transaction(tx2)
    print("  Queued 2 signed transactions in the pending pool.")

    line("Block 2: mined by Miner")
    block2 = chain.mine_pending_transactions(miner.public_key_pem, reward=100.0)
    print(f"  {block2}")
    print_balances(chain, wallets)

    line("Bob tries to send 1000 to Carol (double-spend attempt)")
    try:
        forged_amount_tx = bob.create_transaction(carol.public_key_pem, 1000.0)
        chain.add_transaction(forged_amount_tx)
    except ValueError as exc:
        print(f"  Rejected as expected: {exc}")

    line("Bob sends a legitimate 10 to Carol instead")
    tx3 = bob.create_transaction(carol.public_key_pem, 10.0)
    chain.add_transaction(tx3)
    block3 = chain.mine_pending_transactions(miner.public_key_pem, reward=100.0)
    print(f"  {block3}")
    print_balances(chain, wallets)

    line("Validating the chain BEFORE tampering")
    valid, reason = chain.is_chain_valid()
    print(f"  valid={valid} ({reason})")

    line("Tampering: directly editing a past transaction's amount")
    tampered_block = chain.chain[1]
    original_amount = tampered_block.transactions[0].amount
    tampered_block.transactions[0].amount = 9_999_999.0
    print(
        f"  Mutated block {tampered_block.index}'s first transaction amount "
        f"from {original_amount} to {tampered_block.transactions[0].amount} "
        f"WITHOUT recomputing the block hash (exactly what an attacker would do)."
    )

    line("Validating the chain AFTER tampering")
    valid, reason = chain.is_chain_valid()
    print(f"  valid={valid} ({reason})")
    assert not valid, "tamper detection failed!"
    print("  Tamper detection worked: the chain is correctly rejected.")


if __name__ == "__main__":
    main()
