#!/usr/bin/env python3
"""
BookMyShow ticket-open watcher.

Polls a BMS listing page and sends an instant phone push notification
(via ntfy.sh) the moment the page indicates tickets/booking has opened.

This script only WATCHES a public page and NOTIFIES you. It does not
automate the booking/checkout flow — you click and pay yourself.

Setup:
1. pip install -r requirements.txt
2. Install the "ntfy" app on your phone (iOS/Android) and subscribe to
   YOUR topic (see NTFY_TOPIC below — pick your own, don't reuse examples).
3. Edit the CONFIG section below for your event.
4. Run inside tmux so it survives a closed terminal: `tmux new -s bms`,
   then `python bms_ticket_watcher.py`, then Ctrl+B D to detach.
   Note: tmux does NOT survive the machine itself going to sleep — if
   running on a laptop, disable sleep-on-lid-close and keep it plugged
   in, or run this on an always-on remote/cloud machine instead.
5. Checks happen every 5-10 minutes (randomized) to avoid a bot-like
   fixed cadence that BMS could rate-limit or block.

See README.md for full setup instructions, including how to find your
URL and date code.
"""

import requests
import time
import random
import sys
from datetime import datetime

# ============ CONFIG — edit these ============

# The BMS showtimes page for your city/event. Any valid date in the URL
# works — BMS returns lock/unlock status for the *whole* upcoming week
# regardless of which date is in the path. See README for how to get this.
URL = "https://in.bookmyshow.com/movies/chennai/the-odyssey-imax-2d/buytickets/ET00480917/20260728"

# The date you're waiting on, in YYYYMMDD format. See README for how to
# find this in the page source. This is only used to build the URL path
# above — the actual open/closed trigger is TARGET_VENUE_CODE below.
TARGET_DATE_CODE = "20260728"

# The specific theatre to wait for. Every BMS cinema's own page URL ends in
# its venue code — e.g. .../pvr-palazzo-the-nexus-vijaya-mall/PVPZ -> PVPZ.
# Find yours by visiting the cinema's own listing page and copying the last
# path segment of the URL.
TARGET_VENUE_CODE = "PVPZ"  # PVR: Palazzo, The Nexus Vijaya Mall

# How often to check. Randomized between MIN and MAX on every cycle so
# requests don't land at a fixed, bot-like cadence BMS could rate-limit
# or block. Trade-off: worst case you find out up to POLL_INTERVAL_MAX
# after tickets actually open, not instantly.
POLL_INTERVAL_MIN_SECONDS = 2 * 60  # 5 minutes
POLL_INTERVAL_MAX_SECONDS = 4 * 60  # 10 minutes

# Your ntfy.sh topic. Pick your OWN random, unguessable string — anyone
# who knows this string can read your alerts or publish fake ones, since
# ntfy topics are unauthenticated by default. Don't reuse this example.
# A good pattern: something-something-<random hex>, e.g. via:
#   python -c "import secrets; print('bms-' + secrets.token_hex(6))"
NTFY_TOPIC = "bms-798f41c01a8c"

# ============ END CONFIG ============

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def send_notification(
    title: str, message: str, priority: str = "urgent", retries: int = 3
):
    """Send a push notification via ntfy.sh, retrying on transient failures."""
    for attempt in range(1, retries + 1):
        try:
            requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=message.encode("utf-8"),
                headers={
                    # HTTP headers are Latin-1 by default, but titles here
                    # may contain emoji — encode to UTF-8 bytes ourselves so
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
    print("[!] All notification attempts failed — check your network/ntfy.sh manually.")
    return False


def check_page() -> bool:
    """Returns True if TARGET_VENUE_CODE has showtimes listed for the date in URL.

    BMS embeds a "venue-card" block (containing a venueCode field) into the
    page's JSON state for every cinema that currently has showtimes for the
    selected date. A cinema that hasn't opened bookings yet simply has no
    venue-card at all, so we just check whether our target venue's card exists.
    """
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=10)
    except Exception as e:
        print(f"[{timestamp()}] Request failed: {e}")
        return False

    if resp.status_code != 200:
        print(f"[{timestamp()}] Got status {resp.status_code}")
        return False

    page = resp.text
    venue_open_marker = f'"venueCode":"{TARGET_VENUE_CODE}"'

    return venue_open_marker in page


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def next_poll_delay() -> float:
    """Random delay in seconds between POLL_INTERVAL_MIN/MAX_SECONDS."""
    return random.uniform(POLL_INTERVAL_MIN_SECONDS, POLL_INTERVAL_MAX_SECONDS)


def validate_config():
    """Check that the placeholder CONFIG values have actually been edited."""
    problems = []
    if "CHANGE-ME" in URL or "<" in URL:
        problems.append("URL (still has the placeholder / angle brackets)")
    if "CHANGE-ME" in TARGET_DATE_CODE or not TARGET_DATE_CODE.isdigit():
        problems.append("TARGET_DATE_CODE (must be 8 digits, YYYYMMDD)")
    if "CHANGE-ME" in TARGET_VENUE_CODE or TARGET_VENUE_CODE == "XXXX":
        problems.append("TARGET_VENUE_CODE (set to your theatre's venue code)")
    if "CHANGE-ME" in NTFY_TOPIC:
        problems.append("NTFY_TOPIC (pick your own random topic name)")
    return problems


def main():
    problems = validate_config()
    if problems:
        print("Edit the CONFIG section at the top of this file first:")
        for p in problems:
            print(f"  - {p}")
        print("\nSee README.md for step-by-step instructions.")
        sys.exit(1)

    print(f"Watching: {URL}")
    print(f"Target date: {TARGET_DATE_CODE}")
    print(
        f"Polling every {POLL_INTERVAL_MIN_SECONDS // 60}-"
        f"{POLL_INTERVAL_MAX_SECONDS // 60} min (randomized). Ctrl+C to stop.\n"
    )

    send_notification(
        "Watcher started",
        "BMS watcher is now running and will alert you when tickets open.",
        priority="default",
    )

    checks = 0
    while True:
        checks += 1
        open_now = check_page()
        print(f"[{timestamp()}] Check #{checks} — open: {open_now}")

        if open_now:
            print(f"[{timestamp()}] TICKETS OPEN — sending alert!")
            for i in range(3):  # send a few times in case one is missed
                send_notification(
                    "🎟️ Tickets are OPEN!",
                    "Go book now — BookMyShow just went live.",
                    priority="urgent",
                )
                time.sleep(1)
            print("Stopping watcher — go book your tickets now.")
            break

        delay = next_poll_delay()
        print(f"[{timestamp()}] Next check in {delay / 60:.1f} min")
        time.sleep(delay)


if __name__ == "__main__":
    main()
