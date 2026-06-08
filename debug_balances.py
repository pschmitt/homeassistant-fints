#!/usr/bin/env -S uv run
# /// script
# dependencies = ["fints"]
# ///
"""Debug script: connects to a FinTS endpoint and prints accounts + balances."""

import argparse
import getpass

from fints.client import FinTS3PinTanClient
from fints.models import SEPAAccount


def _accounts_from_information(info: dict) -> list[SEPAAccount]:
    """Build SEPA accounts from UPD metadata when HKSPA is not usable."""
    accounts: list[SEPAAccount] = []
    for raw_account in info.get("accounts", []):
        iban = raw_account.get("iban")
        account_number = raw_account.get("account_number")
        bank_identifier = raw_account.get("bank_identifier")
        bank_code = getattr(bank_identifier, "bank_code", None)
        if not iban or not account_number or not bank_code:
            continue
        country = iban[:2] if len(iban) >= 2 else "DE"
        accounts.append(
            SEPAAccount(
                iban=iban,
                bic=raw_account.get("bic") or f"XXXX{country}XXX",
                accountnumber=account_number,
                subaccount=raw_account.get("subaccount_number") or "",
                blz=bank_code,
            )
        )
    return accounts


def main() -> None:
    parser = argparse.ArgumentParser(description="List FinTS account balances")
    parser.add_argument("--blz", required=True, help="Bank routing number (BLZ)")
    parser.add_argument("--username", required=True, help="Username / customer number")
    parser.add_argument(
        "--customer-id",
        help="Customer ID (defaults to username; useful for banks that require both to match)",
    )
    parser.add_argument("--endpoint", required=True, help="FinTS endpoint URL")
    parser.add_argument("--product-id", required=True, help="FinTS product ID (Produktkennung)")
    parser.add_argument("--tan-medium", help="Explicit TAN medium/device name if the bank requires one")
    parser.add_argument("--pin", help="PIN (prompted interactively if omitted)")
    args = parser.parse_args()

    pin = args.pin or getpass.getpass("PIN: ")

    client = FinTS3PinTanClient(
        args.blz,
        args.username,
        pin,
        args.endpoint,
        customer_id=args.customer_id or args.username,
        tan_medium=args.tan_medium,
        product_id=args.product_id,
    )
    client.fetch_tan_mechanisms()

    with client:
        info = client.get_information()
        try:
            accounts = client.get_sepa_accounts()
        except Exception as exc:
            print(f"HKSPA failed, falling back to UPD accounts: {exc}")
            accounts = _accounts_from_information(info)
        print(f"Found {len(accounts)} account(s):\n")
        for acc in accounts:
            print(f"  IBAN: {acc.iban}")
            try:
                balance = client.get_balance(acc)
                if balance is None:
                    print("  Balance: (no response)")
                else:
                    print(f"  Balance: {balance.amount.amount} {balance.amount.currency}")
            except Exception as e:
                print(f"  Balance: (error: {e})")
            print()


if __name__ == "__main__":
    main()
