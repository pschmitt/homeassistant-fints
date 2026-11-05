<p align="center">
  <img src="logo.png" width="128" alt="FinTS integration logo">
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/marketplace_repository/?owner=pschmitt&amp;repository=homeassistant-fints&amp;category=integration"><img src="https://my.home-assistant.io/badges/marketplace_repository.svg" alt="Open this integration in Home Assistant Marketplace"></a>
</p>

<h1 align="center">FinTS for Home Assistant</h1>

<p align="center">Read German bank account balances over FinTS/HBCI and expose them as Home Assistant sensors.</p>

## Features

- **Multiple banks:** Configure separate connections, each represented by a Home Assistant device.
- **Account balances:** Create one sensor per account IBAN, reporting the balance and currency.
- **UI management:** Reconfigure connections and polling interval without editing YAML.
- **Authentication repairs:** Raise a repair issue when a bank requires reauthentication. See [Bank setup](docs/bank-setup.md).

## Install

Use the Marketplace badge above on Home Assistant 2026.11 or later to add this
repository as a custom integration. On older versions, add it as a HACS
custom repository of type **Integration**. Install and restart Home Assistant.
The badge does not imply a public catalog listing. For manual installation,
copy `custom_components/fints/` into Home Assistant's `custom_components/`
directory and restart.

## Quick start

1. Obtain a FinTS product ID if your bank requires one; see [Bank setup](docs/bank-setup.md).
2. Add **FinTS** under **Settings → Devices & services → Add integration**.
3. Enter your bank's BLZ, login, PIN, FinTS endpoint and product ID; set a TAN medium if needed.
4. Inspect the resulting balance sensors.

## Documentation

| Topic | Description |
|-------|-------------|
| [Bank setup](docs/bank-setup.md) | Product IDs, reauthentication, endpoints and sensor details |

## License

[GPL-3.0](LICENSE). Bank-related assets remain the property of their owners.
