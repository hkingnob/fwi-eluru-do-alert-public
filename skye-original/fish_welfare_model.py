#!/usr/bin/env python3
"""Fish Welfare — DO Prediction Models (v3)

Predicts whether a farm visit will find out-of-range dissolved oxygen,
using ONLY features available BEFORE the visit:
  - Weather forecast (Open-Meteo: temp, wind, humidity, solar, precip)
  - Farm characteristics (from enrollment data: pond area, depth, feed type)
  - Historical patterns (past OOR rate, days since last visit)
  - Temporal/seasonal features (month one-hot, season)

NOT used (would be data leakage — measured AT the visit):
  - pH, water temperature, ammonia, water color
  - Behavioral signs (air gulping, tail splashing, dead fish)
  - Weather observed at visit (categorical ARA field — we use the forecast instead)
  - DO itself (that's the target!)

Train: 2024-2025 Eluru morning non-follow-up data (2,236 visits)
Test:  2026 Eluru morning non-follow-up data (from separate CSV)

Usage:
    uv run --with pandas --with openpyxl --with scikit-learn --with xgboost \\
           --with lightgbm --with matplotlib --with seaborn --with requests \\
           python3 fish_welfare_model.py
"""

import warnings
warnings.filterwarnings("ignore")

import re
import json
import time
import pandas as pd
import numpy as np
import requests
from pathlib import Path

# ML — Classification
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.metrics import (
    roc_auc_score, classification_report, confusion_matrix,
    precision_recall_curve, f1_score, roc_curve
)
from sklearn.impute import SimpleImputer

# ML — Regression
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

import xgboost as xgb
import lightgbm as lgb

# Visualization
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# Constants
BASE_DIR = Path(__file__).parent
DO_OOR_THRESHOLD = 3.0  # mg/L — FWI's out-of-range threshold

# Eluru (WG) representative coordinates (all ponds within ~20 km)
ELURU_LAT = 16.6423
ELURU_LON = 81.1161

# Open-Meteo daily weather variables to fetch
# These match the SeasonalDO model's weather feature set
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
# 0. WEATHER DATA FROM OPEN-METEO
# ============================================================================

def fetch_weather_data(start_date="2024-01-01", end_date=None):
    """Download daily weather from Open-Meteo Historical API.
    
    Weather is uniform across the Eluru area (all ponds within ~20 km),
    so we use a single representative coordinate point.
    
    Data is cached locally to avoid repeated API calls.
    """
    from datetime import date, timedelta
    if end_date is None:
        # Archive API goes up to yesterday
        end_date = (date.today() - timedelta(days=1)).isoformat()
    
    if WEATHER_CACHE_PATH.exists():
        print(f"  Loading cached weather from {WEATHER_CACHE_PATH.name}")
        weather = pd.read_csv(WEATHER_CACHE_PATH, parse_dates=["date"])
        # Check if cache covers our date range
        if weather["date"].min() <= pd.Timestamp(start_date) and \
           weather["date"].max() >= pd.Timestamp(end_date) - pd.Timedelta(days=7):
            return weather
        print("  Cache incomplete, re-downloading...")

    print(f"  Downloading weather from Open-Meteo ({start_date} to {end_date})...")
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": ELURU_LAT,
        "longitude": ELURU_LON,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(WEATHER_DAILY_VARS),
        "timezone": "Asia/Kolkata",
    }
    
    resp = requests.get(url, params=params, timeout=60)
    if not resp.ok:
        print(f"  API error: {resp.text}")
    resp.raise_for_status()
    data = resp.json()
    
    weather = pd.DataFrame(data["daily"])
    weather["date"] = pd.to_datetime(weather["time"])
    weather = weather.drop(columns=["time"])
    
    # Add 7-day and 3-day lagged features (rolling averages)
    # These capture multi-day weather accumulation effects on DO
    lag_vars = [
        "temperature_2m_mean", "windspeed_10m_max", "relative_humidity_2m_mean",
        "precipitation_sum", "shortwave_radiation_sum", "cloudcover_mean",
        "dewpoint_2m_mean", "pressure_msl_mean",
    ]
    for var in lag_vars:
        if var in weather.columns:
            weather[f"{var}_7d_avg"] = weather[var].rolling(7, min_periods=1).mean()
            weather[f"{var}_3d_avg"] = weather[var].rolling(3, min_periods=1).mean()
    
    # Temperature range (diurnal swing — affects DO)
    weather["temp_range"] = weather["temperature_2m_max"] - weather["temperature_2m_min"]
    weather["humidity_range"] = weather["relative_humidity_2m_max"] - weather["relative_humidity_2m_min"]
    
    # Cache locally
    weather.to_csv(WEATHER_CACHE_PATH, index=False)
    print(f"  Cached {len(weather)} days of weather to {WEATHER_CACHE_PATH.name}")
    
    return weather


# ============================================================================
# 1. DATA LOADING
# ============================================================================

def load_data():
    """Load historical + 2026 data + weather. Train on 2024-2025, test on 2026."""
    print("=" * 70)
    print("1. LOADING DATA")
    print("=" * 70)

    # Historical data (2021-2026, but we'll filter to 2024+, Eluru, morning, non-follow-up)
    hist = pd.read_csv(BASE_DIR / "public_ara_data" / "water_quality.csv")
    hist["date"] = pd.to_datetime(hist["Date of data collection"], format="mixed")
    hist["year"] = hist["date"].dt.year
    print(f"  Historical WQ: {hist.shape[0]} total rows")

    # 2026 data (separate, more recent)
    test_2026 = pd.read_csv(BASE_DIR / "2026 ARA WQ WG Morning Non-Follow-up.csv")
    test_2026["date"] = pd.to_datetime(test_2026["Date of data collection"], format="mixed")
    test_2026["year"] = test_2026["date"].dt.year
    test_2026["region"] = "Eluru"
    pond_key = pd.read_csv(BASE_DIR / "2026 Github ARA Pond IDs Key.csv")
    pond_map = dict(zip(pond_key["internal_pond_id"], pond_key["public_pond_id"]))
    test_2026["pond_id"] = test_2026["Pond ID"].map(pond_map)
    print(f"  2026 WQ (WG Morning Non-FU): {test_2026.shape[0]} rows")

    # Filter historical to: Eluru, Morning, non-follow-up, 2024-2025
    mask = (
        (hist["region"] == "Eluru") &
        (hist["Type"] == "Morning") &
        (hist["Is follow up"] == "No") &
        (hist["year"] >= 2024) &
        (hist["year"] <= 2025)
    )
    train_df = hist[mask].copy()
    print(f"  Train (2024-2025 Eluru Morning Non-FU): {train_df.shape[0]} rows")

    # Enrolled ponds (farm characteristics)
    enrolled = pd.read_csv(BASE_DIR / "public_ara_data" / "enrolled_ponds_2026-02-02.csv")
    enrolled_eluru = enrolled[enrolled["region"] == "Eluru"].copy()
    print(f"  Enrolled ponds (Eluru): {enrolled_eluru.shape[0]}")

    # Weather data from Open-Meteo (daily, for the Eluru area)
    weather = fetch_weather_data(start_date="2024-01-01")
    print(f"  Weather: {len(weather)} days, {len(weather.columns)} variables")

    return train_df, test_2026, enrolled_eluru, weather


# ============================================================================
# 2. FEATURE ENGINEERING — PRE-VISIT FEATURES ONLY
# ============================================================================

def engineer_features(df, enrolled, weather, is_train=True):
    """
    Create features from ONLY information available BEFORE the visit:
      - Weather forecast (Open-Meteo daily + 7-day lags)
      - Farm enrollment data: pond area, depth, feed type
      - Historical visit patterns: past OOR rate, last DO, days since visit
      - Calendar: month, season

    NOT available (measured at visit — would be leakage):
      - pH, temperature, ammonia, turbidity, TDS, alkalinity, hardness
      - Water color (observed at visit)
      - Weather observed at visit (the ARA categorical field)
      - Behavioral signs (air gulping, tail splashing, dead fish)
    """
    print(f"\n  Engineering features ({'train' if is_train else 'test'})...")

    df = df.copy()

    # -- Target --
    df["should_visit"] = (df["Is WQ in range?"] == "No").astype(int)
    df["do_mg_l"] = pd.to_numeric(df["DO (mg/L)"], errors="coerce")

    # -- Merge weather by date (available from forecast before visit) --
    df["date_only"] = df["date"].dt.normalize()  # Strip time for merge
    weather_copy = weather.copy()
    weather_copy["date_only"] = weather_copy["date"].dt.normalize()
    df = df.merge(weather_copy.drop(columns=["date"]), on="date_only", how="left")
    df = df.drop(columns=["date_only"])
    n_weather_matched = df["temperature_2m_mean"].notna().sum()
    print(f"    Weather matched: {n_weather_matched}/{len(df)} ({n_weather_matched/len(df):.0%})")

    # -- Temporal features (known before visit) --
    df["month"] = df["date"].dt.month
    df["day_of_week"] = df["date"].dt.dayofweek

    season_map = {1: "dry", 2: "dry", 3: "dry",
                  4: "pre_monsoon", 5: "pre_monsoon", 6: "pre_monsoon",
                  7: "monsoon", 8: "monsoon", 9: "monsoon",
                  10: "post_monsoon", 11: "post_monsoon", 12: "post_monsoon"}
    df["season"] = df["month"].map(season_map)

    month_dummies = pd.get_dummies(df["month"], prefix="month", dtype=int)
    season_dummies = pd.get_dummies(df["season"], prefix="season", dtype=int)
    df = pd.concat([df, month_dummies, season_dummies], axis=1)

    # -- Farm characteristics from enrollment (known before visit) --
    farm_cols = ["pond_id", "Pond area in acres", "Depth in meters", "Feed type"]
    available_farm = [c for c in farm_cols if c in enrolled.columns]
    farm_data = enrolled[available_farm].drop_duplicates(subset=["pond_id"])
    df = df.merge(farm_data, on="pond_id", how="left")

    df["pond_area"] = pd.to_numeric(df.get("Pond area in acres", pd.Series(dtype=float)), errors="coerce")
    df["pond_depth"] = pd.to_numeric(df.get("Depth in meters", pd.Series(dtype=float)), errors="coerce")

    if "Feed type" in df.columns:
        df["Feed type"] = df["Feed type"].fillna("Unknown")
        feed_dummies = pd.get_dummies(df["Feed type"], prefix="feed_type", dtype=int)
        df = pd.concat([df, feed_dummies], axis=1)

    # -- Historical features (from PREVIOUS visits only — no leakage) --
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
        if len(pond_history[pid]) > 0:
            oor_rates.append(np.mean(pond_history[pid]))
        else:
            oor_rates.append(np.nan)
        pond_history[pid].append(row["should_visit"])
    df["pond_historical_oor_rate"] = oor_rates

    df["prev_do"] = df.groupby("pond_id")["do_mg_l"].shift(1)
    df["days_since_last_visit"] = df.groupby("pond_id")["date"].diff().dt.days
    df["n_previous_visits"] = df.groupby("pond_id").cumcount()

    total_fish = df["prev_stocking_density"] * df["pond_area"]
    df["prev_feed_per_fish"] = np.where(total_fish > 0, df["prev_feed_amount"] / total_fish, np.nan)

    # -- Sanitize column names for LightGBM/XGBoost --
    df.columns = [re.sub(r'[^A-Za-z0-9_]', '_', c) for c in df.columns]

    return df


def get_feature_columns(df):
    """Return only pre-visit feature columns (no leakage)."""
    month_cols = [c for c in df.columns if c.startswith("month_")]
    season_cols = [c for c in df.columns if c.startswith("season_")]
    feed_type_cols = [c for c in df.columns if c.startswith("feed_type_")]

    # Weather features (from Open-Meteo forecast — available before visit)
    weather_base = [re.sub(r'[^A-Za-z0-9_]', '_', v) for v in WEATHER_DAILY_VARS]
    weather_derived = ["temp_range", "humidity_range"]
    weather_lags = []
    lag_vars = [
        "temperature_2m_mean", "windspeed_10m_max", "relative_humidity_2m_mean",
        "precipitation_sum", "shortwave_radiation_sum", "cloudcover_mean",
        "dewpoint_2m_mean", "pressure_msl_mean",
    ]
    for var in lag_vars:
        weather_lags.append(f"{var}_7d_avg")
        weather_lags.append(f"{var}_3d_avg")

    feature_cols = [
        # Weather forecast (Open-Meteo — available before visit)
        *weather_base,
        *weather_derived,
        *weather_lags,
        # Farm characteristics (from enrollment — known before visit)
        "pond_area", "pond_depth",
        *feed_type_cols,
        # Historical (from PREVIOUS visits — no leakage)
        "prev_feed_amount", "prev_stocking_density",
        "prev_feed_per_fish",
        "prev_do",
        "pond_historical_oor_rate",
        "days_since_last_visit",
        "n_previous_visits",
        # Temporal (known before visit)
        *month_cols,
        *season_cols,
        "day_of_week",
    ]

    # Only keep columns that exist
    feature_cols = [c for c in feature_cols if c in df.columns]
    return feature_cols


# ============================================================================
# 3. PREPARE FEATURES & SPLIT
# ============================================================================

def prepare_data(train_df, test_df, enrolled, weather):
    """Engineer features and prepare train/test matrices."""
    print("\n" + "=" * 70)
    print("2. FEATURE ENGINEERING (weather + farm + historical)")
    print("=" * 70)

    # Engineer features
    train_df = engineer_features(train_df, enrolled, weather, is_train=True)
    test_df = engineer_features(test_df, enrolled, weather, is_train=False)

    print(f"\n  Train target: {train_df['should_visit'].value_counts().to_dict()}")
    print(f"  Train OOR rate: {train_df['should_visit'].mean():.1%}")
    print(f"  Test target: {test_df['should_visit'].value_counts().to_dict()}")
    print(f"  Test OOR rate: {test_df['should_visit'].mean():.1%}")

    # Get feature columns
    feature_cols = get_feature_columns(train_df)

    # Ensure test has the same columns (fill missing with 0 for one-hot)
    for c in feature_cols:
        if c not in test_df.columns:
            test_df[c] = 0

    # Filter to only columns present in both
    feature_cols = [c for c in feature_cols if c in train_df.columns and c in test_df.columns]

    print(f"\n" + "=" * 70)
    print(f"3. DATA PREPARATION")
    print("=" * 70)
    print(f"  Using {len(feature_cols)} pre-visit features: {feature_cols}")

    X_train = train_df[feature_cols].copy()
    X_test = test_df[feature_cols].copy()
    y_cls_train = train_df["should_visit"].copy()
    y_cls_test = test_df["should_visit"].copy()
    y_reg_train = train_df["do_mg_l"].copy()
    y_reg_test = test_df["do_mg_l"].copy()

    # Fill one-hot columns with 0
    binary_cols = [c for c in feature_cols
                   if c.startswith(("month_", "season_", "feed_type_"))]
    for c in binary_cols:
        X_train[c] = X_train[c].fillna(0)
        X_test[c] = X_test[c].fillna(0)

    # Drop all-NaN features in training
    all_nan = [c for c in feature_cols if X_train[c].isna().all()]
    if all_nan:
        print(f"  Dropping {len(all_nan)} all-NaN features: {all_nan}")
        feature_cols = [c for c in feature_cols if c not in all_nan]
        X_train = X_train[feature_cols]
        X_test = X_test[feature_cols]

    print(f"  Train: {X_train.shape[0]} rows ({y_cls_train.sum()} OOR, {y_cls_train.mean():.1%})")
    print(f"  Test:  {X_test.shape[0]} rows ({y_cls_test.sum()} OOR, {y_cls_test.mean():.1%})")

    # Impute continuous features with median
    imputer = SimpleImputer(strategy="median")
    X_train_imp = pd.DataFrame(
        imputer.fit_transform(X_train), columns=feature_cols, index=X_train.index)
    X_test_imp = pd.DataFrame(
        imputer.transform(X_test), columns=feature_cols, index=X_test.index)

    # Scale for linear models
    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(
        scaler.fit_transform(X_train_imp), columns=feature_cols, index=X_train.index)
    X_test_scaled = pd.DataFrame(
        scaler.transform(X_test_imp), columns=feature_cols, index=X_test.index)

    return {
        "X_train": X_train_imp,
        "X_test": X_test_imp,
        "X_train_scaled": X_train_scaled,
        "X_test_scaled": X_test_scaled,
        "y_train": y_cls_train,
        "y_test": y_cls_test,
        "y_reg_train": y_reg_train,
        "y_reg_test": y_reg_test,
        "feature_cols": feature_cols,
    }


# ============================================================================
# 4. CLASSIFICATION MODEL TRAINING & EVALUATION
# ============================================================================

def train_and_evaluate_classification(data):
    """Train classifiers and compute test statistics."""
    print("\n" + "=" * 70)
    print("4a. BINARY CLASSIFICATION — Should we visit?")
    print("=" * 70)

    X_train = data["X_train"]
    X_test = data["X_test"]
    X_train_s = data["X_train_scaled"]
    X_test_s = data["X_test_scaled"]
    y_train = data["y_train"]
    y_test = data["y_test"]

    n_pos = y_train.sum()
    n_neg = len(y_train) - n_pos
    scale_pos = n_neg / max(n_pos, 1)

    models = {
        "Logistic Regression": {
            "model": LogisticRegression(
                class_weight="balanced", max_iter=1000, C=0.1, random_state=42
            ),
            "scaled": True,
        },
        "Random Forest": {
            "model": RandomForestClassifier(
                n_estimators=200, max_depth=4, min_samples_leaf=10,
                class_weight="balanced", random_state=42, n_jobs=-1
            ),
            "scaled": False,
        },
        "XGBoost": {
            "model": xgb.XGBClassifier(
                n_estimators=200, max_depth=3, learning_rate=0.05,
                min_child_weight=10, subsample=0.8, colsample_bytree=0.8,
                scale_pos_weight=scale_pos, eval_metric="logloss",
                reg_alpha=1.0, reg_lambda=5.0,
                random_state=42, use_label_encoder=False
            ),
            "scaled": False,
        },
        "LightGBM": {
            "model": lgb.LGBMClassifier(
                n_estimators=200, max_depth=3, learning_rate=0.05,
                min_child_samples=10, subsample=0.8, colsample_bytree=0.8,
                scale_pos_weight=scale_pos,
                reg_alpha=1.0, reg_lambda=5.0,
                random_state=42, verbose=-1
            ),
            "scaled": False,
        },
        "SVM (RBF)": {
            "model": SVC(
                kernel="rbf", C=0.5, class_weight="balanced",
                probability=True, random_state=42
            ),
            "scaled": True,
        },
    }

    results = {}
    all_y_scores = {}

    for name, config in models.items():
        print(f"\n  --- {name} ---")
        model = config["model"]
        Xtr = X_train_s if config["scaled"] else X_train
        Xte = X_test_s if config["scaled"] else X_test

        model.fit(Xtr, y_train)
        y_pred = model.predict(Xte)
        y_proba = model.predict_proba(Xte)[:, 1]

        try:
            auc = roc_auc_score(y_test, y_proba)
        except ValueError:
            auc = float("nan")

        f1 = f1_score(y_test, y_pred, zero_division=0)

        n_test = len(y_test)
        sorted_idx = np.argsort(-y_proba)
        y_sorted = y_test.values[sorted_idx]
        k5 = max(1, int(0.05 * n_test))
        k10 = max(1, int(0.10 * n_test))
        k20 = max(1, int(0.20 * n_test))
        prec_at_5 = y_sorted[:k5].mean()
        prec_at_10 = y_sorted[:k10].mean()
        prec_at_20 = y_sorted[:k20].mean()
        base_rate = y_test.mean()
        lift_5 = prec_at_5 / base_rate if base_rate > 0 else float("nan")
        lift_10 = prec_at_10 / base_rate if base_rate > 0 else float("nan")
        lift_20 = prec_at_20 / base_rate if base_rate > 0 else float("nan")

        results[name] = {
            "AUC": auc, "F1": f1,
            "Prec@5%": prec_at_5, "Prec@10%": prec_at_10, "Prec@20%": prec_at_20,
            "Lift@5%": lift_5, "Lift@10%": lift_10, "Lift@20%": lift_20,
        }
        all_y_scores[name] = y_proba

        print(f"    AUC:       {auc:.3f}")
        print(f"    F1:        {f1:.3f}")
        print(f"    Prec@5%:   {prec_at_5:.3f}  (Lift: {lift_5:.1f}x)")
        print(f"    Prec@10%:  {prec_at_10:.3f}  (Lift: {lift_10:.1f}x)")
        print(f"    Prec@20%:  {prec_at_20:.3f}  (Lift: {lift_20:.1f}x)")
        print(f"\n  Classification Report:")
        print(classification_report(y_test, y_pred,
              target_names=["No Visit", "Visit"], zero_division=0))
        cm = confusion_matrix(y_test, y_pred)
        print(f"  Confusion: TN={cm[0,0]} FP={cm[0,1]} FN={cm[1,0]} TP={cm[1,1]}")

    return results, all_y_scores, models


# ============================================================================
# 4b. REGRESSION MODEL TRAINING & EVALUATION
# ============================================================================

def train_and_evaluate_regression(data):
    """Train regression models to predict continuous DO (mg/L)."""
    print("\n" + "=" * 70)
    print("4b. REGRESSION — Predict DO (mg/L)")
    print("=" * 70)

    X_train = data["X_train"]
    X_test = data["X_test"]
    X_train_s = data["X_train_scaled"]
    X_test_s = data["X_test_scaled"]
    y_train = data["y_reg_train"]
    y_test = data["y_reg_test"]
    y_cls_test = data["y_test"]

    models = {
        "Linear Regression": {"model": LinearRegression(), "scaled": True},
        "Ridge Regression": {"model": Ridge(alpha=10.0), "scaled": True},
        "Poly Ridge (deg=2)": {
            "model": Pipeline([
                ("poly", PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)),
                ("ridge", Ridge(alpha=100.0)),  # Strong regularization for poly
            ]),
            "scaled": True,
        },
        "Random Forest (Reg)": {
            "model": RandomForestRegressor(
                n_estimators=200, max_depth=4, min_samples_leaf=10,
                random_state=42, n_jobs=-1
            ),
            "scaled": False,
        },
        "XGBoost (Reg)": {
            "model": xgb.XGBRegressor(
                n_estimators=200, max_depth=3, learning_rate=0.05,
                min_child_weight=10, subsample=0.8, colsample_bytree=0.8,
                reg_alpha=1.0, reg_lambda=5.0, random_state=42
            ),
            "scaled": False,
        },
        "LightGBM (Reg)": {
            "model": lgb.LGBMRegressor(
                n_estimators=200, max_depth=3, learning_rate=0.05,
                min_child_samples=10, subsample=0.8, colsample_bytree=0.8,
                reg_alpha=1.0, reg_lambda=5.0, random_state=42, verbose=-1
            ),
            "scaled": False,
        },
    }

    results = {}
    all_y_preds = {}

    for name, config in models.items():
        print(f"\n  --- {name} ---")
        model = config["model"]
        Xtr = X_train_s if config["scaled"] else X_train
        Xte = X_test_s if config["scaled"] else X_test

        model.fit(Xtr, y_train)
        y_pred = model.predict(Xte)

        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        y_risk_score = -y_pred
        try:
            derived_auc = roc_auc_score(y_cls_test, y_risk_score)
        except ValueError:
            derived_auc = float("nan")

        y_pred_binary = (y_pred < DO_OOR_THRESHOLD).astype(int)
        derived_f1 = f1_score(y_cls_test, y_pred_binary, zero_division=0)

        results[name] = {
            "RMSE": rmse, "MAE": mae, "R²": r2,
            "Derived AUC": derived_auc, "Derived F1": derived_f1,
        }
        all_y_preds[name] = y_pred

        print(f"    RMSE:          {rmse:.3f} mg/L")
        print(f"    MAE:           {mae:.3f} mg/L")
        print(f"    R²:            {r2:.3f}")
        print(f"    Derived AUC:   {derived_auc:.3f}")
        print(f"    Derived F1:    {derived_f1:.3f}")

    return results, all_y_preds, models


# ============================================================================
# 5. VISUALIZATION
# ============================================================================

def summarize_and_plot(cls_results, cls_scores, reg_results, reg_preds,
                       y_cls_test, y_reg_test, all_models, data):
    """Create summary tables and plots."""
    print("\n" + "=" * 70)
    print("5. RESULTS COMPARISON")
    print("=" * 70)

    # Classification summary
    print("\n  ── Binary Classification (weather + farm + historical) ──")
    cls_df = pd.DataFrame(cls_results).T.sort_values("AUC", ascending=False)
    print(cls_df.to_string())
    cls_df.to_csv(BASE_DIR / "classification_results.csv")

    # Regression summary
    print("\n  ── Continuous Regression ──")
    reg_df = pd.DataFrame(reg_results).T.sort_values("RMSE", ascending=True)
    print(reg_df.to_string())
    reg_df.to_csv(BASE_DIR / "regression_results.csv")

    print(f"\n  Saved classification_results.csv and regression_results.csv")

    # Plot 1: Classification
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle("Binary Classification: Should We Visit?\n(Train: 2024-2025, Test: 2026, pre-visit features only)",
                 fontsize=12, fontweight="bold")

    ax = axes[0]
    for name, y_proba in cls_scores.items():
        fpr, tpr, _ = roc_curve(y_cls_test, y_proba)
        auc = cls_results[name]["AUC"]
        ax.plot(fpr, tpr, label=f"{name} ({auc:.3f})", linewidth=2)
    ax.plot([0, 1], [0, 1], "k--", alpha=0.3)
    ax.set_xlabel("FPR"); ax.set_ylabel("TPR"); ax.set_title("ROC Curves")
    ax.legend(fontsize=7); ax.grid(alpha=0.3)

    ax = axes[1]
    for name, y_proba in cls_scores.items():
        prec, rec, _ = precision_recall_curve(y_cls_test, y_proba)
        ax.plot(rec, prec, label=name, linewidth=2)
    ax.axhline(y=y_cls_test.mean(), color="k", linestyle="--", alpha=0.3,
               label=f"Baseline ({y_cls_test.mean():.2f})")
    ax.set_xlabel("Recall"); ax.set_ylabel("Precision"); ax.set_title("Precision-Recall")
    ax.legend(fontsize=7); ax.grid(alpha=0.3)

    ax = axes[2]
    metrics = ["AUC", "F1", "Prec@10%"]
    x = np.arange(len(metrics)); width = 0.15
    for i, (name, res) in enumerate(cls_results.items()):
        ax.bar(x + i * width, [res[m] for m in metrics], width, label=name)
    ax.set_xticks(x + width * 2); ax.set_xticklabels(metrics)
    ax.set_title("Metric Comparison"); ax.legend(fontsize=6); ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(BASE_DIR / "classification_comparison.png", dpi=150, bbox_inches="tight")
    print("  Saved classification_comparison.png")

    # Plot 2: Regression
    n_models = len(reg_preds)
    fig, axes = plt.subplots(1, n_models, figsize=(4 * n_models, 4))
    fig.suptitle("Regression: Predict DO (mg/L)\n(Train: 2024-2025, Test: 2026)",
                 fontsize=12, fontweight="bold")
    if n_models == 1:
        axes = [axes]
    for i, (name, y_pred) in enumerate(reg_preds.items()):
        ax = axes[i]
        ax.scatter(y_reg_test, y_pred, alpha=0.3, s=10, color="steelblue")
        lims = [min(y_reg_test.min(), min(y_pred)) - 0.5,
                max(y_reg_test.max(), max(y_pred)) + 0.5]
        ax.plot(lims, lims, "k--", alpha=0.3)
        ax.set_xlabel("Actual DO"); ax.set_ylabel("Predicted DO")
        r2 = reg_results[name]["R²"]
        ax.set_title(f"{name}\nR²={r2:.3f}", fontsize=8)
        ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(BASE_DIR / "regression_comparison.png", dpi=150, bbox_inches="tight")
    print("  Saved regression_comparison.png")

    # Plot 3: Feature importance
    feature_cols = data["feature_cols"]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Feature Importance (pre-visit features only)", fontsize=12, fontweight="bold")

    for ax, (model_key, title, color) in zip(axes.flat, [
        ("XGBoost", "XGBoost Classifier", "steelblue"),
        ("LightGBM", "LightGBM Classifier", "coral"),
    ]):
        if model_key in all_models:
            model = all_models[model_key]["model"]
            imp = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=True)
            imp.tail(15).plot(kind="barh", ax=ax, color=color)
            ax.set_title(f"{title} (top 15)")
            ax.set_xlabel("Importance")
    plt.tight_layout()
    plt.savefig(BASE_DIR / "feature_importance.png", dpi=150, bbox_inches="tight")
    print("  Saved feature_importance.png")
    plt.close("all")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║  Fish Welfare — DO Prediction (v3: weather + farm + historical)    ║")
    print("║  Train: 2024-2025  |  Test: 2026  |  No on-ground measurements     ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    train_df, test_df, enrolled, weather = load_data()
    data = prepare_data(train_df, test_df, enrolled, weather)

    cls_results, cls_scores, cls_models = train_and_evaluate_classification(data)
    reg_results, reg_preds, reg_models = train_and_evaluate_regression(data)

    all_models = {**cls_models, **reg_models}
    summarize_and_plot(
        cls_results, cls_scores,
        reg_results, reg_preds,
        data["y_test"], data["y_reg_test"],
        all_models, data
    )

    print("\n" + "=" * 70)
    print("DONE ✓")
    print("=" * 70)


if __name__ == "__main__":
    main()
