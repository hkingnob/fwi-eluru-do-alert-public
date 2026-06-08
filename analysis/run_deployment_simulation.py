#!/usr/bin/env python3
"""Simulate deployment policies on YTD 2026 data.

Loads:
  - 2026 YTD measurements from /Skye/2026 measurements YTD.csv (513 visits, 79 days)
  - Skye's exported Ridge weather-only model (model_for_webapp.json)
  - Weather data (cached, extended to today via Open-Meteo if needed)

For every date with at least one visit, computes:
  - observed visits, observed OOR, observed rate
  - model risk score, alert level (NORMAL / ELEVATED / HIGH)

Then simulates these policies (keeping per-day rate as the expected catch rate):
  baseline:    actual observed
  user_proposal:  HIGH × 1.5,  others V_d - 1
  user_strict:    HIGH × 1.5, ELEV unchanged, NORMAL × (V-1)
  reallocate_neutral:  redistribute observed total visits proportional to alert weight
  alert_only:     visits only on HIGH+ELEVATED days (skip Normal entirely)
  inverse:        sanity check — concentrate on NORMAL (should be worse)

Reports total visits, expected total OOR catches, OOR rate, vs baseline.
"""
import json, re, warnings
warnings.filterwarnings("ignore")
import sys
import pandas as pd
import numpy as np
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


sys.path.insert(0, str(Path(__file__).parent))
import fish_welfare_model as fwm

BASE = RESULTS_DIR
YTD_DATA_DIR = (_HERE.parent / "data").resolve()
MODEL_JSON = (_HERE.parent / "model" / "model_for_webapp.json").resolve()

# ---------------------------------------------------------------------------
# Load model + weather
# ---------------------------------------------------------------------------
M = json.load(open(MODEL_JSON))
WEATHER_FEATURES = M["feature_order"]
LAG_VARS = M["lag_var_names"]

weather = fwm.fetch_weather_data(start_date="2024-01-01")  # uses cache
weather["date"] = pd.to_datetime(weather["date"]).dt.normalize()

# Top up missing recent days via direct Open-Meteo call
import requests
needed_through = pd.Timestamp("2026-05-04")
if weather["date"].max() < needed_through:
    print(f"  Cache only goes to {weather['date'].max().date()}; topping up to {needed_through.date()}")
    extra_url = ("https://api.open-meteo.com/v1/forecast?"
                 f"latitude=16.6423&longitude=81.1161&past_days=14&forecast_days=1&timezone=Asia/Kolkata"
                 f"&daily=" + ",".join(fwm.WEATHER_DAILY_VARS))
    try:
        r = requests.get(extra_url, timeout=30); r.raise_for_status()
        extra_data = r.json()["daily"]
    except Exception as e:
        print(f"  WARN: top-up failed ({e}); will skip recent days without weather")
        extra_data = None
    if extra_data is not None:
        extra = pd.DataFrame(extra_data)
        extra["date"] = pd.to_datetime(extra["time"]).dt.normalize()
        extra = extra.drop(columns=["time"])
        extra["temp_range"] = extra["temperature_2m_max"] - extra["temperature_2m_min"]
        extra["humidity_range"] = extra["relative_humidity_2m_max"] - extra["relative_humidity_2m_min"]
        weather = pd.concat([weather, extra], ignore_index=True).drop_duplicates(subset="date", keep="last").sort_values("date").reset_index(drop=True)
        LAG_8 = ["temperature_2m_mean","windspeed_10m_max","relative_humidity_2m_mean",
                 "precipitation_sum","shortwave_radiation_sum","cloudcover_mean",
                 "dewpoint_2m_mean","pressure_msl_mean"]
        for v in LAG_8:
            weather[f"{v}_7d_avg"] = weather[v].rolling(7, min_periods=1).mean()
            weather[f"{v}_3d_avg"] = weather[v].rolling(3, min_periods=1).mean()
print(f"Weather coverage: {weather['date'].min().date()} to {weather['date'].max().date()} ({len(weather)} days)")

# Build per-date feature row matching engineer_features
# For a single date, we only need the weather row for that date; lagged vars are already in cache.
def features_for_date(d):
    row = weather[weather["date"] == pd.Timestamp(d)]
    if row.empty:
        return None
    r = row.iloc[0]
    f = {}
    for name in WEATHER_FEATURES:
        if name in r.index:
            f[name] = float(r[name]) if pd.notna(r[name]) else None
        else:
            f[name] = None
    # Derived (computed in the cache)
    if "temp_range" not in r.index:
        f["temp_range"] = float(r["temperature_2m_max"]) - float(r["temperature_2m_min"])
    if "humidity_range" not in r.index:
        f["humidity_range"] = float(r["relative_humidity_2m_max"]) - float(r["relative_humidity_2m_min"])
    return f

def predict(features):
    z = M["ridge_intercept"]
    for i, k in enumerate(WEATHER_FEATURES):
        v = features.get(k) if features else None
        if v is None or (isinstance(v, float) and np.isnan(v)):
            v = M["imputer_median"][i]
        z += M["ridge_coef"][i] * (v - M["scaler_mean"][i]) / M["scaler_std"][i]
    return z

def classify(predicted_do):
    rs = -predicted_do
    t = M["thresholds_risk_score"]
    if rs >= t["top_5_pct"]:  return "HIGH+"   # within HIGH but at top 5
    if rs >= t["top_10_pct"]: return "HIGH"
    if rs >= t["top_20_pct"]: return "ELEVATED"
    return "NORMAL"

# ---------------------------------------------------------------------------
# Load YTD data and aggregate per day
# ---------------------------------------------------------------------------
ytd = pd.read_csv(YTD_DATA_DIR / "2026_measurements_YTD_anonymized.csv")
ytd["date"] = pd.to_datetime(ytd["Date of data collection"], format="%m/%d/%Y", errors="coerce")
assert ytd["date"].notna().all(), "Some dates failed to parse"
ytd["oor"] = (ytd["Is WQ in range?"] == "No").astype(int)
ytd["pond_id"] = ytd["Pond ID"]

daily = ytd.groupby(ytd["date"].dt.date).agg(
    visits=("pond_id", "count"),
    oor=("oor", "sum"),
).reset_index().rename(columns={"date": "d"})
daily["d"] = pd.to_datetime(daily["d"])
daily["rate"] = daily["oor"] / daily["visits"]

# Score each date
predictions = []
for d in daily["d"]:
    feats = features_for_date(d.date())
    if feats is None:
        print(f"  WARN: no weather for {d.date()}, skipping")
        predictions.append({"predicted_do": None, "alert": None})
        continue
    pdo = predict(feats)
    predictions.append({"predicted_do": pdo, "alert": classify(pdo)})

daily["predicted_do"] = [p["predicted_do"] for p in predictions]
daily["risk_score"]   = [-p["predicted_do"] if p["predicted_do"] is not None else None for p in predictions]
daily["alert"]        = [p["alert"] for p in predictions]

print(f"\nYTD coverage: {daily['d'].min().date()} to {daily['d'].max().date()}")
print(f"Days: {len(daily)}, total visits: {int(daily['visits'].sum())}, total OOR: {int(daily['oor'].sum())}")
print(f"Baseline OOR rate: {daily['oor'].sum() / daily['visits'].sum():.1%}")
print()

# Alert distribution
alert_counts = daily["alert"].value_counts()
alert_visits = daily.groupby("alert")["visits"].sum()
alert_oor    = daily.groupby("alert")["oor"].sum()
alert_rate   = alert_oor / alert_visits
print(f"Alert distribution YTD:")
print(f"{'Alert':<10} {'Days':>6} {'Visits':>8} {'OOR':>6} {'Rate':>8}")
for a in ["HIGH+", "HIGH", "ELEVATED", "NORMAL"]:
    nd = int(alert_counts.get(a, 0))
    nv = int(alert_visits.get(a, 0))
    no = int(alert_oor.get(a, 0))
    rt = no / nv if nv else 0.0
    print(f"  {a:<8} {nd:>6} {nv:>8} {no:>6} {rt*100:>6.1f}%")
print()

# ---------------------------------------------------------------------------
# Simulate policies
# ---------------------------------------------------------------------------
# Helper: for a vector of new visit counts (per day), compute expected OOR
def simulate(new_visits_per_day, label):
    """new_visits_per_day: array same length as `daily`, possibly fractional."""
    # Per-day expected OOR = new_visits × observed_rate
    # For days with observed visits=0 we'd have rate=NaN; treat new visits as 0.
    nv = np.array(new_visits_per_day, dtype=float)
    rate = daily["rate"].fillna(0.0).values
    expected_oor = nv * rate
    total_v = float(nv.sum())
    total_o = float(expected_oor.sum())
    rate_overall = total_o / total_v if total_v else 0.0
    return {
        "label": label,
        "total_visits": total_v,
        "expected_oor": total_o,
        "oor_rate": rate_overall,
    }

# Treat HIGH+ as HIGH for grouping (HIGH+ is just the top 5% subset of HIGH)
def is_high(a): return a in ("HIGH", "HIGH+")

# Baseline: observed (also same as simulating with V_d unchanged)
res_baseline = simulate(daily["visits"].values, "baseline (observed)")
res_baseline["expected_oor"] = float(daily["oor"].sum())  # use actual not expected
res_baseline["oor_rate"]     = res_baseline["expected_oor"] / res_baseline["total_visits"]

# Policy: user's proposal (HIGH × 1.5, others V-1)
nv = []
for _, row in daily.iterrows():
    if is_high(row["alert"]):
        nv.append(row["visits"] * 1.5)
    else:
        nv.append(max(0, row["visits"] - 1))
res_user = simulate(nv, "user_proposal: HIGH×1.5, others V-1")

# Policy: user_strict — HIGH × 1.5, ELEVATED unchanged, NORMAL × (V-1)
nv = []
for _, row in daily.iterrows():
    if is_high(row["alert"]):                 nv.append(row["visits"] * 1.5)
    elif row["alert"] == "ELEVATED":          nv.append(row["visits"])
    else:                                      nv.append(max(0, row["visits"] - 1))
res_user_strict = simulate(nv, "user_strict: HIGH×1.5, ELEV=, NORMAL V-1")

# Policy: reallocate_neutral — keep total visits constant, weight by alert tier
WEIGHTS = {"HIGH+": 2.5, "HIGH": 2.0, "ELEVATED": 1.5, "NORMAL": 1.0, None: 1.0}
weight_per_day = np.array([WEIGHTS.get(a,1.0) for a in daily["alert"]], dtype=float)
# Weighted shares — but only for days that already had visits (we can't visit days with no visits)
visited_mask = (daily["visits"] > 0).values
weighted_share = weight_per_day * visited_mask
weighted_share = weighted_share / weighted_share.sum()
total_v_baseline = daily["visits"].sum()
nv = weighted_share * total_v_baseline
# Round to integers for "what would be done in practice"
res_realloc = simulate(nv, "reallocate_neutral: keep total visits, weight 2.5/2/1.5/1")

# Policy: alert_only — visit only on HIGH or ELEVATED days
nv = [row["visits"] if (is_high(row["alert"]) or row["alert"] == "ELEVATED") else 0
      for _, row in daily.iterrows()]
res_alert_only = simulate(nv, "alert_only: visit only HIGH+ELEVATED days")

# Policy: high_only — visit only on HIGH
nv = [row["visits"] if is_high(row["alert"]) else 0 for _, row in daily.iterrows()]
res_high_only = simulate(nv, "high_only: visit only HIGH days")

# Policy: inverse (sanity check) — concentrate on NORMAL only
nv = [row["visits"] if row["alert"] == "NORMAL" else 0 for _, row in daily.iterrows()]
res_inverse = simulate(nv, "inverse (sanity): NORMAL only")

# Policy: capacity-neutral concentrated — HIGH×1.5 minus N from NORMAL such that total stays equal to baseline
high_extras = sum(row["visits"] * 0.5 for _, row in daily.iterrows() if is_high(row["alert"]))
n_normal_days = sum(1 for _, row in daily.iterrows() if row["alert"] == "NORMAL")
shave_per_normal_day = high_extras / n_normal_days if n_normal_days else 0
nv = []
for _, row in daily.iterrows():
    if is_high(row["alert"]):       nv.append(row["visits"] * 1.5)
    elif row["alert"] == "NORMAL":  nv.append(max(0, row["visits"] - shave_per_normal_day))
    else:                            nv.append(row["visits"])
res_neutral_user = simulate(nv, f"capacity-neutral: HIGH×1.5, NORMAL each -{shave_per_normal_day:.2f}")

# Policy: binary "alert vs normal" (combine HIGH and ELEVATED into one tier)
# Capacity-neutral: shift visits from NORMAL to alert days at constant total
def is_alert(a): return is_high(a) or a == "ELEVATED"
n_alert_days  = int(sum(is_alert(a) for a in daily["alert"]))
n_normal_days = int(sum(a == "NORMAL" for a in daily["alert"]))
# Shift X visits per alert day FROM 1 visit per normal day (X = normal_days / alert_days)
add_per_alert = (n_normal_days / n_alert_days) if n_alert_days else 0
nv = []
for _, row in daily.iterrows():
    if is_alert(row["alert"]):    nv.append(row["visits"] + add_per_alert)
    elif row["alert"] == "NORMAL": nv.append(max(0, row["visits"] - 1))
    else:                          nv.append(row["visits"])
res_binary_neutral = simulate(nv, f"binary_neutral: alert +{add_per_alert:.2f}, normal -1")

# Policy: binary x1.5 — alert tier × 1.5, normal V-1 (matches user's spec, but combined alert)
nv = []
for _, row in daily.iterrows():
    if is_alert(row["alert"]):    nv.append(row["visits"] * 1.5)
    elif row["alert"] == "NORMAL": nv.append(max(0, row["visits"] - 1))
    else:                          nv.append(row["visits"])
res_binary_15x = simulate(nv, "binary_user-style: alert(=HIGH+ELEV)×1.5, normal V-1")

results = [res_baseline, res_user, res_user_strict, res_realloc,
           res_alert_only, res_high_only, res_inverse, res_neutral_user,
           res_binary_neutral, res_binary_15x]

print(f"\n{'Policy':<55} {'Visits':>7} {'OOR':>6} {'Rate':>7} {'Δvisits':>8} {'ΔOOR':>7} {'ΔRate':>7}")
print("-" * 100)
b_v = res_baseline["total_visits"]
b_o = res_baseline["expected_oor"]
b_r = res_baseline["oor_rate"]
for r in results:
    dv = r["total_visits"] - b_v
    do = r["expected_oor"] - b_o
    dr = r["oor_rate"] - b_r
    print(f"{r['label']:<55} {r['total_visits']:>7.0f} {r['expected_oor']:>6.1f} {r['oor_rate']*100:>6.1f}% "
          f"{dv:>+8.0f} {do:>+7.1f} {dr*100:>+6.1f}p")

# Save daily detail
daily_out = daily.copy()
daily_out["d"] = daily_out["d"].dt.strftime("%Y-%m-%d")
daily_out.to_csv(BASE / "ytd_daily_with_alerts.csv", index=False)
print(f"\n✓ Saved per-day detail to ytd_daily_with_alerts.csv")

# Save policy comparison
import csv
with open(BASE / "ytd_policy_comparison.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["policy","total_visits","expected_oor","oor_rate","delta_visits","delta_oor","delta_rate_pp"])
    for r in results:
        w.writerow([r["label"], round(r["total_visits"],1), round(r["expected_oor"],2),
                    round(r["oor_rate"]*100,2),
                    round(r["total_visits"]-b_v,1), round(r["expected_oor"]-b_o,2),
                    round((r["oor_rate"]-b_r)*100,2)])
print(f"✓ Saved policy comparison to ytd_policy_comparison.csv")
