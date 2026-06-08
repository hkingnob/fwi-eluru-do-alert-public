#!/usr/bin/env python3
"""Experiments #3 (rank-product ensemble) and #4 (XGB early stopping).

Both from Skye's Future_Experiments.md. Reuses his pipeline as a module.

#3 Rank Product Ensemble: train weather-only and farm-only models separately,
   convert each to test-set ranks, combine via product. Skye cited Sol's
   Model Comparison reaching AUC 0.709 with this architecture.

#4 XGBoost(max_depth=2, lr=0.03, early_stopping=50): the closest reasonable
   reproduction of Sol's SeasonalDO recipe (AUC 0.766) inside Skye's pipeline,
   without copying his actual code. Splits training into temporal train/val
   for early stopping.

Test set in both cases: 2026 ARA WQ WG Morning Non-Follow-up.csv (312 rows, 9.3% OOR).
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
import run_experiment_1 as rx1

from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score
import xgboost as xgb

BASE_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Feature partitioning for rank-product ensemble
# ---------------------------------------------------------------------------
def partition_features(all_features):
    """Split feature list into weather-only and farm/history/calendar."""
    weather_base = [re.sub(r'[^A-Za-z0-9_]', '_', v) for v in fwm.WEATHER_DAILY_VARS]
    weather_derived = ["temp_range", "humidity_range"]
    lag_vars = [
        "temperature_2m_mean", "windspeed_10m_max", "relative_humidity_2m_mean",
        "precipitation_sum", "shortwave_radiation_sum", "cloudcover_mean",
        "dewpoint_2m_mean", "pressure_msl_mean",
    ]
    weather_lags = []
    for v in lag_vars:
        weather_lags += [f"{v}_7d_avg", f"{v}_3d_avg"]
    weather_set = set(weather_base + weather_derived + weather_lags)
    weather_features = [f for f in all_features if f in weather_set]
    farm_features = [f for f in all_features if f not in weather_set]
    return weather_features, farm_features


def topk_metrics(y_true, score, k_pcts=(0.05, 0.10, 0.20)):
    """Compute Prec@K and Lift@K for a continuous score (higher = riskier)."""
    n = len(y_true)
    base = float(y_true.mean())
    out = {"AUC": float(roc_auc_score(y_true, score))}
    order = np.argsort(-np.asarray(score))
    yt = np.asarray(y_true)[order]
    for k in k_pcts:
        topk = max(1, int(n * k))
        prec = float(yt[:topk].mean())
        out[f"Prec@{int(k*100)}%"] = prec
        out[f"Lift@{int(k*100)}%"] = prec / base if base > 0 else 0.0
    return out


# ---------------------------------------------------------------------------
# EXPERIMENT 3: Rank-Product Ensemble
# ---------------------------------------------------------------------------
def run_experiment_3():
    print("\n" + "█" * 70)
    print("█  EXPERIMENT 3: RANK-PRODUCT ENSEMBLE (full year v3 setup)")
    print("█" * 70)

    train_df, test_df, enrolled, weather = rx1.load_data_seasonal(season_months=None)
    data = fwm.prepare_data(train_df, test_df, enrolled, weather)

    feature_cols = data["feature_cols"]
    weather_feats, farm_feats = partition_features(feature_cols)
    print(f"\n  Weather-only features ({len(weather_feats)}): {weather_feats[:5]}...")
    print(f"  Farm/history features  ({len(farm_feats)}): {farm_feats[:5]}...")

    Xtr_s = data["X_train_scaled"]
    Xte_s = data["X_test_scaled"]
    Xtr   = data["X_train"]
    Xte   = data["X_test"]
    y_tr  = data["y_train"]
    y_te  = data["y_test"]
    yreg_tr = data["y_reg_train"]
    yreg_te = data["y_reg_test"]

    results = {}

    # --- Logistic Regression rank-product ---
    print("\n  -- Logistic Regression --")
    lr_w = LogisticRegression(C=0.1, max_iter=2000, random_state=42, class_weight="balanced")
    lr_w.fit(Xtr_s[weather_feats], y_tr)
    p_w = lr_w.predict_proba(Xte_s[weather_feats])[:, 1]

    lr_f = LogisticRegression(C=0.1, max_iter=2000, random_state=42, class_weight="balanced")
    lr_f.fit(Xtr_s[farm_feats], y_tr)
    p_f = lr_f.predict_proba(Xte_s[farm_feats])[:, 1]

    # rank: 1 = highest risk; lower combined = higher risk; flip sign for "score"
    rank_w = pd.Series(p_w).rank(ascending=False).values
    rank_f = pd.Series(p_f).rank(ascending=False).values
    combined = -(rank_w * rank_f)  # higher score = riskier

    m_w = topk_metrics(y_te, p_w)
    m_f = topk_metrics(y_te, p_f)
    m_c = topk_metrics(y_te, combined)
    results["LR weather-only"]   = m_w
    results["LR farm-only"]      = m_f
    results["LR rank-product"]   = m_c
    print(f"    weather-only AUC={m_w['AUC']:.3f}  Lift@10={m_w['Lift@10%']:.2f}")
    print(f"    farm-only    AUC={m_f['AUC']:.3f}  Lift@10={m_f['Lift@10%']:.2f}")
    print(f"    rank-product AUC={m_c['AUC']:.3f}  Lift@10={m_c['Lift@10%']:.2f}")

    # --- Ridge regression rank-product (continuous DO → flip for risk) ---
    print("\n  -- Ridge Regression (DO predictor) --")
    rr_w = Ridge(alpha=10.0, random_state=42)
    rr_w.fit(Xtr_s[weather_feats], yreg_tr.fillna(yreg_tr.median()))
    pdo_w = rr_w.predict(Xte_s[weather_feats])

    rr_f = Ridge(alpha=10.0, random_state=42)
    rr_f.fit(Xtr_s[farm_feats], yreg_tr.fillna(yreg_tr.median()))
    pdo_f = rr_f.predict(Xte_s[farm_feats])

    # Lower predicted DO = higher OOR risk → invert the rank logic
    rank_w_r = pd.Series(pdo_w).rank(ascending=True).values   # 1 = lowest predicted DO
    rank_f_r = pd.Series(pdo_f).rank(ascending=True).values
    combined_r = -(rank_w_r * rank_f_r)

    score_w = -pdo_w  # so that higher = riskier
    score_f = -pdo_f
    m_w = topk_metrics(y_te, score_w)
    m_f = topk_metrics(y_te, score_f)
    m_c = topk_metrics(y_te, combined_r)
    results["Ridge weather-only"]   = m_w
    results["Ridge farm-only"]      = m_f
    results["Ridge rank-product"]   = m_c
    print(f"    weather-only DerAUC={m_w['AUC']:.3f}  Lift@10={m_w['Lift@10%']:.2f}")
    print(f"    farm-only    DerAUC={m_f['AUC']:.3f}  Lift@10={m_f['Lift@10%']:.2f}")
    print(f"    rank-product DerAUC={m_c['AUC']:.3f}  Lift@10={m_c['Lift@10%']:.2f}")

    rdf = pd.DataFrame(results).T
    rdf.to_csv(RESULTS_DIR / "experiment_3_rank_product_results.csv")
    print(f"\n  ✓ Saved experiment_3_rank_product_results.csv")
    return rdf


# ---------------------------------------------------------------------------
# EXPERIMENT 4: XGBoost(max_depth=2, early_stopping)
# ---------------------------------------------------------------------------
def _xgb_early_stop_run(label, season_months, val_year=2025):
    print(f"\n  -- {label} --")
    train_df, test_df, enrolled, weather = rx1.load_data_seasonal(season_months=season_months)
    data = fwm.prepare_data(train_df, test_df, enrolled, weather)

    feature_cols = data["feature_cols"]
    Xtr = data["X_train"]
    Xte = data["X_test"]
    y_tr = data["y_train"]
    y_te = data["y_test"]

    # Temporal val split: rows from val_year go to validation set
    train_yr = pd.to_datetime(train_df["date"]).dt.year.values
    train_dates_idx = pd.Series(train_yr, index=Xtr.index)
    is_val = train_dates_idx == val_year
    is_tr  = ~is_val
    n_tr  = int(is_tr.sum())
    n_val = int(is_val.sum())
    print(f"     temporal split for early-stopping: train={n_tr}, val={n_val} (val_year={val_year})")

    if n_val < 30 or is_val.sum() == 0 or is_tr.sum() == 0:
        print(f"     ⚠ Not enough rows in val_year; skipping")
        return None

    Xtr_fit = Xtr[is_tr]
    Xtr_val = Xtr[is_val]
    y_tr_fit = y_tr[is_tr]
    y_tr_val = y_tr[is_val]

    model = xgb.XGBClassifier(
        max_depth=2,
        n_estimators=1000,
        learning_rate=0.03,
        eval_metric="auc",
        early_stopping_rounds=50,
        tree_method="hist",
        random_state=42,
        verbosity=0,
    )
    model.fit(Xtr_fit, y_tr_fit, eval_set=[(Xtr_val, y_tr_val)], verbose=False)
    best_iter = getattr(model, "best_iteration", None)
    print(f"     best_iter = {best_iter}")

    p = model.predict_proba(Xte)[:, 1]
    metrics = topk_metrics(y_te, p)
    print(f"     AUC={metrics['AUC']:.3f}  Prec@5={metrics['Prec@5%']:.3f}  "
          f"Prec@10={metrics['Prec@10%']:.3f}  Lift@10={metrics['Lift@10%']:.2f}")
    metrics["best_iter"] = int(best_iter) if best_iter is not None else None
    metrics["n_train_fit"] = n_tr
    metrics["n_val"] = n_val
    metrics["n_features"] = len(feature_cols)
    return metrics


def run_experiment_4():
    print("\n" + "█" * 70)
    print("█  EXPERIMENT 4: XGBoost(max_depth=2, early_stopping=50)")
    print("█" * 70)

    results = {}
    # 4a: full-year training, val=2025
    r = _xgb_early_stop_run("4a: full year, val=2025", season_months=None, val_year=2025)
    if r: results["4a_full_year_val2025"] = r

    # 4b: full-year training, val=2024
    r = _xgb_early_stop_run("4b: full year, val=2024", season_months=None, val_year=2024)
    if r: results["4b_full_year_val2024"] = r

    # 4c: seasonal Jan-Mar, val=2025 (Sol-style)
    r = _xgb_early_stop_run("4c: seasonal Jan-Mar, val=2025", season_months=[1,2,3], val_year=2025)
    if r: results["4c_seasonal_val2025"] = r

    # 4d: seasonal Jan-Mar, val=2024
    r = _xgb_early_stop_run("4d: seasonal Jan-Mar, val=2024", season_months=[1,2,3], val_year=2024)
    if r: results["4d_seasonal_val2024"] = r

    rdf = pd.DataFrame(results).T
    rdf.to_csv(RESULTS_DIR / "experiment_4_xgb_earlystop_results.csv")
    print(f"\n  ✓ Saved experiment_4_xgb_earlystop_results.csv")
    return rdf


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print("╔" + "═" * 68 + "╗")
    print("║  Experiments #3 (rank-product) and #4 (XGB early stopping)         ║")
    print("╚" + "═" * 68 + "╝")

    e3 = run_experiment_3()
    e4 = run_experiment_4()

    print("\n" + "=" * 70)
    print("FINAL: best operational metric across ALL variants")
    print("=" * 70)

    # Best per family
    print("\n  Experiment #3 (rank-product):")
    print(e3.to_string())
    print("\n  Experiment #4 (XGB early stopping):")
    print(e4.to_string())

    # Reload prior results for comparison
    bundle = {"experiment_3": e3.to_dict(orient="index"),
              "experiment_4": e4.to_dict(orient="index")}
    with open(RESULTS_DIR / "experiments_3_4_results.json", "w") as f:
        json.dump(bundle, f, indent=2, default=str)
    print("\n  ✓ Saved experiments_3_4_results.json")


if __name__ == "__main__":
    main()
