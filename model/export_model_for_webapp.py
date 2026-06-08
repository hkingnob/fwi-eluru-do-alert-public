#!/usr/bin/env python3
"""Train Ridge weather-only model and export everything the web app needs.

Outputs model_for_webapp.json with:
  - feature_order: list of 37 weather feature names in the order the model expects
  - scaler_mean, scaler_std: per-feature standardization parameters
  - ridge_coef, ridge_intercept: linear weights
  - training_score_distribution: predicted DO scores on training data
  - thresholds: percentile cuts (top 5%, 10%, 20%) of "risk score" (= -DO)
  - lag_var_names: 8 weather variables that have 3-day and 7-day rolling averages
  - openmeteo_var_map: how Open-Meteo names map to the model's feature names
  - sanity_test: a few real test-set rows + their model predictions
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

from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

BASE_DIR = Path(__file__).parent

# Same weather feature definition as Skye's pipeline
WEATHER_BASE = [re.sub(r'[^A-Za-z0-9_]', '_', v) for v in fwm.WEATHER_DAILY_VARS]
WEATHER_DERIVED = ["temp_range", "humidity_range"]
LAG_VARS = [
    "temperature_2m_mean", "windspeed_10m_max", "relative_humidity_2m_mean",
    "precipitation_sum", "shortwave_radiation_sum", "cloudcover_mean",
    "dewpoint_2m_mean", "pressure_msl_mean",
]
WEATHER_LAGS = [f"{v}_{w}d_avg" for v in LAG_VARS for w in (7, 3)]
WEATHER_FEATURES = WEATHER_BASE + WEATHER_DERIVED + WEATHER_LAGS  # 19 + 2 + 16 = 37
print(f"Weather features ({len(WEATHER_FEATURES)}): {WEATHER_FEATURES}")

# Load training data the same way Skye does (full year 2024-25 baseline)
hist = pd.read_csv(SKYE_DIR / "public_ara_data" / "water_quality.csv")
hist["date"] = pd.to_datetime(hist["Date of data collection"], format="mixed")
hist["year"] = hist["date"].dt.year
mask = ((hist["region"] == "Eluru") & (hist["Type"] == "Morning") &
        (hist["Is follow up"] == "No") & (hist["year"].between(2024, 2025)))
train_df = hist[mask].copy()

test_2026 = pd.read_csv(SKYE_DIR / "2026 ARA WQ WG Morning Non-Follow-up.csv")
test_2026["date"] = pd.to_datetime(test_2026["Date of data collection"], format="mixed")
test_2026["year"] = test_2026["date"].dt.year
test_2026["region"] = "Eluru"
pond_key = pd.read_csv(SKYE_DIR / "2026 Github ARA Pond IDs Key.csv")
test_2026["pond_id"] = test_2026["Pond ID"].map(
    dict(zip(pond_key["internal_pond_id"], pond_key["public_pond_id"])))

enrolled = pd.read_csv(SKYE_DIR / "public_ara_data" / "enrolled_ponds_2026-02-02.csv")
enrolled_eluru = enrolled[enrolled["region"] == "Eluru"].copy()

weather = fwm.fetch_weather_data(start_date="2024-01-01")

# Engineer features
train_df = fwm.engineer_features(train_df, enrolled_eluru, weather, is_train=True)
test_df  = fwm.engineer_features(test_2026, enrolled_eluru, weather, is_train=False)

# Subset to weather features only
X_train = train_df[WEATHER_FEATURES].copy()
X_test  = test_df[WEATHER_FEATURES].copy()
y_reg_train = train_df["do_mg_l"].copy()
y_reg_test  = test_df["do_mg_l"].copy()

# Impute and scale
imputer = SimpleImputer(strategy="median")
X_train_imp = pd.DataFrame(imputer.fit_transform(X_train), columns=WEATHER_FEATURES, index=X_train.index)
X_test_imp  = pd.DataFrame(imputer.transform(X_test),       columns=WEATHER_FEATURES, index=X_test.index)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train_imp)
X_test_s  = scaler.transform(X_test_imp)

# Fill NaN target with median (same as Skye)
y_reg_train_filled = y_reg_train.fillna(y_reg_train.median())

# Train Ridge
ridge = Ridge(alpha=10.0, random_state=42)
ridge.fit(X_train_s, y_reg_train_filled)

# Predict on training to derive thresholds
train_preds = ridge.predict(X_train_s)
test_preds  = ridge.predict(X_test_s)

# Risk score = -predicted_DO (lower predicted DO = higher risk)
train_risk = -train_preds
test_risk  = -test_preds

# Per-day average risk (the model assigns the same score to all visits on a day,
# but imputation can vary if any features are NaN — average to be safe)
train_df["_risk"] = train_risk
test_df["_risk"]  = test_risk
train_daily_risk = train_df.groupby(train_df["date"].dt.date)["_risk"].mean()
test_daily_risk  = test_df.groupby(test_df["date"].dt.date)["_risk"].mean()

# Percentile thresholds from training-day distribution
thresholds = {
    "top_5_pct":  float(np.percentile(train_daily_risk, 95)),
    "top_10_pct": float(np.percentile(train_daily_risk, 90)),
    "top_20_pct": float(np.percentile(train_daily_risk, 80)),
}
print(f"\nDaily risk-score percentiles (training):")
print(f"  Top 5%  threshold (≥): {thresholds['top_5_pct']:.4f}")
print(f"  Top 10% threshold (≥): {thresholds['top_10_pct']:.4f}")
print(f"  Top 20% threshold (≥): {thresholds['top_20_pct']:.4f}")
print(f"  Min/median/max:        {train_daily_risk.min():.4f} / {train_daily_risk.median():.4f} / {train_daily_risk.max():.4f}")

# Sanity check: how many training days fell into each tier?
n_days = len(train_daily_risk)
for tier, t in [("top_5_pct", thresholds["top_5_pct"]),
                ("top_10_pct", thresholds["top_10_pct"]),
                ("top_20_pct", thresholds["top_20_pct"])]:
    n_above = int((train_daily_risk >= t).sum())
    print(f"  Days at/above {tier} threshold: {n_above}/{n_days} ({100*n_above/n_days:.1f}%)")

# Map model feature names back to Open-Meteo API variable names for the JS code
def _to_model_name(om_var):
    return re.sub(r'[^A-Za-z0-9_]', '_', om_var)

openmeteo_var_map = {_to_model_name(v): v for v in fwm.WEATHER_DAILY_VARS}

# Sanity test: pick 5 test-set days and emit features + expected predictions
sample_dates = sorted(test_df["date"].dt.date.unique())[:5]
sanity = []
for d in sample_dates:
    rows = test_df[test_df["date"].dt.date == d]
    row = rows.iloc[0]
    feat_dict = {f: float(row[f]) if pd.notna(row[f]) else None for f in WEATHER_FEATURES}
    expected = float(ridge.predict(X_test_s[X_test.index.get_loc(row.name):X_test.index.get_loc(row.name)+1])[0])
    sanity.append({
        "date": str(d),
        "expected_predicted_do": expected,
        "expected_risk_score": -expected,
        "first_5_features": {k: feat_dict[k] for k in WEATHER_FEATURES[:5]},
    })

# Test-set evaluation summary (so the web app can quote it accurately)
test_df["_oor"] = (test_df["should_visit"] == 1).astype(int)
test_daily = test_df.groupby(test_df["date"].dt.date).agg(
    risk=("_risk", "mean"), n_visits=("_oor", "size"), n_oor=("_oor", "sum"))
test_daily = test_daily.sort_values("risk", ascending=False)
n_days_test = len(test_daily)
oor_overall = float(test_daily["n_oor"].sum() / test_daily["n_visits"].sum())
print(f"\nTest-set evaluation (Q1 2026), evaluated DAY-LEVEL:")
print(f"  Total days in test: {n_days_test}, total visits: {int(test_daily['n_visits'].sum())}, OOR: {int(test_daily['n_oor'].sum())}")
print(f"  Overall OOR rate: {oor_overall:.1%}")

tier_eval = {}
for label, pct, train_thresh in [
    ("top_5_pct",  0.05, thresholds["top_5_pct"]),
    ("top_10_pct", 0.10, thresholds["top_10_pct"]),
    ("top_20_pct", 0.20, thresholds["top_20_pct"]),
]:
    # (a) by training threshold
    above = test_daily[test_daily["risk"] >= train_thresh]
    n_above = int(len(above))
    visits_above = int(above["n_visits"].sum())
    oor_above = int(above["n_oor"].sum())
    rate_above = oor_above / visits_above if visits_above else 0.0
    lift_above = rate_above / oor_overall if oor_overall else 0.0
    # (b) by exact percentile of test days
    n_top = max(1, int(round(n_days_test * pct)))
    top_n = test_daily.head(n_top)
    visits_top = int(top_n["n_visits"].sum())
    oor_top = int(top_n["n_oor"].sum())
    rate_top = oor_top / visits_top if visits_top else 0.0
    lift_top = rate_top / oor_overall if oor_overall else 0.0
    print(f"  {label}:")
    print(f"    a) Days above training-percentile threshold: {n_above}/{n_days_test} → "
          f"{visits_above} visits, {oor_above} OOR, rate={rate_above:.1%}, lift={lift_above:.2f}x")
    print(f"    b) Top-{int(pct*100)}% of test days ({n_top}/{n_days_test}): "
          f"{visits_top} visits, {oor_top} OOR, rate={rate_top:.1%}, lift={lift_top:.2f}x")
    tier_eval[label] = {
        "training_threshold": train_thresh,
        "by_training_threshold": {
            "n_alert_days": n_above, "n_visits": visits_above, "n_oor": oor_above,
            "rate": rate_above, "lift": lift_above,
        },
        "by_exact_percentile": {
            "n_alert_days": n_top, "n_visits": visits_top, "n_oor": oor_top,
            "rate": rate_top, "lift": lift_top,
        },
    }

# Bundle everything
bundle = {
    "model_name": "FWI Eluru Weather-Only Daily DO Risk (Ridge regression)",
    "trained_on": "Eluru morning non-follow-up visits, Jan 2024 – Dec 2025",
    "feature_order": WEATHER_FEATURES,
    "openmeteo_var_map": openmeteo_var_map,
    "lag_var_names": LAG_VARS,
    "scaler_mean": list(map(float, scaler.mean_)),
    "scaler_std":  list(map(float, scaler.scale_)),
    "ridge_coef":  list(map(float, ridge.coef_)),
    "ridge_intercept": float(ridge.intercept_),
    "imputer_median": list(map(float, imputer.statistics_)),
    "thresholds_risk_score": thresholds,
    "training_daily_risk_summary": {
        "min": float(train_daily_risk.min()),
        "median": float(train_daily_risk.median()),
        "mean": float(train_daily_risk.mean()),
        "max": float(train_daily_risk.max()),
        "n_days": int(len(train_daily_risk)),
    },
    "test_evaluation_q1_2026": {
        "n_days_in_test": int(n_days_test),
        "n_visits_in_test": int(test_daily["n_visits"].sum()),
        "n_oor_in_test": int(test_daily["n_oor"].sum()),
        "overall_oor_rate": oor_overall,
        "tiers": tier_eval,
    },
    "sanity_test_rows": sanity,
}

out_path = RESULTS_DIR / "model_for_webapp.json"
with open(out_path, "w") as f:
    json.dump(bundle, f, indent=2)
print(f"\n✓ Wrote {out_path} ({out_path.stat().st_size} bytes)")
