# Inbox Zero

**Self-hosted AI email assistant for IMAP, Gmail and Outlook inside Home Assistant.**

[![Validate Inbox Zero](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate-inbox-zero.yml/badge.svg?branch=main)](https://github.com/HyperCriSiS/Home-Assistant-Apps/actions/workflows/validate-inbox-zero.yml)
[![Inbox Zero version](https://img.shields.io/badge/Inbox%20Zero-v2.30.0%20(a08ec63)-6E56CF)](https://github.com/HyperCriSiS/inbox-zero/commit/a08ec63f0c09739e49385134d6a17a176be43683)
![Architecture amd64](https://img.shields.io/badge/amd64-supported-success)
![Architecture aarch64](https://img.shields.io/badge/aarch64-supported-success)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-App-41BDF5?logo=homeassistant&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

This Home Assistant App runs [Inbox Zero](https://github.com/HyperCriSiS/inbox-zero), an AI assistant that sorts, labels and drafts replies to your email. It packages the fork with IMAP/SMTP and CalDAV support, so it works with any mailbox and needs neither a Google nor a Microsoft developer account. PostgreSQL, Redis and the scheduler run inside the App; nothing else has to be installed.

> [!IMPORTANT]
> Home Assistant Apps require **Home Assistant OS** or a **Supervised** installation. Older Home Assistant versions may still use the term **Add-ons** instead of **Apps**.

> [!IMPORTANT]
> Inbox Zero is licensed under the AGPL-3.0 with additional terms: no commercial resale, and organizations with five or more business users need an enterprise license from Inbox Zero Inc. See [LICENSE-INBOX-ZERO](LICENSE-INBOX-ZERO).

## Installation

### Stable

[![Add stable repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FHyperCriSiS%2FHome-Assistant-Apps)

```text
https://github.com/HyperCriSiS/Home-Assistant-Apps
```

1. Add the stable repository using the button above.
2. Install **Inbox Zero** from the App store.
3. Open the **Configuration** tab and set the three required values described under [First start](#first-start).
4. Start the App and choose **Open Web UI**.

### Development testing

To test the current `dev-inbox-zero` candidate before it is promoted to `main`, add the shared generated
development store:

[![Add development repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FHyperCriSiS%2FHome-Assistant-Apps%23dev-store)

```text
https://github.com/HyperCriSiS/Home-Assistant-Apps#dev-store
```

The development App is shown as **Inbox Zero (Dev)** under
**HyperCriSiS Apps (Dev)**, so it can be distinguished from the stable App at a glance.

> [!WARNING]
> Development builds may contain breaking changes. Create a Home Assistant backup before
> testing a development update.

## First start

The App does not start until these options are set:

1. **Address of Inbox Zero** (`base_url`): the address you will open in the browser, for example `http://homeassistant.local:3000` or `http://192.168.1.10:3000`. Sign-in only works on exactly this address.
2. **Models** (`llm.default_models`) and, for a hosted provider, **API key** (`llm.api_key`), for example `openai:gpt-6-luna` or `ollama:qwen3.5:4b`.
3. **Allowed email addresses** (`auth.allowed_emails`): the addresses that may create an account with a password.

Then open the web interface, sign up with one of the allowed addresses and add a mailbox under **Accounts** with **Add other mail account (IMAP)**. The first start takes about a minute because the database is created and migrated.

## Access

Inbox Zero cannot be embedded in the Home Assistant sidebar: it forbids being shown in a frame and cannot run under a path prefix. It is therefore reached on its own port, `3000` by default, and protected by its own sign-in.

> [!TIP]
> For access from outside your network, put a reverse proxy with TLS in front of port `3000` and set `base_url` to the public `https://` address. Never forward the port to the internet without TLS. Gmail and Outlook push notifications need such a public address; IMAP mailboxes do not.

## Configuration

All options are described in [DOCS.md](DOCS.md), which Home Assistant also shows in the **Documentation** tab.

## Data and backups

Everything is stored in the App data volume: the PostgreSQL database with accounts, rules and encrypted mailbox credentials, and the generated secrets that encrypt them. Home Assistant backups include both. The App uses **cold backups**: Home Assistant stops Inbox Zero briefly while the backup is created, so the database files are captured in a consistent state. Redis holds only caches and short-lived queues and is not persisted.

Database migrations run at every start. A downgrade across migrations is not supported, so a rollback means restoring the Home Assistant backup taken before the update.

## Troubleshooting

- Review the App logs under **Settings → Apps → Inbox Zero → Logs**. A missing required option is reported there in one line.
- If sign-in redirects to a wrong address or fails without a message, `base_url` does not match the address in the browser.
- If a mail server in your own network is rejected, enable **Allow servers in the local network**.
- If the App runs out of memory on a small device, keep in mind that it runs a Next.js server, PostgreSQL and Redis; plan for about 2 GB of free RAM.

## Support

For App-specific issues, use the [issue tracker](https://github.com/HyperCriSiS/Home-Assistant-Apps/issues). For Inbox Zero itself, see the [packaged fork](https://github.com/HyperCriSiS/inbox-zero) and the [upstream project](https://github.com/elie222/inbox-zero).

## License

This App packaging is licensed under the MIT License. Inbox Zero and the other packaged components keep their own licenses, listed in [NOTICE.md](NOTICE.md).
