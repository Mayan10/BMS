# BMS Ticket Watcher

Polls a BookMyShow event page and sends a phone notification when tickets open.

## Setup

```bash
git clone https://github.com/Mayan10/BMS.git
cd BMS
pip install -r requirements.txt
```

Edit `bms_ticket_watcher.py` — replace the 3 `# CHANGE-ME` values:
1. **URL** — your event's BMS buy-tickets page
2. **TARGET_DATE_CODE** — the date you're waiting on (`YYYYMMDD`, find it in page source)
3. **NTFY_TOPIC** — run `python3 -c "import secrets; print('bms-' + secrets.token_hex(6))"` and subscribe to that topic in the ntfy app

## Run

```bash
python bms_ticket_watcher.py
```

Keep it running (use `tmux` or a free cloud VM). You'll get an alert the moment booking opens.
