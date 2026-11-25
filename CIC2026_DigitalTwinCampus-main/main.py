"""
main.py - Digital Twin Orchestrator
Entry point for the Data Collector Service.

Credentials are read from the .env file (EB_EMAIL, EB_PASSWORD).
They can be overridden with CLI flags for one-off runs.

Usage:
    python main.py                        # use credentials from .env
    python main.py --once                 # single fetch then exit (useful for cron)
    python main.py --email x@y.fi --password secret  # override .env values
"""

import os
import sys
import argparse
import logging
from dotenv import load_dotenv

# Load .env before anything else so os.environ is populated
load_dotenv()

from services.collector import DataCollector

# Creates a logger named "main" so the script can print info/warning/error messages.
log = logging.getLogger("main")

# handle command‑line arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Campus Digital Twin – Data Collector")
    parser.add_argument("--email",    default=None, help="EB account email (overrides .env)")
    parser.add_argument("--password", default=None, help="EB account password (overrides .env)")
    parser.add_argument("--once",     action="store_true", help="Fetch once and exit instead of polling")
    return parser.parse_args()


def main():
    # Reads the command‑line arguments.
    args = parse_args()

    # CLI flags take priority; fall back to .env values loaded into os.environ
    email    = args.email    or os.environ.get("EB_EMAIL")
    password = args.password or os.environ.get("EB_PASSWORD")

    if not email or not password:
        log.error("No credentials found. Set EB_EMAIL and EB_PASSWORD in .env or pass --email / --password.")
        sys.exit(1)

    collector = DataCollector(email, password)

    if args.once:
        log.info("Single-shot mode")
        ok = collector.fetch_once()
        sys.exit(0 if ok else 1)
    else:
        try:
            collector.run()
        except KeyboardInterrupt:
            log.info("Stopped by user.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    main()
