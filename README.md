# FinTS for Home Assistant

`fints` is a Home Assistant custom integration that connects to your bank via the [FinTS/HBCI](https://www.hbci-zka.de/) protocol and exposes account balances as sensor entities.

Features:

- supports multiple bank connections through config entries
- creates one Home Assistant device per bank connection
- creates one balance sensor per account (IBAN)
- reconfigurable from the UI without restarting Home Assistant
- raises a repair issue when authentication fails (e.g. stale web session)

## Requirements

### FinTS product ID (Produktkennung)

Many German banks require a registered **FinTS product ID** before you can use third-party HBCI/FinTS clients. You must request one from your bank:

- **ING**: Register at the [ING developer portal](https://www.ing.de/baufinanzierung/ing-developer/) or via customer service.
- **Other banks**: Check your bank's FinTS/HBCI documentation.

### ING: periodic web re-authentication

ING periodically suspends FinTS access and requires you to log into [ing.de](https://www.ing.de) via browser to re-enable it. When this happens, the integration raises a repair issue in Home Assistant. Simply log into your ING account via the web, then reload the integration.

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=pschmitt&repository=homeassistant-fints&category=integration)

1. Click the badge above, or open HACS and add `https://github.com/pschmitt/homeassistant-fints` as a custom repository of type **Integration**.
2. Install **FinTS**.
3. Restart Home Assistant.

### Manual

Copy `custom_components/fints` from this repository into your Home Assistant `custom_components/` directory, then restart.

## Configuration

The integration is configured from the Home Assistant UI:

1. Go to **Settings → Devices & services**.
2. Click **Add integration** and search for **FinTS**.
3. Fill in:
   - **BLZ** — your bank's 8-digit routing number (e.g. `50010517` for ING)
   - **Username / Customer number** — your online banking login
   - **PIN** — your online banking PIN
   - **FinTS endpoint URL** — your bank's FinTS server (e.g. `https://fints.ing.de/fints`)
   - **Product ID** — your registered FinTS product ID (Produktkennung)
   - **Name** — optional display name (defaults to the BLZ)

## Common FinTS endpoints

| Bank | BLZ | Endpoint |
|------|-----|----------|
| ING | 50010517 | `https://fints.ing.de/fints` |
| Deutsche Bank | 20070000 | `https://meine.deutsche-bank.de/pfpd` |
| Commerzbank | 20040000 | `https://fints.commerzbank.de/` |
| Sparkasse (varies) | — | check your Sparkasse's website |

## Entity model

- **Device**: one per configured bank connection
- **Entity**: one `sensor` per account IBAN
- **State**: the current account balance (e.g. `179.29`)
- **Unit**: the account currency (e.g. `EUR`)
- **Attributes**: `iban`, `bic`, `account_number`

## Options

After setup, click **Configure** on the integration entry to adjust:

- **Update interval** — how often to poll (default: 3600 s / 1 hour, minimum: 300 s)

## Branding

This repository bundles bank-related assets for display purposes. All integration code is GPL-3.0 licensed.
