# BMS Ticket Watcher 🎟️

A tiny Python script that watches a [BookMyShow](https://in.bookmyshow.com) event
page and sends an **instant push notification to your phone** the moment
booking opens for a specific date — so you're not the person hitting refresh
for three hours.

> **It only watches and notifies.** It does not log in, does not fill in any
> forms, and does not buy tickets for you. You still click and pay yourself,
> just the second you get the alert instead of whenever you happen to check.

---

## How it works

BookMyShow server-renders the next 7 days of availability as JSON inside the
page itself (`window.__INITIAL_STATE__`). Each date is tagged with a
`styleId`: dates that aren't bookable yet are marked `"date-disabled"`. The
script polls the page every 5–10 minutes (randomized, to avoid a bot-like
fixed cadence) and checks whether your target date's `"date-disabled"` marker
has disappeared. The instant it does, it fires a push notification via
[ntfy.sh](https://ntfy.sh) — a free, no-signup push notification service —
three times in a row (in case one is missed) and then exits.

## Features

- ✅ Zero-login, read-only — just polls a public page
- ✅ Randomized polling interval so requests don't look bot-like
- ✅ Free push notifications to your phone via ntfy.sh (no account needed)
- ✅ Retries notification delivery if the first attempt fails
- ✅ Config is validated on startup — it refuses to run with placeholder values,
  so you can't accidentally leave it half-configured

## Requirements

- Python 3.7+
- The [`ntfy`](https://ntfy.sh) app on your phone ([iOS](https://apps.apple.com/us/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy))
- A place to leave it running (see [Running it reliably](#running-it-reliably))

## Installation

```bash
git clone https://github.com/Mayan10/BMS.git
cd BMS
pip install -r requirements.txt
```

## Configuration

Open `bms_ticket_watcher.py` and edit the `CONFIG` section near the top.
Every value marked `# CHANGE-ME` **must** be replaced — the script checks for
this on startup and refuses to run otherwise.

### 1. `URL` — your event's BMS page

1. Go to the event on BookMyShow and click through to the "Buy tickets" /
   showtimes page (the URL will look like
   `https://in.bookmyshow.com/movies/<city>/<event-slug>/buytickets/<EVENT-ID>/<date>`).
2. Copy that full URL into `URL`. The trailing date doesn't matter much — BMS
   returns the whole upcoming week's status regardless of which date is in
   the path — but use any valid, current date.

### 2. `TARGET_DATE_CODE` — the exact date you're waiting on

1. Open the same URL in a browser.
2. View page source (`Ctrl+U` / `Cmd+Option+U`) and search (`Ctrl+F`) for
   `date-disabled`.
3. You'll see entries like `{"id":"20260728","styleId":"date-disabled"}`.
   Find the one for your date and copy the `id` value (format `YYYYMMDD`)
   into `TARGET_DATE_CODE`.
4. If your date has already opened, you won't find a `date-disabled` entry
   for it — meaning you don't need this script for that date at all.

### 3. `NTFY_TOPIC` — your private notification channel

ntfy.sh topics are just a shared string — **anyone who knows your topic name
can read your notifications or spam you on it**, since there's no
authentication by default. Generate your own random, unguessable one:

```bash
python3 -c "import secrets; print('bms-' + secrets.token_hex(6))"
```

Put the result in `NTFY_TOPIC`, then open the ntfy app on your phone and
subscribe to that **exact** string.

### Optional: polling interval

`POLL_INTERVAL_MIN_SECONDS` / `POLL_INTERVAL_MAX_SECONDS` default to 5–10
minutes. You can tighten this for a faster alert, but very frequent polling
increases the chance BMS rate-limits or blocks your IP — see
[A note on responsible use](#a-note-on-responsible-use).

## Usage

```bash
python bms_ticket_watcher.py
```

You'll get a "Watcher started" notification immediately (confirming ntfy is
wired up correctly), then the script checks on its randomized schedule until
the target date opens, at which point it sends three urgent alerts and exits.

## Running it reliably

The watcher needs to stay running for however long you're waiting — often
hours. A few options, easiest first:

**tmux (quick, but laptop-dependent)**
```bash
tmux new -s bms
python bms_ticket_watcher.py
# Ctrl+B, then D to detach — it keeps running in the background
# Reattach any time with: tmux attach -t bms
```
This survives you closing the terminal, but **not** the machine going to
sleep. If you're on a laptop, disable sleep-on-lid-close and keep it plugged
in, or use one of the options below.

**A free always-on cloud VM**
Any small free-tier VM (e.g. Oracle Cloud Free Tier, a $0 GitHub Codespace
session, a Raspberry Pi at home) works well — run it inside `tmux` there and
you don't need your own laptop on at all.

**systemd (Linux, for a "set and forget" setup)**
```ini
# /etc/systemd/system/bms-watcher.service
[Unit]
Description=BMS Ticket Watcher

[Service]
ExecStart=/usr/bin/python3 /path/to/bms_ticket_watcher.py
WorkingDirectory=/path/to/bms-ticket-watcher
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now bms-watcher
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Exits immediately with "Edit the CONFIG section first" | You left one of the `# CHANGE-ME` values unedited |
| No "Watcher started" notification on launch | Wrong `NTFY_TOPIC`, or you didn't subscribe in the app to the exact same string |
| Never detects the opening | `TARGET_DATE_CODE` doesn't match what's actually in the page — re-check the page source, BMS occasionally changes date formats between events |
| Got HTTP errors / non-200 status in the logs | BMS may be rate-limiting your IP — increase the polling interval |

## A note on responsible use

This project only reads a public page you could load in a browser yourself —
it doesn't bypass any login, CAPTCHA, or paywall, and it deliberately
randomizes its polling interval to avoid hammering BMS's servers. That said,
automated polling of any site should be done politely (don't crank the
interval down aggressively) and in line with that site's terms of service.
This project isn't affiliated with, endorsed by, or supported by BookMyShow;
use it at your own discretion and risk.

## Contributing

Issues and PRs are welcome — this is a small, single-file script, so keep
changes focused and dependency-free where possible.

## License

[MIT](LICENSE)
