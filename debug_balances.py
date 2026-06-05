#!/usr/bin/env -S uv run
# /// script
# dependencies = ["fints"]
# ///
"""Debug script: connects to a FinTS endpoint and prints accounts + balances."""

import argparse
import getpass

from fints.client import FinTS3PinTanClient
from fints.utils import minimal_interactive_cli_bootstrap


def main() -> None:
    parser = argparse.ArgumentParser(description="List FinTS account balances")
    parser.add_argument("--blz", required=True, help="Bank routing number (BLZ)")
    parser.add_argument("--username", required=True, help="Username / customer number")
    parser.add_argument("--endpoint", required=True, help="FinTS endpoint URL")
    parser.add_argument("--product-id", required=True, help="FinTS product ID (Produktkennung)")
    parser.add_argument("--pin", help="PIN (prompted interactively if omitted)")
    args = parser.parse_args()

    pin = args.pin or getpass.getpass("PIN: ")

    client = FinTS3PinTanClient(
        args.blz,
        args.username,
        pin,
        args.endpoint,
        product_id=args.product_id,
    )

    minimal_interactive_cli_bootstrap(client)

    with client:
        accounts = client.get_sepa_accounts()
        print(f"Found {len(accounts)} account(s):\n")
        for acc in accounts:
            print(f"  IBAN: {acc.iban}")
            try:
                balance = client.get_balance(acc)
                print(f"  Balance: {balance.amount.amount} {balance.amount.currency}")
            except Exception as e:
                print(f"  Balance: (error: {e})")
            print()


if __name__ == "__main__":
    main()
