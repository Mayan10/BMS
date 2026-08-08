# BMS Ticket Watcher

[![License: MIT](https://img.shields.io/github/license/Mayan10/BMS)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/downloads/)
[![Lint](https://github.com/Mayan10/BMS/actions/workflows/lint.yml/badge.svg)](https://github.com/Mayan10/BMS/actions/workflows/lint.yml)
[![Latest release](https://img.shields.io/github/v/release/Mayan10/BMS)](https://github.com/Mayan10/BMS/releases)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](#contributing)

A tiny Python script that watches a [BookMyShow](https://in.bookmyshow.com) event
page and sends an instant push notification to your phone the moment
booking opens for a specific date, so you're not the person hitting refresh
for three hours.

> It only watches and notifies. It does not log in, does not fill in any
> forms, and does not buy tickets for you. You still click and pay yourself,
> just the second you get the alert instead of whenever you happen to check.

---

## How it works

Run the script and it asks you a few questions, no source editing required.
BookMyShow server-renders event data as JSON inside the page itself
(`window.__INITIAL_STATE__`), and the script checks it one of two ways
depending on whether you gave it a specific theatre:

- **Any theatre** (leave the venue code blank): each of the next 7 days is
  tagged with a `styleId`; dates that aren't bookable yet are marked
  `"date-disabled"`. The script polls until that marker disappears for your
  target date, i.e. the instant *any* theatre opens booking for that date.
- **One specific theatre** (give it a venue code): BMS only adds a
  `"venueCode"` entry to the page for theatres that currently have showtimes
  listed. The script polls until your chosen theatre's entry appears, so it
  stays quiet even if other theatres open first.

Either way, it polls every 5 to 10 minutes by default (randomized, to avoid
a bot-like fixed cadence), and the instant it detects the opening it fires a
push notification via [ntfy.sh](https://ntfy.sh), a free, no-signup push
notification service, three times in a row (in case one is missed) and then
exits.

## Features

- Fully interactive: run it and answer a few prompts, nothing to edit in the source
- Watch any theatre in a city, or lock onto one specific theatre
- Auto-detects the target date from the URL you paste
- Zero-login, read-only: just polls a public page
- Randomized polling interval so requests don't look bot-like
- Free push notifications to your phone via ntfy.sh (no account needed)
- Retries notification delivery if the first attempt fails
- Input is validated as you type, so it won't let you proceed with a malformed date or empty required field

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

## Usage

```bash
python BookMyShowTicketWatcher.py
```

Nothing needs editing. The script prompts you for everything it needs, in order:

### 1. The event URL

Go to the event on BookMyShow and click through to the "Buy tickets" /
showtimes page (the URL will look like
`https://in.bookmyshow.com/movies/<city>/<event-slug>/buytickets/<EVENT-ID>/<date>`).
Paste the full URL. Any `?query` junk on the end (tracking params, stale
Cloudflare tokens, etc.) is stripped automatically.

### 2. The target date (YYYYMMDD)

The script tries to auto-detect this from the URL you just pasted and offers
it as a default, so just press Enter if it looks right. The trailing date in
the URL doesn't have to be exact (BMS returns the whole upcoming week's
status regardless of which date is in the path), but the date you confirm
here is the one actually being watched.

### 3. Theatre venue code (optional)

- **Leave this blank** to get notified the instant *any* theatre in the city
  opens booking for your date.
- **Fill it in** to wait for one specific theatre instead. Every BMS cinema
  has its own listing page, and the URL always ends in that theatre's code,
  e.g. `.../pvr-palazzo-the-nexus-vijaya-mall/PVPZ` has the code `PVPZ`.
  Find your theatre on BMS, open its page, and copy the last part of the URL.

### 4. Your ntfy.sh topic

ntfy.sh topics are just a shared string. Anyone who knows your topic name
can read your notifications or spam you on it, since there's no
authentication by default. Generate your own random, unguessable one:

```bash
python3 -c "import secrets; print('bms-' + secrets.token_hex(6))"
```

Then open the ntfy app on your phone and subscribe to that exact string
before running the script, so you're ready to receive the "Watcher
started" confirmation.

### 5. Polling interval (optional)

Defaults to 5 to 10 minutes, randomized each cycle. Press Enter twice to
accept the defaults, or tighten it for a faster alert. Very frequent polling
increases the chance BMS rate-limits or blocks your IP; see
[A note on responsible use](#a-note-on-responsible-use).

---

Once you've answered the prompts, you'll get a "Watcher started" notification
immediately (confirming ntfy is wired up correctly), then the script checks
on its randomized schedule until the target opens, at which point it sends
three urgent alerts and exits.

## Running it reliably

The watcher needs to stay running for however long you're waiting, often
hours. A few options, easiest first:

**tmux (quick, but laptop-dependent)**
```bash
tmux new -s bms
python BookMyShowTicketWatcher.py
# Ctrl+B, then D to detach, it keeps running in the background
# Reattach any time with: tmux attach -t bms
```
This survives you closing the terminal, but not the machine going to
sleep. If you're on a laptop, disable sleep-on-lid-close and keep it plugged
in, or use one of the options below.

**A free always-on cloud VM**
Any small free-tier VM (e.g. Oracle Cloud Free Tier, a free GitHub Codespace
session, a Raspberry Pi at home) works well. Run it inside `tmux` there and
you don't need your own laptop on at all.

**systemd (Linux, for a "set and forget" setup)**

Since the script is interactive, a plain systemd service has no terminal
to answer its prompts. Easiest fix: run it once manually inside a `tmux`
session (answer the prompts there), then just leave that session detached.
You don't need systemd on top of tmux for a single run. If you really want
systemd specifically, run it inside a persistent pty (e.g. via `screen -D -m`
in `ExecStart`) so the prompts have somewhere to go, or fork a
non-interactive variant that reads a JSON/env config instead.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Keeps rejecting your date input | Must be exactly 8 digits, `YYYYMMDD`, e.g. `20260728`, not `2026-07-28` |
| No "Watcher started" notification on launch | Wrong ntfy topic typed in, or you didn't subscribe in the app to the exact same string beforehand |
| Never detects the opening (any-theatre mode) | Double check the date you confirmed matches what BMS actually uses. Date formats occasionally shift between events, so re-check page source for `date-disabled` |
| Never detects the opening (specific-theatre mode) | Venue code might be wrong. Revisit that theatre's own BMS page and re-copy the code from the end of the URL |
| Got HTTP errors / non-200 status in the logs | BMS may be rate-limiting your IP. Increase the polling interval |

## A note on responsible use

This project only reads a public page you could load in a browser yourself.
It doesn't bypass any login, CAPTCHA, or paywall, and it deliberately
randomizes its polling interval to avoid hammering BMS's servers. That said,
automated polling of any site should be done politely (don't crank the
interval down aggressively) and in line with that site's terms of service.
This project isn't affiliated with, endorsed by, or supported by BookMyShow.
Use it at your own discretion and risk.

## Contributing

Issues and PRs are welcome. This is a small, single-file script, so keep
changes focused and dependency-free where possible.

## License

[MIT](LICENSE)
