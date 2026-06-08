#!/usr/bin/env python3
"""Export per-date OOR summary for the web app's Historical Lookup tab.

For every date present in either training (2024-2025) or test (2026) data,
emit: { "YYYY-MM-DD": { "visits": N, "oor": M, "rate": M/N, "in": "train"|"test" } }

This lets the web app show ground-truth OOR for any date the user looks up,
so the Programs team can verify the model's calls against reality.
"""
import json
import pandas as pd
from pathlib import Path

# --- Path bootstrap (added when reorganized into the new repo layout) ---
import sys
from pathlib import Path
_HERE = Path(__file__).resolve().parent
# Skye's original repo lives at <repo_root>/skye-original/. From analysis/ or model/ that's ../skye-original/.
SKYE_DIR = (_HERE.parent / "skye-original").resolve()
# Outputs go to <repo_root>/analysis/results/  (script outputs) or <repo_root>/model/  (model files).
if _HERE.name == "analysis":
    RESULTS_DIR = (_HERE / "results").resolve()
elif _HERE.name == "model":
    RESULTS_DIR = _HERE  # exports stay in model/
else:
    RESULTS_DIR = _HERE
RESULTS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(SKYE_DIR))
# --- end bootstrap ---


BASE = RESULTS_DIR
hist = pd.read_csv(BASE / "public_ara_data" / "water_quality.csv")
hist["date"] = pd.to_datetime(hist["Date of data collection"], format="mixed")
hist["year"] = hist["date"].dt.year

# Same filters as Skye's training set
mask = ((hist["region"] == "Eluru") & (hist["Type"] == "Morning") &
        (hist["Is follow up"] == "No"))
train_2425 = hist[mask & hist["year"].between(2024, 2025)].copy()

# Test set (2026 Q1)
test_2026 = pd.read_csv(BASE / "2026 ARA WQ WG Morning Non-Follow-up.csv")
test_2026["date"] = pd.to_datetime(test_2026["Date of data collection"], format="mixed")

def to_oor_dict(df, label):
    df = df.copy()
    df["oor"] = (df["Is WQ in range?"] == "No").astype(int)
    g = df.groupby(df["date"].dt.date).agg(visits=("oor","size"), oor=("oor","sum"))
    out = {}
    for d, row in g.iterrows():
        out[str(d)] = {
            "visits": int(row["visits"]),
            "oor":    int(row["oor"]),
            "rate":   float(row["oor"] / row["visits"]) if row["visits"] else None,
            "in":     label,
        }
    return out

train_dict = to_oor_dict(train_2425, "train_2024_2025")
test_dict  = to_oor_dict(test_2026,  "test_2026_q1")

# Merge — test overrides train if any overlap (shouldn't be)
combined = {**train_dict, **test_dict}
print(f"Train days: {len(train_dict)}, Test days: {len(test_dict)}, Combined: {len(combined)}")

# Summary stats
total_visits = sum(v["visits"] for v in combined.values())
total_oor    = sum(v["oor"] for v in combined.values())
print(f"Total visits across all dates: {total_visits}")
print(f"Total OOR: {total_oor}")
print(f"Overall OOR rate: {total_oor/total_visits:.1%}")
print(f"Date range: {min(combined)} to {max(combined)}")

# Save
out_path = BASE / "historical_oor_for_webapp.json"
with open(out_path, "w") as f:
    json.dump(combined, f, separators=(",", ":"))
print(f"\n✓ Wrote {out_path} ({out_path.stat().st_size} bytes, {len(combined)} dates)")
