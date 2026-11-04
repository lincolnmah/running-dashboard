"""
Garmin Connect Personal API -> CSV/JSON export.

Reads your API key from connect-personal-api-key.txt (next to this script),
pulls activities and daily health data for a date range, and writes one
CSV and one JSON file per dataset into a garmin_export folder.

Usage (from this folder):
    python garmin_export.py                      # last 180 days
    python garmin_export.py --start 2026-07-01   # from a date to today
    python garmin_export.py --start 2026-07-01 --end 2026-10-31

Read-only: the Personal API cannot change anything in your account.
"""

import argparse
import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    from gcpapi_sync import GarminClient, GarminError
except ImportError:
    sys.exit("Missing library. Run:  python -m pip install gcpapi-sync")

HERE = Path(__file__).resolve().parent
KEY_FILE = HERE / "connect-personal-api-key.txt"


def to_plain(obj):
    """Turn library model objects into plain dicts/lists."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, (list, tuple)):
        return [to_plain(o) for o in obj]
    return obj


def flatten(d, prefix=""):
    """Flatten nested dicts into one level: {'a': {'b': 1}} -> {'a.b': 1}.
    Lists are kept as JSON text so every row fits in one CSV line."""
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, list):
            out[key] = json.dumps(v)
        else:
            out[key] = v
    return out


def write_outputs(name, records, out_dir):
    rows = [to_plain(r) for r in records]
    rows = [r for r in rows if r is not None]
    (out_dir / f"{name}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    flat = [flatten(r) if isinstance(r, dict) else {"value": r} for r in rows]
    columns = []  # keep only columns that have a value in at least one row
    for r in flat:
        for k, v in r.items():
            if k not in columns and v not in (None, "", "[]"):
                columns.append(k)
    flat = [{k: r.get(k) for k in columns} for r in flat]
    with open(out_dir / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns or ["empty"])
        w.writeheader()
        w.writerows(flat)
    return len(rows)


def main():
    p = argparse.ArgumentParser(description="Export Garmin Connect data to CSV/JSON.")
    p.add_argument("--start", help="first day, YYYY-MM-DD (default: 180 days ago)")
    p.add_argument("--end", help="last day, YYYY-MM-DD (default: today)")
    p.add_argument("--out", default=str(HERE / "garmin_export"), help="output folder")
    a = p.parse_args()

    end = date.fromisoformat(a.end) if a.end else date.today()
    start = date.fromisoformat(a.start) if a.start else end - timedelta(days=180)
    if start > end:
        sys.exit("--start must be on or before --end")

    if not KEY_FILE.exists():
        sys.exit(f"API key file not found: {KEY_FILE}")
    api_key = KEY_FILE.read_text(encoding="utf-8-sig").strip()
    if not api_key:
        sys.exit(f"API key file is empty: {KEY_FILE}")

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Exporting {start} to {end} into {out_dir}\n")

    client = GarminClient(api_key)

    datasets = {
        "activities": lambda: client.iter_activities(
            start_date=start, end_date=end, sort_order="asc"),
        "daily_summaries": lambda: client.get_daily_summaries(start, end),
        "sleep": lambda: client.get_daily_sleep_summaries(start, end),
        "hrv": lambda: client.get_daily_hrv_summaries(start, end),
        "body_battery": lambda: client.get_daily_body_battery(start, end),
        "stress": lambda: client.get_daily_stress(start, end),
        "steps": lambda: client.get_daily_steps(start, end),
    }

    failures = 0
    for name, fetch in datasets.items():
        try:
            n = write_outputs(name, list(fetch()), out_dir)
            print(f"  {name:<16} {n:>5} records")
        except GarminError as e:
            failures += 1
            print(f"  {name:<16} FAILED: {type(e).__name__}: {e}")
            if "Authentication" in type(e).__name__:
                sys.exit("\nGarmin rejected the API key. Check it hasn't expired or "
                         "been revoked in Garmin Connect > Settings > Personal API Key.")
        except Exception as e:  # keep going so one bad dataset doesn't stop the rest
            failures += 1
            print(f"  {name:<16} FAILED: {type(e).__name__}: {e}")

    print("\nDone." + (f" {failures} dataset(s) failed; see above." if failures else ""))


if __name__ == "__main__":
    main()
