#!/usr/bin/env python3
"""
Fish Welfare — Experiment Runner

Implements experiments #1-4 from Future Experiments.md:
  1. Seasonal training windows (Jan-Mar only)
  2. Feature selection (reduce to top ~26 features)
  3. Rank product ensemble (weather-only × farm-only)
  4. XGBoost with max_depth=2 + early stopping

Each experiment is compared against the v3 baseline.

Usage:
    uv run --with pandas --with openpyxl --with scikit-learn --with xgboost \
           --with lightgbm --with matplotlib --with seaborn --with requests \
           python3 experiments.py
"""

import warnings
warnings.filterwarnings("ignore")

import re
import pandas as pd
import numpy as np
import requests
from pathlib import Path
from scipy.stats import rankdata

from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, f1_score
import xgboost as xgb
import lightgbm as lgb

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).parent
DO_OOR_THRESHOLD = 3.0

ELURU_LAT = 16.6423
ELURU_LON = 81.1161

WEATHER_DAILY_VARS = [
    "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
    "apparent_temperature_max", "apparent_temperature_min", "apparent_temperature_mean",
    "precipitation_sum", "rain_sum",
    "windspeed_10m_max", "windgusts_10m_max", "winddirection_10m_dominant",
    "shortwave_radiation_sum", "et0_fao_evapotranspiration",
    "relative_humidity_2m_max", "relative_humidity_2m_min", "relative_humidity_2m_mean",
    "dewpoint_2m_mean", "pressure_msl_mean", "cloudcover_mean",
]

WEATHER_CACHE_PATH = BASE_DIR / "weather_cache_eluru.csv"


# ============================================================================
# DATA LOADING (shared)
# ============================================================================

def load_weather():
    """Load cached weather or download."""
    if WEATHER_CACHE_PATH.exists():
        return pd.read_csv(WEATHER_CACHE_PATH, parse_dates=["date"])
    
    from datetime import date, timedelta
    end_date = (date.today() - timedelta(days=1)).isoformat()
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": ELURU_LAT, "longitude": ELURU_LON,
        "start_date": "2024-01-01", "end_date": end_date,
        "daily": ",".join(WEATHER_DAILY_VARS), "timezone": "Asia/Kolkata",
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    weather = pd.DataFrame(data["daily"])
    weather["date"] = pd.to_datetime(weather["time"])
    weather = weather.drop(columns=["time"])
    
    lag_vars = ["temperature_2m_mean", "windspeed_10m_max", "relative_humidity_2m_mean",
                "precipitation_sum", "shortwave_radiation_sum", "cloudcover_mean",
                "dewpoint_2m_mean", "pressure_msl_mean"]
    for var in lag_vars:
        if var in weather.columns:
            weather[f"{var}_7d_avg"] = weather[var].rolling(7, min_periods=1).mean()
            weather[f"{var}_3d_avg"] = weather[var].rolling(3, min_periods=1).mean()
    
    weather["temp_range"] = weather["temperature_2m_max"] - weather["temperature_2m_min"]
    weather["humidity_range"] = weather["relative_humidity_2m_max"] - weather["relative_humidity_2m_min"]
    weather.to_csv(WEATHER_CACHE_PATH, index=False)
    return weather


def load_all_data():
    """Load all data sources."""
    hist = pd.read_csv(BASE_DIR / "public_ara_data" / "water_quality.csv")
    hist["date"] = pd.to_datetime(hist["Date of data collection"], format="mixed")
    hist["year"] = hist["date"].dt.year

    test_2026 = pd.read_csv(BASE_DIR / "2026 ARA WQ WG Morning Non-Follow-up.csv")
    test_2026["date"] = pd.to_datetime(test_2026["Date of data collection"], format="mixed")
    test_2026["year"] = test_2026["date"].dt.year
    test_2026["region"] = "Eluru"
    pond_key = pd.read_csv(BASE_DIR / "2026 Github ARA Pond IDs Key.csv")
    pond_map = dict(zip(pond_key["internal_pond_id"], pond_key["public_pond_id"]))
    test_2026["pond_id"] = test_2026["Pond ID"].map(pond_map)

    enrolled = pd.read_csv(BASE_DIR / "public_ara_data" / "enrolled_ponds_2026-02-02.csv")
    enrolled_eluru = enrolled[enrolled["region"] == "Eluru"].copy()

    weather = load_weather()

    # Full train: Eluru, Morning, non-follow-up, 2024-2025
    mask_full = (
        (hist["region"] == "Eluru") & (hist["Type"] == "Morning") &
        (hist["Is follow up"] == "No") & (hist["year"] >= 2024) & (hist["year"] <= 2025)
    )
    train_full = hist[mask_full].copy()

    # Seasonal train: same but only Jan, Feb, Mar
    train_seasonal = train_full[train_full["date"].dt.month.isin([1, 2, 3])].copy()

    return {
        "train_full": train_full,
        "train_seasonal": train_seasonal,
        "test": test_2026,
        "enrolled": enrolled_eluru,
        "weather": weather,
    }


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

def engineer_features(df, enrolled, weather):
    """Create features. Returns df with features and targets appended."""
    df = df.copy()
    df["should_visit"] = (df["Is WQ in range?"] == "No").astype(int)
    df["do_mg_l"] = pd.to_numeric(df["DO (mg/L)"], errors="coerce")

    # Weather merge
    df["date_only"] = df["date"].dt.normalize()
    wc = weather.copy()
    wc["date_only"] = wc["date"].dt.normalize()
    df = df.merge(wc.drop(columns=["date"]), on="date_only", how="left")
    df = df.drop(columns=["date_only"])

    # Temporal
    df["month"] = df["date"].dt.month
    df["day_of_week"] = df["date"].dt.dayofweek
    season_map = {1: "dry", 2: "dry", 3: "dry", 4: "pre_monsoon", 5: "pre_monsoon",
                  6: "pre_monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon",
                  10: "post_monsoon", 11: "post_monsoon", 12: "post_monsoon"}
    df["season"] = df["month"].map(season_map)
    month_dummies = pd.get_dummies(df["month"], prefix="month", dtype=int)
    season_dummies = pd.get_dummies(df["season"], prefix="season", dtype=int)
    df = pd.concat([df, month_dummies, season_dummies], axis=1)

    # Farm enrollment
    farm_cols = ["pond_id", "Pond area in acres", "Depth in meters", "Feed type"]
    available = [c for c in farm_cols if c in enrolled.columns]
    farm_data = enrolled[available].drop_duplicates(subset=["pond_id"])
    df = df.merge(farm_data, on="pond_id", how="left")
    df["pond_area"] = pd.to_numeric(df.get("Pond area in acres", pd.Series(dtype=float)), errors="coerce")
    df["pond_depth"] = pd.to_numeric(df.get("Depth in meters", pd.Series(dtype=float)), errors="coerce")
    if "Feed type" in df.columns:
        df["Feed type"] = df["Feed type"].fillna("Unknown")
        feed_dummies = pd.get_dummies(df["Feed type"], prefix="feed_type", dtype=int)
        df = pd.concat([df, feed_dummies], axis=1)

    # Historical
    df = df.sort_values(["pond_id", "date"]).reset_index(drop=True)
    df["feed_amount"] = pd.to_numeric(df["Feed amount (kg)"], errors="coerce")
    df["stocking_density"] = pd.to_numeric(df["Stocking density (per acre)"], errors="coerce")
    df["prev_feed_amount"] = df.groupby("pond_id")["feed_amount"].shift(1)
    df["prev_stocking_density"] = df.groupby("pond_id")["stocking_density"].shift(1)

    oor_rates = []
    pond_history = {}
    for _, row in df.iterrows():
        pid = row["pond_id"]
        if pid not in pond_history:
            pond_history[pid] = []
        oor_rates.append(np.mean(pond_history[pid]) if pond_history[pid] else np.nan)
        pond_history[pid].append(row["should_visit"])
    df["pond_historical_oor_rate"] = oor_rates

    df["prev_do"] = df.groupby("pond_id")["do_mg_l"].shift(1)
    df["days_since_last_visit"] = df.groupby("pond_id")["date"].diff().dt.days
    df["n_previous_visits"] = df.groupby("pond_id").cumcount()
    total_fish = df["prev_stocking_density"] * df["pond_area"]
    df["prev_feed_per_fish"] = np.where(total_fish > 0, df["prev_feed_amount"] / total_fish, np.nan)

    # Sanitize
    df.columns = [re.sub(r'[^A-Za-z0-9_]', '_', c) for c in df.columns]
    return df


def get_weather_features():
    """19 base weather + 16 lagged + 2 derived = 37 weather features."""
    base = [re.sub(r'[^A-Za-z0-9_]', '_', v) for v in WEATHER_DAILY_VARS]
    derived = ["temp_range", "humidity_range"]
    lags = []
    for var in ["temperature_2m_mean", "windspeed_10m_max", "relative_humidity_2m_mean",
                "precipitation_sum", "shortwave_radiation_sum", "cloudcover_mean",
                "dewpoint_2m_mean", "pressure_msl_mean"]:
        lags.extend([f"{var}_7d_avg", f"{var}_3d_avg"])
    return base + derived + lags


def get_farm_features(df):
    """Farm enrollment + historical features."""
    feed_cols = [c for c in df.columns if c.startswith("feed_type_")]
    return [
        "pond_area", "pond_depth", *feed_cols,
        "prev_feed_amount", "prev_stocking_density", "prev_feed_per_fish",
        "prev_do", "pond_historical_oor_rate", "days_since_last_visit",
        "n_previous_visits",
    ]


def get_temporal_features(df):
    """Calendar features."""
    month_cols = [c for c in df.columns if c.startswith("month_")]
    season_cols = [c for c in df.columns if c.startswith("season_")]
    return [*month_cols, *season_cols, "day_of_week"]


def get_all_features(df):
    """All 71 features."""
    weather = get_weather_features()
    farm = get_farm_features(df)
    temporal = get_temporal_features(df)
    return [c for c in weather + farm + temporal if c in df.columns]


def get_selected_features(df):
    """
    Experiment #2: Reduced feature set (~26 features).
    19 base weather + pond_area + pond_depth + feed_type (top 3 only) +
    pond_historical_oor_rate + prev_do + days_since_last_visit + day_of_week
    """
    base_weather = [re.sub(r'[^A-Za-z0-9_]', '_', v) for v in WEATHER_DAILY_VARS]
    
    farm_selected = [
        "pond_area", "pond_depth",
        "pond_historical_oor_rate", "prev_do", "days_since_last_visit",
    ]
    
    # Keep only the top feed types (DORB, Mash, Pelleted)
    feed_selected = [c for c in df.columns if c.startswith("feed_type_") and 
                     any(k in c for k in ["DORB", "Mash", "Pelleted", "Unknown"])]
    
    temporal_selected = ["day_of_week"]
    
    all_sel = base_weather + farm_selected + feed_selected + temporal_selected
    return [c for c in all_sel if c in df.columns]


# ============================================================================
# EVALUATION HELPERS
# ============================================================================

def compute_metrics(y_true, y_score, label=""):
    """Compute AUC, lift, F1 from scores."""
    try:
        auc = roc_auc_score(y_true, y_score)
    except ValueError:
        auc = float("nan")

    n = len(y_true)
    sorted_idx = np.argsort(-y_score)
    y_sorted = y_true.values[sorted_idx] if hasattr(y_true, 'values') else y_true[sorted_idx]
    base_rate = y_true.mean() if hasattr(y_true, 'mean') else np.mean(y_true)

    k5 = max(1, int(0.05 * n))
    k10 = max(1, int(0.10 * n))
    k20 = max(1, int(0.20 * n))
    prec5 = y_sorted[:k5].mean()
    prec10 = y_sorted[:k10].mean()
    prec20 = y_sorted[:k20].mean()
    lift5 = prec5 / base_rate if base_rate > 0 else float("nan")
    lift10 = prec10 / base_rate if base_rate > 0 else float("nan")
    lift20 = prec20 / base_rate if base_rate > 0 else float("nan")

    return {
        "AUC": auc, "Prec@5%": prec5, "Prec@10%": prec10, "Prec@20%": prec20,
        "Lift@5%": lift5, "Lift@10%": lift10, "Lift@20%": lift20,
    }


def prepare_xy(train_df, test_df, feature_cols):
    """Prepare X/y matrices with imputation and scaling."""
    # Align columns
    for c in feature_cols:
        if c not in train_df.columns:
            train_df[c] = 0
        if c not in test_df.columns:
            test_df[c] = 0

    feature_cols = [c for c in feature_cols if c in train_df.columns and c in test_df.columns]

    X_train = train_df[feature_cols].copy()
    X_test = test_df[feature_cols].copy()
    y_train = train_df["should_visit"].copy()
    y_test = test_df["should_visit"].copy()
    y_reg_train = train_df["do_mg_l"].copy()
    y_reg_test = test_df["do_mg_l"].copy()

    # Fill binary cols
    binary_cols = [c for c in feature_cols if c.startswith(("month_", "season_", "feed_type_"))]
    for c in binary_cols:
        X_train[c] = X_train[c].fillna(0)
        X_test[c] = X_test[c].fillna(0)

    # Drop all-NaN
    all_nan = [c for c in feature_cols if X_train[c].isna().all()]
    if all_nan:
        feature_cols = [c for c in feature_cols if c not in all_nan]
        X_train = X_train[feature_cols]
        X_test = X_test[feature_cols]

    # Impute
    imputer = SimpleImputer(strategy="median")
    X_train_imp = pd.DataFrame(imputer.fit_transform(X_train), columns=feature_cols, index=X_train.index)
    X_test_imp = pd.DataFrame(imputer.transform(X_test), columns=feature_cols, index=X_test.index)

    # Scale
    scaler = StandardScaler()
    X_train_s = pd.DataFrame(scaler.fit_transform(X_train_imp), columns=feature_cols, index=X_train.index)
    X_test_s = pd.DataFrame(scaler.transform(X_test_imp), columns=feature_cols, index=X_test.index)

    return {
        "X_train": X_train_imp, "X_test": X_test_imp,
        "X_train_s": X_train_s, "X_test_s": X_test_s,
        "y_train": y_train, "y_test": y_test,
        "y_reg_train": y_reg_train, "y_reg_test": y_reg_test,
        "feature_cols": feature_cols,
    }


# ============================================================================
# EXPERIMENT RUNNERS
# ============================================================================

def run_standard_models(data, experiment_name):
    """Run Logistic Regression, Ridge, XGBoost, LightGBM and collect results."""
    X_tr, X_te = data["X_train"], data["X_test"]
    X_trs, X_tes = data["X_train_s"], data["X_test_s"]
    y_tr, y_te = data["y_train"], data["y_test"]
    y_rtr, y_rte = data["y_reg_train"], data["y_reg_test"]

    n_pos = y_tr.sum()
    n_neg = len(y_tr) - n_pos
    spw = n_neg / max(n_pos, 1)

    results = {}

    # -- Logistic Regression (classifier) --
    lr = LogisticRegression(class_weight="balanced", max_iter=1000, C=0.1, random_state=42)
    lr.fit(X_trs, y_tr)
    y_prob = lr.predict_proba(X_tes)[:, 1]
    m = compute_metrics(y_te, y_prob)
    results[f"{experiment_name} | Logistic Reg"] = m

    # -- Ridge Regression (regressor → derived AUC) --
    ridge = Ridge(alpha=10.0)
    ridge.fit(X_trs, y_rtr)
    y_pred_do = ridge.predict(X_tes)
    y_risk = -y_pred_do  # lower DO = higher risk
    m = compute_metrics(y_te, y_risk)
    m["R²"] = 1 - np.sum((y_rte - y_pred_do)**2) / np.sum((y_rte - y_rte.mean())**2)
    results[f"{experiment_name} | Ridge (derived)"] = m

    # -- XGBoost Classifier --
    xgb_clf = xgb.XGBClassifier(
        n_estimators=200, max_depth=3, learning_rate=0.05,
        min_child_weight=10, subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=spw, eval_metric="logloss",
        reg_alpha=1.0, reg_lambda=5.0, random_state=42, use_label_encoder=False
    )
    xgb_clf.fit(X_tr, y_tr)
    y_prob = xgb_clf.predict_proba(X_te)[:, 1]
    m = compute_metrics(y_te, y_prob)
    results[f"{experiment_name} | XGBoost"] = m

    # -- LightGBM Classifier --
    lgb_clf = lgb.LGBMClassifier(
        n_estimators=200, max_depth=3, learning_rate=0.05,
        min_child_samples=10, subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=spw, reg_alpha=1.0, reg_lambda=5.0,
        random_state=42, verbose=-1
    )
    lgb_clf.fit(X_tr, y_tr)
    y_prob = lgb_clf.predict_proba(X_te)[:, 1]
    m = compute_metrics(y_te, y_prob)
    results[f"{experiment_name} | LightGBM"] = m

    return results


def run_experiment_4_xgb_tuned(data, experiment_name):
    """Experiment #4: XGBoost with max_depth=2 and early stopping."""
    X_tr, X_te = data["X_train"], data["X_test"]
    y_tr, y_te = data["y_train"], data["y_test"]
    
    n_pos = y_tr.sum()
    n_neg = len(y_tr) - n_pos
    spw = n_neg / max(n_pos, 1)

    # Use time-based validation: last 30% of training data
    n_val = int(0.3 * len(X_tr))
    X_val = X_tr.iloc[-n_val:]
    y_val = y_tr.iloc[-n_val:]
    X_tr_sub = X_tr.iloc[:-n_val]
    y_tr_sub = y_tr.iloc[:-n_val]

    results = {}

    # max_depth=2 with early stopping
    for lr_val in [0.01, 0.03, 0.05]:
        model = xgb.XGBClassifier(
            n_estimators=1000, max_depth=2, learning_rate=lr_val,
            min_child_weight=10, subsample=0.8, colsample_bytree=0.7,
            scale_pos_weight=spw, eval_metric="auc",
            reg_alpha=1.0, reg_lambda=5.0,
            random_state=42, use_label_encoder=False,
            early_stopping_rounds=50,
        )
        model.fit(X_tr_sub, y_tr_sub, eval_set=[(X_val, y_val)], verbose=False)
        best_iter = model.best_iteration
        y_prob = model.predict_proba(X_te)[:, 1]
        m = compute_metrics(y_te, y_prob)
        m["best_iter"] = best_iter
        name = f"{experiment_name} | XGB d2 lr={lr_val}"
        results[name] = m
    
    # Also try max_depth=2 with full training data, best_iter found above
    best_config = max(results, key=lambda k: results[k]["AUC"])
    best_lr = float(best_config.split("lr=")[1])
    best_n = int(results[best_config].get("best_iter", 200))
    
    model_full = xgb.XGBClassifier(
        n_estimators=max(best_n, 50), max_depth=2, learning_rate=best_lr,
        min_child_weight=10, subsample=0.8, colsample_bytree=0.7,
        scale_pos_weight=spw, eval_metric="logloss",
        reg_alpha=1.0, reg_lambda=5.0,
        random_state=42, use_label_encoder=False,
    )
    model_full.fit(X_tr, y_tr)
    y_prob = model_full.predict_proba(X_te)[:, 1]
    m = compute_metrics(y_te, y_prob)
    m["n_estimators"] = max(best_n, 50)
    m["learning_rate"] = best_lr
    results[f"{experiment_name} | XGB d2 full (lr={best_lr}, n={max(best_n, 50)})"] = m

    return results, model_full


def run_experiment_3_rank_product(train_df, test_df, enrolled, weather):
    """Experiment #3: Rank product of weather-only × farm-only models."""
    # Engineer features for both
    train_eng = engineer_features(train_df, enrolled, weather)
    test_eng = engineer_features(test_df, enrolled, weather)

    y_test = test_eng["should_visit"]
    results = {}

    # -- Weather-Only Model (ranks days, not ponds) --
    weather_feats = get_weather_features()
    weather_feats = [c for c in weather_feats if c in train_eng.columns and c in test_eng.columns]

    wd = prepare_xy(train_eng, test_eng, weather_feats)
    
    # Ridge regression on weather only
    ridge_w = Ridge(alpha=10.0)
    ridge_w.fit(wd["X_train_s"], wd["y_reg_train"])
    weather_score = -ridge_w.predict(wd["X_test_s"])  # lower DO = higher risk
    
    m = compute_metrics(y_test, weather_score)
    results["Rank Product | Weather-Only (Ridge)"] = m

    # -- Farm-Only Model (ranks ponds, not days) --
    farm_feats = get_farm_features(train_eng)
    farm_feats = [c for c in farm_feats if c in train_eng.columns and c in test_eng.columns]

    fd = prepare_xy(train_eng, test_eng, farm_feats)

    # Logistic regression on farm only
    lr_f = LogisticRegression(class_weight="balanced", max_iter=1000, C=0.1, random_state=42)
    lr_f.fit(fd["X_train_s"], fd["y_train"])
    farm_score = lr_f.predict_proba(fd["X_test_s"])[:, 1]
    
    m = compute_metrics(y_test, farm_score)
    results["Rank Product | Farm-Only (LR)"] = m

    # -- Rank Product: combine --
    # Convert to ranks (1 = highest risk)
    weather_rank = rankdata(-weather_score)  # highest score → rank 1
    farm_rank = rankdata(-farm_score)
    
    # Rank product (lower = higher risk)
    rank_product = weather_rank * farm_rank
    combined_score = -rank_product  # negate so higher score = higher risk
    
    m = compute_metrics(y_test, combined_score)
    results["Rank Product | Weather × Farm"] = m

    # Also try z-score sum (alternative combination)
    w_z = (weather_score - weather_score.mean()) / (weather_score.std() + 1e-8)
    f_z = (farm_score - farm_score.mean()) / (farm_score.std() + 1e-8)
    zscore_sum = w_z + f_z
    
    m = compute_metrics(y_test, zscore_sum)
    results["Rank Product | Z-Score Sum"] = m

    return results


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║  Fish Welfare — Experiment Runner (Experiments #1-4)               ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    all_data = load_all_data()
    train_full = all_data["train_full"]
    train_seasonal = all_data["train_seasonal"]
    test = all_data["test"]
    enrolled = all_data["enrolled"]
    weather = all_data["weather"]

    print(f"\n  Train (full year): {len(train_full)} rows")
    print(f"  Train (seasonal Jan-Mar): {len(train_seasonal)} rows")
    print(f"  Test (2026 Jan-Mar): {len(test)} rows")

    # Engineer features for all sets
    print("\n  Engineering features...")
    train_full_eng = engineer_features(train_full, enrolled, weather)
    train_seasonal_eng = engineer_features(train_seasonal, enrolled, weather)
    test_eng = engineer_features(test, enrolled, weather)

    all_results = {}

    # ================================================================
    # BASELINE: v3 (all features, full-year training)
    # ================================================================
    print("\n" + "=" * 70)
    print("BASELINE: Full-year training, all 71 features")
    print("=" * 70)

    all_feats = get_all_features(train_full_eng)
    baseline_data = prepare_xy(train_full_eng, test_eng, all_feats)
    print(f"  Features: {len(baseline_data['feature_cols'])}, Train: {len(baseline_data['y_train'])}")

    r = run_standard_models(baseline_data, "Baseline (71f, full-yr)")
    all_results.update(r)
    for name, m in r.items():
        print(f"  {name}: AUC={m['AUC']:.3f}  Lift@10%={m['Lift@10%']:.2f}x")

    # ================================================================
    # EXPERIMENT 1: Seasonal training window
    # ================================================================
    print("\n" + "=" * 70)
    print("EXP 1: Seasonal training (Jan-Mar only), all features")
    print("=" * 70)
    
    all_feats_s = get_all_features(train_seasonal_eng)
    exp1_data = prepare_xy(train_seasonal_eng, test_eng, all_feats_s)
    print(f"  Features: {len(exp1_data['feature_cols'])}, Train: {len(exp1_data['y_train'])}")
    print(f"  Train OOR: {exp1_data['y_train'].sum()} ({exp1_data['y_train'].mean():.1%})")

    r = run_standard_models(exp1_data, "Exp1 Seasonal (71f)")
    all_results.update(r)
    for name, m in r.items():
        print(f"  {name}: AUC={m['AUC']:.3f}  Lift@10%={m['Lift@10%']:.2f}x")

    # ================================================================
    # EXPERIMENT 2: Feature selection (reduced to ~26)
    # ================================================================
    print("\n" + "=" * 70)
    print("EXP 2a: Reduced features (~26), full-year training")
    print("=" * 70)

    sel_feats = get_selected_features(train_full_eng)
    exp2a_data = prepare_xy(train_full_eng, test_eng, sel_feats)
    print(f"  Features: {len(exp2a_data['feature_cols'])}, Train: {len(exp2a_data['y_train'])}")

    r = run_standard_models(exp2a_data, "Exp2a Reduced (full-yr)")
    all_results.update(r)
    for name, m in r.items():
        print(f"  {name}: AUC={m['AUC']:.3f}  Lift@10%={m['Lift@10%']:.2f}x")

    # ================================================================
    # EXPERIMENT 1+2: Seasonal + reduced features (the SeasonalDO recipe)
    # ================================================================
    print("\n" + "=" * 70)
    print("EXP 1+2: Seasonal training + reduced features (SeasonalDO recipe)")
    print("=" * 70)

    sel_feats_s = get_selected_features(train_seasonal_eng)
    exp12_data = prepare_xy(train_seasonal_eng, test_eng, sel_feats_s)
    print(f"  Features: {len(exp12_data['feature_cols'])}, Train: {len(exp12_data['y_train'])}")

    r = run_standard_models(exp12_data, "Exp1+2 Seasonal+Reduced")
    all_results.update(r)
    for name, m in r.items():
        print(f"  {name}: AUC={m['AUC']:.3f}  Lift@10%={m['Lift@10%']:.2f}x")

    # ================================================================
    # EXPERIMENT 3: Rank product ensemble
    # ================================================================
    print("\n" + "=" * 70)
    print("EXP 3: Rank product (Weather-Only × Farm-Only)")
    print("=" * 70)

    # Full year
    r = run_experiment_3_rank_product(train_full, test, enrolled, weather)
    all_results.update(r)
    for name, m in r.items():
        print(f"  {name}: AUC={m['AUC']:.3f}  Lift@10%={m['Lift@10%']:.2f}x")

    # Also try with seasonal training
    print("\n  --- Seasonal variant ---")
    r_s = run_experiment_3_rank_product(train_seasonal, test, enrolled, weather)
    r_s_renamed = {k.replace("Rank Product", "Seasonal Rank Product"): v for k, v in r_s.items()}
    all_results.update(r_s_renamed)
    for name, m in r_s_renamed.items():
        print(f"  {name}: AUC={m['AUC']:.3f}  Lift@10%={m['Lift@10%']:.2f}x")

    # ================================================================
    # EXPERIMENT 4: XGBoost d=2 + early stopping
    # ================================================================
    print("\n" + "=" * 70)
    print("EXP 4: XGBoost max_depth=2 + early stopping")
    print("=" * 70)

    # With reduced features (best setup from above)
    print("  (a) Full-year, reduced features:")
    r4a, _ = run_experiment_4_xgb_tuned(exp2a_data, "Exp4a XGB-tuned (full-yr)")
    all_results.update(r4a)
    for name, m in r4a.items():
        bi = m.get("best_iter", m.get("n_estimators", ""))
        print(f"  {name}: AUC={m['AUC']:.3f}  Lift@10%={m['Lift@10%']:.2f}x  (iter={bi})")

    print("  (b) Seasonal, reduced features:")
    r4b, best_model = run_experiment_4_xgb_tuned(exp12_data, "Exp4b XGB-tuned (seasonal)")
    all_results.update(r4b)
    for name, m in r4b.items():
        bi = m.get("best_iter", m.get("n_estimators", ""))
        print(f"  {name}: AUC={m['AUC']:.3f}  Lift@10%={m['Lift@10%']:.2f}x  (iter={bi})")

    # ================================================================
    # SUMMARY
    # ================================================================
    print("\n\n" + "=" * 70)
    print("EXPERIMENT COMPARISON (sorted by AUC)")
    print("=" * 70)

    summary_df = pd.DataFrame(all_results).T
    summary_df = summary_df.sort_values("AUC", ascending=False)
    
    # Display key columns
    display_cols = ["AUC", "Lift@5%", "Lift@10%", "Lift@20%", "Prec@5%", "Prec@10%"]
    available_display = [c for c in display_cols if c in summary_df.columns]
    print(summary_df[available_display].to_string(float_format=lambda x: f"{x:.3f}"))
    
    summary_df.to_csv(BASE_DIR / "experiment_results.csv")
    print(f"\n  Saved experiment_results.csv")

    # ================================================================
    # PLOT
    # ================================================================
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    fig.suptitle("Experiment Comparison", fontsize=14, fontweight="bold")

    # AUC comparison
    ax = axes[0]
    top_n = min(20, len(summary_df))
    top = summary_df.head(top_n)
    colors = []
    for name in top.index:
        if "Baseline" in name: colors.append("#888888")
        elif "Exp1+2" in name: colors.append("#e74c3c")
        elif "Exp1 " in name: colors.append("#3498db")
        elif "Exp2" in name: colors.append("#2ecc71")
        elif "Rank" in name or "Seasonal Rank" in name: colors.append("#9b59b6")
        elif "Exp4" in name: colors.append("#e67e22")
        else: colors.append("#95a5a6")
    
    ax.barh(range(top_n), top["AUC"].values, color=colors)
    ax.set_yticks(range(top_n))
    ax.set_yticklabels([n.split("|")[-1].strip()[:30] for n in top.index], fontsize=7)
    ax.set_xlabel("AUC")
    ax.set_title("AUC (higher = better)")
    ax.axvline(x=0.5, color="gray", linestyle="--", alpha=0.3, label="Random")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3)

    # Lift@10% comparison
    ax = axes[1]
    ax.barh(range(top_n), top["Lift@10%"].values, color=colors)
    ax.set_yticks(range(top_n))
    ax.set_yticklabels([n.split("|")[-1].strip()[:30] for n in top.index], fontsize=7)
    ax.set_xlabel("Lift@10%")
    ax.set_title("Lift at Top 10% (higher = better)")
    ax.axvline(x=1.0, color="gray", linestyle="--", alpha=0.3, label="Random (1.0×)")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3)

    plt.tight_layout()
    plt.savefig(BASE_DIR / "experiment_comparison.png", dpi=150, bbox_inches="tight")
    print("  Saved experiment_comparison.png")
    plt.close()

    # Top 5 results
    print("\n" + "=" * 70)
    print("TOP 5 BEST MODELS")
    print("=" * 70)
    for i, (name, row) in enumerate(summary_df.head(5).iterrows()):
        print(f"\n  #{i+1}: {name}")
        print(f"      AUC={row['AUC']:.3f}  Lift@5%={row['Lift@5%']:.2f}x  Lift@10%={row['Lift@10%']:.2f}x  Lift@20%={row['Lift@20%']:.2f}x")

    print("\n" + "=" * 70)
    print("DONE ✓")
    print("=" * 70)


if __name__ == "__main__":
    main()
