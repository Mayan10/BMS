#!/usr/bin/env python3
"""
BookMyShow ticket-open watcher.

Polls a BMS listing page and sends an instant phone push notification
(via ntfy.sh) the moment the page indicates tickets/booking has opened.

This script only WATCHES a public page and NOTIFIES you. It does not
automate the booking/checkout flow; you click and pay yourself.

This version is fully interactive: run it and it asks you for the event
URL, date, (optionally) a specific theatre, and your ntfy.sh topic, no
editing the source required. Anyone can just run it and answer the prompts.

Setup:
1. pip install -r requirements.txt
2. Install the "ntfy" app on your phone (iOS/Android).
3. Run: python BookMyShowTicketWatcher.py
   Answer the prompts (see README.md for how to find the URL / venue code).
4. Run inside tmux so it survives a closed terminal: `tmux new -s bms`,
   then `python BookMyShowTicketWatcher.py`, then Ctrl+B D to detach.
   Note: tmux does NOT survive the machine itself going to sleep. If
   running on a laptop, disable sleep-on-lid-close and keep it plugged
   in, or run this on an always-on remote/cloud machine instead.
5. Checks happen every few minutes (randomized, you choose the range) to
   avoid a bot-like fixed cadence that BMS could rate-limit or block.
"""

import re
import sys
import time
import random
import requests
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


# ============ INTERACTIVE SETUP ============

def ask(prompt_text: str, default: str = None, required: bool = True,
        validator=None, error_msg: str = None) -> str:
    """Prompt the user, optionally with a default, requirement, and validator."""
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"{prompt_text}{suffix}: ").strip()
        if not raw and default is not None:
            raw = default
        if not raw and not required:
            return ""
        if not raw:
            print("  This is required, please enter a value.")
            continue
        if validator and not validator(raw):
            print(f"  {error_msg or 'Invalid value, try again.'}")
            continue
        return raw


def strip_query_string(url: str) -> str:
    """Drop ?query and #fragment parts. BMS sometimes appends Cloudflare
    challenge tokens etc. that go stale and aren't needed for a plain GET."""
    return url.split("?", 1)[0].split("#", 1)[0]


def guess_date_from_url(url: str):
    """Try to pull an 8-digit YYYYMMDD date off the end of the URL path."""
    match = re.search(r"/(\d{8})/?$", strip_query_string(url))
    return match.group(1) if match else None


def get_config() -> dict:
    print("=== BMS Ticket Watcher Setup ===")
    print("Answer a few questions below. Press Enter to accept a [default] where shown.\n")

    print("1) Paste the full BookMyShow ticket page URL for your event.")
    print("   (Open the movie/event on BookMyShow, click a date, copy the address bar URL.)")
    raw_url = ask("URL")
    url = strip_query_string(raw_url)

    guessed_date = guess_date_from_url(url)
    print("\n2) The date you're waiting on, in YYYYMMDD format.")
    if guessed_date:
        print(f"   Detected '{guessed_date}' from your URL, press Enter to use it.")
    date_code = ask(
        "Target date (YYYYMMDD)",
        default=guessed_date,
        validator=lambda v: v.isdigit() and len(v) == 8,
        error_msg="Must be exactly 8 digits, e.g. 20260728.",
    )

    print("\n3) (Optional) Watch ONE specific theatre instead of any theatre in the city.")
    print("   Every BMS cinema's own page URL ends in its venue code, e.g.")
    print("   .../pvr-palazzo-the-nexus-vijaya-mall/PVPZ -> PVPZ")
    print("   Leave blank to alert as soon as ANY theatre opens for this date.")
    venue_code = ask("Theatre venue code (optional)", required=False)

    print("\n4) Your ntfy.sh topic, pick your OWN random, unguessable string.")
    print("   Subscribe to this exact string in the ntfy app before running.")
    print("   Generate one with:")
    print("     python3 -c \"import secrets; print('bms-' + secrets.token_hex(6))\"")
    ntfy_topic = ask("ntfy.sh topic")

    print("\n5) (Optional) How often to check, in minutes (randomized between these each cycle).")
    poll_min = ask(
        "Minimum minutes between checks", default="5",
        validator=lambda v: v.isdigit() and int(v) > 0,
        error_msg="Enter a positive whole number.",
    )
    poll_max = ask(
        "Maximum minutes between checks", default="10",
        validator=lambda v: v.isdigit() and int(v) >= int(poll_min),
        error_msg=f"Enter a whole number >= {poll_min}.",
    )

    print()
    return {
        "url": url,
        "date_code": date_code,
        "venue_code": venue_code,
        "ntfy_topic": ntfy_topic,
        "poll_min_seconds": int(poll_min) * 60,
        "poll_max_seconds": int(poll_max) * 60,
    }


# ============ CORE LOGIC ============

def send_notification(
    topic: str, title: str, message: str, priority: str = "urgent", retries: int = 3
):
    """Send a push notification via ntfy.sh, retrying on transient failures."""
    for attempt in range(1, retries + 1):
        try:
            requests.post(
                f"https://ntfy.sh/{topic}",
                data=message.encode("utf-8"),
                headers={
                    # HTTP headers are Latin-1 by default, but titles here
                    # may contain emoji, so encode to UTF-8 bytes ourselves so
                    # the underlying http.client doesn't try (and fail) to
                    # encode the string as Latin-1 when sending.
                    "Title": title.encode("utf-8"),
                    "Priority": priority,
                    "Tags": "rotating_light",
                },
                timeout=15,
            )
            return True
        except Exception as e:
            print(f"[!] Notification attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(5)
    print("[!] All notification attempts failed, check your network/ntfy.sh manually.")
    return False


def check_page(url: str, date_code: str, venue_code: str) -> bool:
    """Returns True once tickets appear open.

    If venue_code is set: True once that theatre's "venueCode" card appears
    in the page's embedded JSON (theatres with no showtimes yet have no card
    at all).

    If venue_code is blank: True once the date itself unlocks. BMS marks
    each of the next 7 days with a styleId; not-yet-open days are tagged
    "date-disabled" with no click handler until booking opens.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
    except Exception as e:
        print(f"[{timestamp()}] Request failed: {e}")
        return False

    if resp.status_code != 200:
        print(f"[{timestamp()}] Got status {resp.status_code}")
        return False

    page = resp.text

    if venue_code:
        marker = f'"venueCode":"{venue_code}"'
        return marker in page
    else:
        still_locked_marker = f'"id":"{date_code}","styleId":"date-disabled"'
        return still_locked_marker not in page


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def main():
    try:
        cfg = get_config()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
        sys.exit(1)

    print(f"Watching: {cfg['url']}")
    print(f"Target date: {cfg['date_code']}")
    if cfg["venue_code"]:
        print(f"Target venue code: {cfg['venue_code']}")
    else:
        print("No specific theatre set, will alert as soon as ANY theatre opens for this date.")
    print(
        f"Polling every {cfg['poll_min_seconds'] // 60}-"
        f"{cfg['poll_max_seconds'] // 60} min (randomized). Ctrl+C to stop.\n"
    )

    send_notification(
        cfg["ntfy_topic"],
        "Watcher started",
        "BMS watcher is now running and will alert you when tickets open.",
        priority="default",
    )

    checks = 0
    while True:
        checks += 1
        open_now = check_page(cfg["url"], cfg["date_code"], cfg["venue_code"])
        print(f"[{timestamp()}] Check #{checks}, open: {open_now}")

        if open_now:
            print(f"[{timestamp()}] TICKETS OPEN, sending alert!")
            for i in range(3):  # send a few times in case one is missed
                send_notification(
                    cfg["ntfy_topic"],
                    "🎟️ Tickets are OPEN!",
                    "Go book now, BookMyShow just went live.",
                    priority="urgent",
                )
                time.sleep(1)
            print("Stopping watcher, go book your tickets now.")
            break

        delay = random.uniform(cfg["poll_min_seconds"], cfg["poll_max_seconds"])
        print(f"[{timestamp()}] Next check in {delay / 60:.1f} min")
        time.sleep(delay)


if __name__ == "__main__":
    main()
