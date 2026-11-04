"""Combine Stryd + Garmin CSVs into site/data.js for the dashboard."""
import csv, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
num = lambda v: (None if v in ("", None) else (float(v) if "." in v else int(v)))
rd = lambda p: list(csv.DictReader(open(D / p, encoding="utf-8")))

def cols(rows, keys, conv=num):
    return {k: [conv(r[k]) if k != "date" and k not in ("type","name","start","mode","note","brand","default","bed","wake") else r[k] for r in rows] for k in keys}

out = {}
runs = rd("stryd/runs.csv")
out["stryd_runs"] = cols(runs, ["date","km","moving_s","power_w","rss","lower_body_stress","hr"])
out["cp"] = cols(rd("stryd/cp_history.csv"), ["date","cp_w","mode"])
out["shoes"] = rd("stryd/shoes.csv")
out["races"] = rd("stryd/races.csv")
out["chicago_laps"] = cols(rd("stryd/chicago2026_laps.csv"), ["lap","start_s","duration_s","distance_m","power_w","hr","cadence","ground_time_ms"])
out["chicago_walk"] = rd("stryd/walking_chicago2026.csv")
daily = rd("garmin/garmin_daily.csv")
out["g_daily"] = cols(daily, ["date","steps","rhr","bb_min","bb_max","stress_avg","kcal","int_mod","int_vig","resp","utc_offset_h"])
sl = rd("garmin/garmin_sleep.csv")
out["g_sleep"] = cols(sl, ["date","sleep_h","deep_h","light_h","rem_h","awake_min"])
acts = rd("garmin/garmin_activities.csv")
out["g_acts"] = cols(acts, ["date","type","km","min","avg_hr","avg_power","load","aerobic_te","kcal"])
out["generated"] = __import__("datetime").date.today().isoformat()
js = "window.DASH = " + json.dumps(out, separators=(",", ":")) + ";\n"
(ROOT / "docs" / "data.js").write_text(js)
print(len(js)//1024, "KB", {k: (len(v["date"]) if isinstance(v, dict) and "date" in v else len(v) if isinstance(v,list) else '') for k, v in out.items()})
