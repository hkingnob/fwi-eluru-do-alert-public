#!/usr/bin/env python3
"""Combined Experiment #1 + #2 from Skye's Future Experiments.md.

#1: Train only on Jan-Mar of 2024 and 2025 (seasonal training window).
#2: Prune features to ~26 (Skye's recommended hand-picked subset).

Per Skye's recipe in Future_Experiments.md:
    "19 base weather features + pond_area + pond_depth +
     feed_type (one-hot, collapsed to top 3) +
     pond_historical_oor_rate + prev_do + days_since_last_visit"

Reuses Skye's pipeline (load, engineer_features, train/evaluate) and only
overrides (a) the data filter and (b) the feature list.

Reports v3 (full year, 59 feats) vs v4 (seasonal, 59 feats) vs v5 (seasonal, ~26 feats).
"""
import sys, json, re, warnings
warnings.filterwarnings("ignore")
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
import run_experiment_1 as rx1   # for load_data_seasonal()

BASE_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Curated feature set (Skye's recipe)
# ---------------------------------------------------------------------------
WEATHER_BASE_NAMES = [re.sub(r'[^A-Za-z0-9_]', '_', v) for v in fwm.WEATHER_DAILY_VARS]
# 19 names: temperature_2m_max/min/mean, apparent_temperature_*,
#           precipitation_sum, rain_sum, windspeed/winddirection/windgusts,
#           shortwave_radiation_sum, et0, relative_humidity_*, dewpoint, pressure, cloudcover

NON_WEATHER_FEATURES = [
    "pond_area",
    "pond_depth",
    # 3 top feed_type one-hots filled in below
    "pond_historical_oor_rate",
    "prev_do",
    "days_since_last_visit",
]


def pick_top_feed_type_columns(train_df, k=3):
    """Pick the k most-common feed_type_* one-hot columns by training count."""
    cols = [c for c in train_df.columns if c.startswith("feed_type_")]
    counts = {c: int(train_df[c].sum()) for c in cols}
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])
    chosen = [c for c, _ in ordered[:k]]
    return chosen, ordered


def get_lagged_weather_names():
    lag_vars = [
        "temperature_2m_mean", "windspeed_10m_max", "relative_humidity_2m_mean",
        "precipitation_sum", "shortwave_radiation_sum", "cloudcover_mean",
        "dewpoint_2m_mean", "pressure_msl_mean",
    ]
    out = []
    for v in lag_vars:
        out.append(f"{v}_7d_avg")
        out.append(f"{v}_3d_avg")
    return out


def prepare_data_curated(train_df, test_df, enrolled, weather, include_lagged_weather=False):
    """Like fwm.prepare_data but uses Skye's curated ~26-feature set."""
    print("\n" + "=" * 70)
    print("2. FEATURE ENGINEERING + PRUNING TO ~26 FEATURES")
    print("=" * 70)

    train_df = fwm.engineer_features(train_df, enrolled, weather, is_train=True)
    test_df  = fwm.engineer_features(test_df,  enrolled, weather, is_train=False)

    print(f"\n  Train target: {train_df['should_visit'].value_counts().to_dict()}")
    print(f"  Train OOR rate: {train_df['should_visit'].mean():.1%}")
    print(f"  Test target: {test_df['should_visit'].value_counts().to_dict()}")
    print(f"  Test OOR rate: {test_df['should_visit'].mean():.1%}")

    # Pick top-3 feed types from training distribution
    top_feed, all_feed_counts = pick_top_feed_type_columns(train_df, k=3)
    print(f"\n  Feed type one-hot counts in training:")
    for col, cnt in all_feed_counts:
        flag = "  <- top 3" if col in top_feed else ""
        print(f"    {col}: {cnt}{flag}")

    feature_cols = (
        WEATHER_BASE_NAMES
        + (get_lagged_weather_names() if include_lagged_weather else [])
        + NON_WEATHER_FEATURES[:2]      # pond_area, pond_depth
        + top_feed                      # 3 feed_type one-hots
        + NON_WEATHER_FEATURES[2:]      # pond_historical_oor_rate, prev_do, days_since_last_visit
    )

    # Make sure both sides have all columns
    for c in feature_cols:
        if c not in train_df.columns:
            train_df[c] = 0
        if c not in test_df.columns:
            test_df[c] = 0

    # Drop all-NaN
    all_nan = [c for c in feature_cols if train_df[c].isna().all()]
    if all_nan:
        print(f"  Dropping {len(all_nan)} all-NaN features: {all_nan}")
        feature_cols = [c for c in feature_cols if c not in all_nan]

    print(f"\n  Curated feature set ({len(feature_cols)} features): {feature_cols}")

    # Build matrices following the same logic as fwm.prepare_data
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    X_train = train_df[feature_cols].copy()
    X_test  = test_df[feature_cols].copy()
    y_cls_train = train_df["should_visit"].copy()
    y_cls_test  = test_df["should_visit"].copy()
    y_reg_train = train_df["do_mg_l"].copy()
    y_reg_test  = test_df["do_mg_l"].copy()

    binary_cols = [c for c in feature_cols if c.startswith("feed_type_")]
    for c in binary_cols:
        X_train[c] = X_train[c].fillna(0)
        X_test[c]  = X_test[c].fillna(0)

    print(f"\n  Train: {X_train.shape[0]} rows ({y_cls_train.sum()} OOR, {y_cls_train.mean():.1%})")
    print(f"  Test:  {X_test.shape[0]} rows ({y_cls_test.sum()} OOR, {y_cls_test.mean():.1%})")

    imputer = SimpleImputer(strategy="median")
    X_train_imp = pd.DataFrame(imputer.fit_transform(X_train), columns=feature_cols, index=X_train.index)
    X_test_imp  = pd.DataFrame(imputer.transform(X_test),       columns=feature_cols, index=X_test.index)

    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train_imp), columns=feature_cols, index=X_train.index)
    X_test_scaled  = pd.DataFrame(scaler.transform(X_test_imp),       columns=feature_cols, index=X_test.index)

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


def _run_variant(label, season_months, include_lagged):
    print("\n" + "█" * 70)
    print(f"█  RUN: {label}")
    print("█" * 70)

    train_df, test_df, enrolled, weather = rx1.load_data_seasonal(season_months=season_months)
    data = prepare_data_curated(train_df, test_df, enrolled, weather,
                                include_lagged_weather=include_lagged)

    cls_results, cls_scores, _ = fwm.train_and_evaluate_classification(data)
    reg_results, reg_preds, _  = fwm.train_and_evaluate_regression(data)

    cls_df = pd.DataFrame(cls_results).T
    reg_df = pd.DataFrame(reg_results).T

    cls_df.to_csv(BASE_DIR / f"classification_results__{label}.csv")
    reg_df.to_csv(BASE_DIR / f"regression_results__{label}.csv")

    return {
        "label": label,
        "n_train": int(data["X_train"].shape[0]),
        "n_test":  int(data["X_test"].shape[0]),
        "n_features": int(data["X_train"].shape[1]),
        "feature_cols": data["feature_cols"],
        "classification": cls_df.to_dict(orient="index"),
        "regression":     reg_df.to_dict(orient="index"),
    }


def run_v5_seasonal_pruned():
    return _run_variant("v5_seasonal_pruned", [1, 2, 3], include_lagged=False)


def run_v6_seasonal_pruned_with_lags():
    return _run_variant("v6_seasonal_pruned_with_lags", [1, 2, 3], include_lagged=True)


def main():
    print("╔" + "═" * 68 + "╗")
    print("║  Experiment #1+#2: Seasonal Training + Feature Pruning             ║")
    print("╚" + "═" * 68 + "╝")

    # Load prior results from experiment_1 run
    with open(RESULTS_DIR / "experiment_1_results.json") as f:
        prior = json.load(f)

    v5 = run_v5_seasonal_pruned()
    v6 = run_v6_seasonal_pruned_with_lags()
    print(f"\n  v5 features ({v5['n_features']}): {v5['feature_cols']}")
    print(f"\n  v6 features ({v6['n_features']}): {v6['feature_cols']}")

    print("\n" + "=" * 70)
    print("FOUR-WAY COMPARISON")
    print("  v3 = full year, 59 features (Skye's baseline)")
    print("  v4 = seasonal Jan-Mar, 59 features")
    print("  v5 = seasonal Jan-Mar, 27 features (Skye's pruning recipe)")
    print("  v6 = seasonal Jan-Mar, ~43 features (v5 + 16 lagged weather)")
    print("=" * 70)

    print(f"\n  v3 n_train=2236, 59 features")
    print(f"  v4 n_train=483,  59 features")
    print(f"  v5 n_train={v5['n_train']},  {v5['n_features']} features")
    print(f"  v6 n_train={v6['n_train']},  {v6['n_features']} features")

    # Classification comparison
    rows = []
    for model in sorted(prior["v3_full_year"]["classification"].keys()):
        v3 = prior["v3_full_year"]["classification"][model]
        v4 = prior["v4_seasonal"]["classification"][model]
        v5m = v5["classification"][model]
        v6m = v6["classification"][model]
        rows.append({
            "Model": model,
            "AUC v3": f"{v3['AUC']:.3f}",
            "AUC v4": f"{v4['AUC']:.3f}",
            "AUC v5": f"{v5m['AUC']:.3f}",
            "AUC v6": f"{v6m['AUC']:.3f}",
            "Best Δ v3": f"{max(v4['AUC'],v5m['AUC'],v6m['AUC']) - v3['AUC']:+.3f}",
            "Lift@10 v6": f"{v6m['Lift@10%']:.3f}",
            "Prec@10 v6": f"{v6m['Prec@10%']:.3f}",
        })
    cmp_df = pd.DataFrame(rows).sort_values("AUC v6", ascending=False)
    print("\n  Classification (sorted by v6 AUC):")
    print(cmp_df.to_string(index=False))

    # Regression comparison
    rrows = []
    for model in sorted(prior["v3_full_year"]["regression"].keys()):
        v3 = prior["v3_full_year"]["regression"][model]
        v4 = prior["v4_seasonal"]["regression"][model]
        v5m = v5["regression"][model]
        v6m = v6["regression"][model]
        rrows.append({
            "Model": model,
            "DerAUC v3": f"{v3['Derived AUC']:.3f}",
            "DerAUC v4": f"{v4['Derived AUC']:.3f}",
            "DerAUC v5": f"{v5m['Derived AUC']:.3f}",
            "DerAUC v6": f"{v6m['Derived AUC']:.3f}",
            "RMSE v6":   f"{v6m['RMSE']:.3f}",
            "R² v6":     f"{v6m['R²']:.3f}",
        })
    rcmp_df = pd.DataFrame(rrows).sort_values("DerAUC v6", ascending=False)
    print("\n  Regression (sorted by v6 Derived AUC):")
    print(rcmp_df.to_string(index=False))

    # Save outputs
    with open(RESULTS_DIR / "experiment_1_2_results.json", "w") as f:
        json.dump({
            "v3_full_year": prior["v3_full_year"],
            "v4_seasonal":  prior["v4_seasonal"],
            "v5_seasonal_pruned": v5,
            "v6_seasonal_pruned_with_lags": v6,
        }, f, indent=2, default=str)
    cmp_df.to_csv(RESULTS_DIR / "experiment_1_2_classification_comparison.csv", index=False)
    rcmp_df.to_csv(RESULTS_DIR / "experiment_1_2_regression_comparison.csv", index=False)
    print("\n  ✓ Saved experiment_1_2_results.json")
    print("  ✓ Saved experiment_1_2_classification_comparison.csv")
    print("  ✓ Saved experiment_1_2_regression_comparison.csv")


if __name__ == "__main__":
    main()
