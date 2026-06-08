#!/usr/bin/env -S uv run
# /// script
# dependencies = ["fints"]
# ///
"""Probe FinTS SCA flows for banks that do not answer normal read operations cleanly."""

from __future__ import annotations

import argparse
import getpass
import logging
from datetime import date, timedelta
from typing import Any

from fints.client import FinTS3PinTanClient, NeedTANResponse
from fints.models import SEPAAccount
from fints.segments.accounts import HKSPA1
from fints.segments.journal import HKPRO3, HKPRO4
from fints.segments.saldo import HKSAL5, HKSAL6, HKSAL7
from fints.segments.statement import HKKAZ5, HKKAZ6, HKKAZ7


def _accounts_from_information(info: dict[str, Any]) -> list[SEPAAccount]:
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


def _print_responses(response: Any, command_seg: Any, tan_seg: Any | None) -> None:
    if tan_seg is not None:
        tan_responses = list(response.responses(tan_seg))
        print(f"  TAN responses: {[f'{resp.code} {resp.text}' for resp in tan_responses]}")
    cmd_responses = list(response.responses(command_seg))
    print(f"  Command responses: {[f'{resp.code} {resp.text}' for resp in cmd_responses]}")
    hitan = response.find_segment_first("HITAN")
    if hitan is None:
        print("  HITAN: none")
    else:
        print(f"  HITAN: {hitan!r}")


def _probe_operation(client: FinTS3PinTanClient, label: str, command_seg: Any) -> None:
    print(f"\n== {label} ==")
    with client._get_dialog() as dialog:
        tan_seg = client._get_tan_segment(command_seg, "4")
        response = dialog.send(command_seg, tan_seg)
        _print_responses(response, command_seg, tan_seg)

        for resp in response.responses(tan_seg):
            if resp.code in ("0030", "3955"):
                challenge = NeedTANResponse(
                    command_seg,
                    response.find_segment_first("HITAN"),
                    None,
                    client.is_challenge_structured(),
                    resp.code == "3955",
                )
                print(f"  NeedTANResponse.decoupled={challenge.decoupled}")
                print(f"  NeedTANResponse.challenge={challenge.challenge!r}")
                print(f"  NeedTANResponse.challenge_raw={challenge.challenge_raw!r}")
                return


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe FinTS TAN flows")
    parser.add_argument("--blz", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--customer-id")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--pin")
    parser.add_argument(
        "--mechanism",
        action="append",
        dest="mechanisms",
        help="Security function to test (defaults to all bank-advertised mechanisms)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable python-fints debug logging",
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger("urllib3").setLevel(logging.INFO)
        logging.getLogger("fints").setLevel(logging.DEBUG)

    pin = args.pin or getpass.getpass("PIN: ")
    customer_id = args.customer_id or args.username

    seed_client = FinTS3PinTanClient(
        args.blz,
        args.username,
        pin,
        args.endpoint,
        customer_id=customer_id,
        product_id=args.product_id,
    )
    seed_client.fetch_tan_mechanisms()
    with seed_client:
        info = seed_client.get_information()
    accounts = _accounts_from_information(info)

    print(f"Found {len(accounts)} fallback account(s)")
    for account in accounts:
        print(f"  {account.iban} {account.accountnumber} {account.subaccount}")

    advertised = list(seed_client.get_tan_mechanisms().keys())
    mechanisms = args.mechanisms or advertised
    print(f"Advertised mechanisms: {advertised}")
    print(f"Testing mechanisms: {mechanisms}")

    for mechanism in mechanisms:
        print(f"\n######## mechanism {mechanism} ########")
        client = FinTS3PinTanClient(
            args.blz,
            args.username,
            pin,
            args.endpoint,
            customer_id=customer_id,
            product_id=args.product_id,
        )
        client.fetch_tan_mechanisms()
        client.set_tan_mechanism(mechanism)
        print(f"Current mechanism: {client.get_current_tan_mechanism()}")

        try:
            with client:
                _probe_operation(client, "HKSPA", HKSPA1())
        except Exception as exc:
            print(f"HKSPA probe error: {type(exc).__name__}: {exc}")

        if not accounts:
            continue

        try:
            with client._get_dialog() as dialog:
                hksal_cls = client._find_highest_supported_command(HKSAL5, HKSAL6, HKSAL7)
                seg = hksal_cls(
                    account=hksal_cls._fields["account"].type.from_sepa_account(accounts[0]),
                    all_accounts=False,
                )
                _probe_operation(client, "HKSAL", seg)
        except Exception as exc:
            print(f"HKSAL probe error: {type(exc).__name__}: {exc}")

        try:
            hkkaz_cls = client._find_highest_supported_command(HKKAZ5, HKKAZ6, HKKAZ7)
            seg = hkkaz_cls(
                account=hkkaz_cls._fields["account"].type.from_sepa_account(accounts[0]),
                all_accounts=False,
                date_start=date.today() - timedelta(days=7),
                date_end=date.today(),
                touchdown_point=None,
            )
            _probe_operation(client, "HKKAZ", seg)
        except Exception as exc:
            print(f"HKKAZ probe error: {type(exc).__name__}: {exc}")

        try:
            hkpro_cls = client._find_highest_supported_command(HKPRO3, HKPRO4)
            _probe_operation(client, "HKPRO", hkpro_cls(touchdown_point=None))
        except Exception as exc:
            print(f"HKPRO probe error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
