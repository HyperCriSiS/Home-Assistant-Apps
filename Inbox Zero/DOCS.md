# Inbox Zero documentation

## Getting started

1. Set `base_url`, `llm.default_models` (with `llm.api_key` for a hosted provider) and `auth.allowed_emails`.
2. Start the App. The first start creates and migrates the database and takes about a minute.
3. Choose **Open Web UI**, sign up with an allowed address and a password.
4. Under **Accounts**, choose **Add other mail account (IMAP)** and pick a preset or enter the server settings.

Inbox Zero is opened on its own port, not through the Home Assistant sidebar, and is protected by its own sign-in.

## Options

```yaml
base_url: "http://homeassistant.local:3000"
llm:
  default_models: "openai:gpt-6-luna"
  api_key: "sk-..."
auth:
  allowed_emails: "me@example.com"
google:
  client_id: ""
  client_secret: ""
  pubsub_topic_name: ""
  pubsub_verification_token: ""
microsoft:
  client_id: ""
  client_secret: ""
  tenant_id: "common"
imap:
  allow_private_hosts: false
  allow_plaintext: false
  idle_enabled: true
env_vars: []
```

### `base_url`

Default: `http://homeassistant.local:3000`. The address you open in the browser, without a trailing slash. Sign-in cookies and redirects are bound to it, so use the exact host name or IP address and the host port from the **Network** section. Behind a reverse proxy, set the public `https://` address.

### `llm.default_models`

Required, no default. An ordered list of `provider:model` entries separated by commas; the first is used, the others are fallbacks. Examples: `openai:gpt-6-luna`, `anthropic:claude-sonnet-5`, `google:gemini-3.8-flash`, `openrouter:anthropic/claude-sonnet-5`, `ollama:qwen3.5:4b`.

### `llm.api_key`

Default: empty. The API key of the provider in `llm.default_models`. Leave it empty for a local model. For Ollama, add `OLLAMA_BASE_URL` (for example `http://192.168.1.20:11434/api`) under `env_vars`.

### `auth.allowed_emails`

Default: empty. Comma-separated email addresses that may sign up with a password. Setting it enables password sign-in. The App refuses to start when this is empty and neither Google nor Microsoft is configured, because nobody could sign in.

### `google.client_id`, `google.client_secret`

Default: empty. OAuth client for Gmail accounts and Google sign-in. When empty, Google is hidden. Google requires a public `https://` address as `base_url`.

### `google.pubsub_topic_name`, `google.pubsub_verification_token`

Default: empty. Pub/Sub topic and the token of its push subscription, needed for Gmail push notifications.

### `microsoft.client_id`, `microsoft.client_secret`, `microsoft.tenant_id`

Default: empty, empty, `common`. App registration for Outlook accounts and Microsoft sign-in. When the client ID is empty, Microsoft is hidden.

### `imap.allow_private_hosts`

Default: `false`. Allows IMAP, SMTP and CalDAV servers on private addresses, such as Proton Mail Bridge or a mail server in your network. This turns off the protection against requests into your network, so enable it only when you are the only user.

### `imap.allow_plaintext`

Default: `false`. Allows the security option `None` and `http://` CalDAV addresses, which send the password unencrypted.

### `imap.idle_enabled`

Default: `true`. Keeps one IMAP IDLE connection per mailbox open, so new mail is processed within seconds. When off, new mail is found by the poll that runs every minute.

### `env_vars`

Default: empty list. Further Inbox Zero environment variables as `name` and `value`, applied last so they override the options above. Example:

```yaml
env_vars:
  - name: OLLAMA_BASE_URL
    value: "http://192.168.1.20:11434/api"
  - name: REVIEW_BEFORE_DELETE_LABEL
    value: "To delete"
```

The variables are listed in the [environment reference](https://github.com/HyperCriSiS/inbox-zero/blob/main/apps/web/.env.example). Do not set the database, Redis or secret variables; the App manages them.

## Network

| Port | Purpose |
| --- | --- |
| `3000/tcp` | Web interface. When you change the host port, change it in `base_url` as well. |

PostgreSQL and Redis listen inside the container only and are not reachable from the network.

## Persistence and backups

| Container path | Content | In the App backup |
| --- | --- | --- |
| `/data/postgres` | PostgreSQL 16 database: users, mailboxes, rules, history | yes |
| `/data/secrets.env` | Generated secrets, including the key that encrypts mailbox credentials | yes |
| `/data/options.json` | The options above, written by Home Assistant | yes |

Backups are **cold**: Home Assistant stops the App while the backup is created. Redis keeps caches and short-lived queues in memory only. Without `/data/secrets.env`, stored mailbox credentials cannot be decrypted, so restore the backup as a whole.

## Troubleshooting

- **The App stops right after the start:** the log names the missing option, `llm.default_models` or `auth.allowed_emails`.
- **Sign-in fails or redirects to another address:** `base_url` must equal the address in the browser, including the port.
- **A mail server is rejected as private:** enable `imap.allow_private_hosts`.
- **"A required process exited" in the log:** the database, Redis or the web server stopped; the lines above it show which one. Home Assistant restarts the App.
- **After an update the App does not start:** restore the backup taken before the update and open an issue with the complete log.
