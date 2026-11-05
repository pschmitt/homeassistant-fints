# Bank setup

## FinTS product ID

Many German banks require a registered FinTS product ID (Produktkennung)
before third-party HBCI/FinTS clients can connect. Ask your bank how to obtain
one. ING offers registration through its
[developer portal](https://www.ing.de/baufinanzierung/ing-developer/) or
customer service.

## ING reauthentication

ING periodically suspends FinTS access until you log in at
[ing.de](https://www.ing.de) through a browser. The integration raises a
Home Assistant repair issue when this happens. Log in through ING's website
and reload the integration.

## Connection options

The Home Assistant config flow asks for your bank's eight-digit BLZ, online
banking username or customer number, PIN, FinTS endpoint URL, registered
product ID, and an optional TAN medium and display name. Configure the update
interval from the integration's **Configure** button (default 3600 seconds,
minimum 300 seconds).

| Bank | Example BLZ | Endpoint |
|------|-------------|----------|
| ING | 50010517 | `https://fints.ing.de/fints` |
| Deutsche Bank | 20070000 | `https://meine.deutsche-bank.de/pfpd` |
| Commerzbank | 20040000 | `https://fints.commerzbank.de/` |
| norisbank | 10077777 | `https://fints.norisbank.de` |
| Sparkasse | Varies | Check your Sparkasse's website |

Each configured bank connection appears as a Home Assistant device with one
balance sensor per account IBAN. The sensor state is the balance, its unit is
the account currency, and its attributes include `iban`, `bic` and
`account_number`.
