# ntrip-monitor

A lightweight, cross-platform monitoring system for **NTRIP casters**, designed to run continuously on low‑power Linux devices (including Raspberry Pi). It performs periodic availability checks, stores historical results, sends Telegram alerts on failures and recoveries, exports daily CSV logs, and provides a mobile‑friendly web dashboard with uptime statistics.

---

## Features

- Periodic NTRIP caster health checks (mountpoint list retrieval)
- Supports multiple casters with individual credentials
- SQLite database for persistent history
- Telegram push notifications (failure + recovery)
- Dynamic web UI to add/edit/delete casters
- Designed for Python 3 and systemd

---

## Supported Platforms

Tested or suitable for:

- Raspberry Pi OS (Lite or Desktop)
- Debian / Ubuntu / Linux Mint
- Alpine Linux (with Python installed)
- Fedora / Rocky / AlmaLinux
- Any Linux with Python ≥ 3.8

> ⚠️ Raspberry Pi 1 is supported but **performance is limited**. Keep caster count reasonable.

---

## Directory Layout

```
ntrip-monitor/
├── monitor.py          # Main monitoring loop
├── web_status.py       # Flask web dashboard
├── config.py           # Telegram + runtime configuration
├── init_db.py          # SQLite DB initilisation
├── monitor.db          # SQLite database (auto-created)
└── README.md
```

---

## System Requirements

- Python 3.8 or newer
- Internet access (outbound TCP 2101)
- SQLite (usually preinstalled)
- systemd (recommended but optional)

---

## Installing Dependencies

### Debian / Ubuntu / Raspberry Pi OS

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv sqlite3
```

### Alpine Linux

```bash
apk add python3 py3-pip sqlite
```

### Fedora / RHEL

```bash
sudo dnf install -y python3 python3-pip sqlite
```

### Python Packages

```bash
pip3 install flask requests
```

---

## Configuration

### 1. Telegram Bot

1. Create a bot using **@BotFather**
2. Record the **Bot Token**
3. Send a message to the bot
4. Get your Chat ID using **@userinfobot** or similar

### 2. `config.py`

Edit `config.py`:

```python
TELEGRAM_BOT_TOKEN = "123456:ABCDEF"
TELEGRAM_CHAT_ID = "987654321"

CHECK_INTERVAL = 300   # seconds (5 minutes)
CSV_DIR = "csv"
```

---

## Database Initialization

The database is created automatically on first run.

Tables:
- `casters` – active caster configuration
- `checks` – historical check results

No manual setup required.

---

## Running the Monitor

### Manual (for testing)

```bash
python3 monitor.py
```

### Web Dashboard

```bash
python3 web_status.py
```

Then visit:

```
http://<device-ip>:8080
```

---

## Running as a Service (Recommended)

### systemd Service Example

Create `/etc/systemd/system/ntrip-monitor.service`

```ini
[Unit]
Description=NTRIP Caster Monitor
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/ntrip-monitor/monitor.py
WorkingDirectory=/opt/ntrip-monitor
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable ntrip-monitor
sudo systemctl start ntrip-monitor
```

Check status:

```bash
sudo systemctl status ntrip-monitor
```

---

## Web UI – Caster Management

The web dashboard allows:

- Adding new casters
- Editing existing casters
- Deleting casters (history preserved)

Deleted casters stop being checked immediately but historical data remains.

---


## Security Notes

- No authentication on web UI by default
- Restrict access via firewall if exposed
- Telegram token grants message access only

---

## Performance Notes

- Raspberry Pi 1: ≤ 10 casters recommended
- SQLite is sufficient for years of data at 5‑minute intervals
- Web UI is intentionally minimal for low resource usage

---

## Troubleshooting

**Caster shows stale data**
- Confirm it exists in `casters`
- Check monitor service is running

**No Telegram alerts**
- Verify token and chat ID
- Check outbound HTTPS access

**Web page not loading**
- Ensure Flask is running
- Confirm port 8080 is open

---

## License

Use, modify, and deploy freely. No warranty implied.

---

## Philosophy

This project prioritizes:

- Reliability over cleverness
- Transparency over abstraction
- Longevity over trends

If it’s running quietly for years, it’s doing its job.

