"""
Turn a Garmin export (from garmin_export.py) into the dashboard's compact CSVs,
merging it into the existing history in data/garmin/.

    python scripts/compact_garmin.py EXPORT_DIR --start 2026-10-01

Days and activities on or after --start are replaced with the new export;
everything earlier is kept as it was.
"""

import argparse
import csv
import json
from functools import reduce
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "garmin"


def g(d, *keys):
    return reduce(lambda a, k: a.get(k) if isinstance(a, dict) else None, keys, d)


def r(v, n=1):
    return round(v, n) if isinstance(v, (int, float)) else None


def load(export, name):
    p = Path(export) / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def daily_rows(data):
    out = []
    for x in sorted(data, key=lambda x: x["calendar_date"]):
        row = dict(
            date=x["calendar_date"], steps=g(x, "movement", "steps", "value"),
            rhr=g(x, "heart_rate", "resting_value"), hr_max=g(x, "heart_rate", "max_value"),
            bb_min=g(x, "body_battery", "min_value"), bb_max=g(x, "body_battery", "max_value"),
            bb_charged=g(x, "body_battery", "charged_value"), bb_drained=g(x, "body_battery", "drained_value"),
            stress_avg=g(x, "stress", "avg_level"), stress_max=g(x, "stress", "max_level"),
            high_stress_min=round((g(x, "stress", "high_stress_duration_in_millis") or 0) / 60000),
            kcal=g(x, "calories", "burned_total"), kcal_active=g(x, "calories", "burned_active"),
            int_mod=g(x, "intensity_minutes", "moderate"), int_vig=g(x, "intensity_minutes", "vigorous"),
            resp=g(x, "respiration", "avg_value"), utc_offset_h=None,
        )
        st = g(x, "wellness_chronology", "start_timestamp_gmt")
        if st:
            h = int(st[11:13])
            row["utc_offset_h"] = -h if h <= 12 else 24 - h
        out.append(row)
    return out


def sleep_rows(data):
    out = []
    for x in sorted(data, key=lambda x: x["calendar_date"]):
        t = x.get("sleep_time_seconds")
        if not t:
            continue
        sc = x.get("sleep_scores") or {}
        out.append(dict(
            date=x["calendar_date"], sleep_h=round(t / 3600, 2),
            deep_h=round((x.get("deep_sleep_seconds") or 0) / 3600, 2),
            light_h=round((x.get("light_sleep_seconds") or 0) / 3600, 2),
            rem_h=round((x.get("rem_sleep_seconds") or 0) / 3600, 2),
            awake_min=round((x.get("awake_sleep_seconds") or 0) / 60),
            resp=x.get("average_respiration_value"),
            score=(sc.get("overall") or {}).get("value") if isinstance(sc, dict) else None,
            bed=(x.get("sleep_start_timestamp_local") or "")[11:16],
            wake=(x.get("sleep_end_timestamp_local") or "")[11:16],
        ))
    return out


def activity_rows(data):
    out = []
    for x in sorted(data, key=lambda x: x.get("start_time_local") or ""):
        tk = (x.get("activity_type") or {}).get("type_key")
        if tk == "incident_detected":
            continue
        out.append(dict(
            date=(x.get("start_time_local") or "")[:10], start=(x.get("start_time_local") or "")[11:16],
            type=tk, name=x.get("activity_name"),
            km=r((x.get("distance") or 0) / 1000, 2), min=r((x.get("moving_duration") or x.get("duration") or 0) / 60),
            avg_hr=r(x.get("average_hr"), 0), max_hr=r(x.get("max_hr"), 0), avg_power=r(x.get("avg_power"), 0),
            cadence=r(x.get("average_running_cadence_in_steps_per_minute"), 0), elev_gain=r(x.get("elevation_gain"), 0),
            kcal=r(x.get("calories"), 0), aerobic_te=r(x.get("aerobic_training_effect")),
            anaerobic_te=r(x.get("anaerobic_training_effect")), load=r(x.get("activity_training_load"), 0),
            vo2max=r(x.get("vo2_max_value")),
            **{f"hrz{i}": r(x.get(f"hr_time_in_zone_{i}"), 0) for i in range(1, 6)},
        ))
    return out


def norm(v):
    return "" if v is None else str(v)


def merge(path, new_rows, start):
    old = list(csv.DictReader(open(path, encoding="utf-8"))) if path.exists() else []
    cols = list(old[0].keys()) if old else list(new_rows[0].keys())
    kept = [row for row in old if row["date"] < start]
    added = [{c: norm(row.get(c)) for c in cols} for row in new_rows if row["date"] >= start]
    rows = sorted(kept + added, key=lambda row: (row["date"], row.get("start", "")))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return len(old), len(rows), len(added)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("export_dir")
    p.add_argument("--start", required=True, help="first day the export covers, YYYY-MM-DD")
    a = p.parse_args()
    for name, fn, src in [("garmin_daily.csv", daily_rows, "daily_summaries"),
                          ("garmin_sleep.csv", sleep_rows, "sleep"),
                          ("garmin_activities.csv", activity_rows, "activities")]:
        data = load(a.export_dir, src)
        if not data:
            print(f"{name}: no new data in the export, left unchanged")
            continue
        before, after, added = merge(OUT / name, fn(data), a.start)
        print(f"{name}: {before} -> {after} rows ({added} from the export)")


if __name__ == "__main__":
    main()
