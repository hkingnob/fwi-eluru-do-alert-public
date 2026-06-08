#!/usr/bin/env python3
"""Experiment #1 from Future Experiments.md: seasonal training windows.

Runs Skye's v3 pipeline twice — once with full 2024-2025 training (baseline),
once filtered to Jan-Mar of 2024 and 2025 (seasonal). Test set is unchanged
in both cases (Jan-Mar 2026 from "2026 ARA WQ WG Morning Non-Follow-up.csv").

Outputs side-by-side metrics to compare. Does NOT touch features or models.
"""
import sys
import re
import json
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
from pathlib import Path

# Reuse all of Skye's pipeline functions
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

BASE_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Override load_data to optionally filter training to Jan-Mar months
# ---------------------------------------------------------------------------
def load_data_seasonal(season_months=None):
    """Like fwm.load_data() but optionally filters training to season_months.

    season_months=None  -> baseline (all months 2024-2025)
    season_months=[1,2,3] -> seasonal (Jan-Mar of 2024 and 2025 only)
    """
    print("=" * 70)
    print(f"1. LOADING DATA  (season_months={season_months})")
    print("=" * 70)

    hist = pd.read_csv(SKYE_DIR / "public_ara_data" / "water_quality.csv")
    hist["date"] = pd.to_datetime(hist["Date of data collection"], format="mixed")
    hist["year"] = hist["date"].dt.year

    test_2026 = pd.read_csv(SKYE_DIR / "2026 ARA WQ WG Morning Non-Follow-up.csv")
    test_2026["date"] = pd.to_datetime(test_2026["Date of data collection"], format="mixed")
    test_2026["year"] = test_2026["date"].dt.year
    test_2026["region"] = "Eluru"
    pond_key = pd.read_csv(SKYE_DIR / "2026 Github ARA Pond IDs Key.csv")
    pond_map = dict(zip(pond_key["internal_pond_id"], pond_key["public_pond_id"]))
    test_2026["pond_id"] = test_2026["Pond ID"].map(pond_map)
    print(f"  Test (2026 WG Morning Non-FU): {test_2026.shape[0]} rows")

    mask = (
        (hist["region"] == "Eluru") &
        (hist["Type"] == "Morning") &
        (hist["Is follow up"] == "No") &
        (hist["year"] >= 2024) &
        (hist["year"] <= 2025)
    )
    if season_months is not None:
        mask = mask & hist["date"].dt.month.isin(season_months)

    train_df = hist[mask].copy()
    print(f"  Train rows: {train_df.shape[0]}  (months in train: "
          f"{sorted(train_df['date'].dt.month.unique().tolist())})")
    print(f"  Train OOR rate: {(train_df['Is WQ in range?'] == 'No').mean():.1%}")
    print(f"  Test  OOR rate: {(test_2026['Is WQ in range?'] == 'No').mean():.1%}")

    enrolled = pd.read_csv(SKYE_DIR / "public_ara_data" / "enrolled_ponds_2026-02-02.csv")
    enrolled_eluru = enrolled[enrolled["region"] == "Eluru"].copy()

    weather = fwm.fetch_weather_data(start_date="2024-01-01")
    return train_df, test_2026, enrolled_eluru, weather


def run_one(label, season_months=None):
    print("\n" + "█" * 70)
    print(f"█  RUN: {label}")
    print("█" * 70)

    train_df, test_df, enrolled, weather = load_data_seasonal(season_months)
    data = fwm.prepare_data(train_df, test_df, enrolled, weather)
    cls_results, cls_scores, cls_models = fwm.train_and_evaluate_classification(data)
    reg_results, reg_preds, reg_models = fwm.train_and_evaluate_regression(data)

    cls_df = pd.DataFrame(cls_results).T
    reg_df = pd.DataFrame(reg_results).T

    out_dir = BASE_DIR
    cls_df.to_csv(out_dir / f"classification_results__{label}.csv")
    reg_df.to_csv(out_dir / f"regression_results__{label}.csv")
    print(f"\n  ✓ Saved classification_results__{label}.csv")
    print(f"  ✓ Saved regression_results__{label}.csv")

    return {
        "label": label,
        "n_train": len(train_df),
        "n_test": len(test_df),
        "train_oor_rate": float((train_df["Is WQ in range?"] == "No").mean()),
        "test_oor_rate":  float((test_df["Is WQ in range?"] == "No").mean()),
        "classification": cls_df.to_dict(orient="index"),
        "regression":     reg_df.to_dict(orient="index"),
    }


def main():
    print("╔" + "═" * 68 + "╗")
    print("║  Experiment #1: Seasonal Training Windows                          ║")
    print("║  Compare v3 (full-year train) vs v4 (Jan-Mar 2024-25 train only)   ║")
    print("╚" + "═" * 68 + "╝")

    results = {}
    results["v3_full_year"]  = run_one("v3_full_year",  season_months=None)
    results["v4_seasonal"]   = run_one("v4_seasonal",   season_months=[1, 2, 3])

    # Side-by-side comparison
    print("\n" + "=" * 70)
    print("SIDE-BY-SIDE COMPARISON")
    print("=" * 70)
    print(f"\n  v3 (full year): n_train={results['v3_full_year']['n_train']}, "
          f"OOR={results['v3_full_year']['train_oor_rate']:.1%}")
    print(f"  v4 (Jan-Mar):   n_train={results['v4_seasonal']['n_train']}, "
          f"OOR={results['v4_seasonal']['train_oor_rate']:.1%}")
    print(f"  Test  (Q1 2026): n_test={results['v3_full_year']['n_test']}, "
          f"OOR={results['v3_full_year']['test_oor_rate']:.1%}")

    print("\n  Classification (sorted by v4 AUC):")
    rows = []
    for model in sorted(results["v3_full_year"]["classification"].keys()):
        v3 = results["v3_full_year"]["classification"][model]
        v4 = results["v4_seasonal"]["classification"][model]
        rows.append({
            "Model": model,
            "AUC v3":     f"{v3['AUC']:.3f}",
            "AUC v4":     f"{v4['AUC']:.3f}",
            "ΔAUC":       f"{v4['AUC'] - v3['AUC']:+.3f}",
            "Prec@5 v3":  f"{v3['Prec@5%']:.3f}",
            "Prec@5 v4":  f"{v4['Prec@5%']:.3f}",
            "Prec@10 v3": f"{v3['Prec@10%']:.3f}",
            "Prec@10 v4": f"{v4['Prec@10%']:.3f}",
            "Lift@10 v3": f"{v3['Lift@10%']:.3f}",
            "Lift@10 v4": f"{v4['Lift@10%']:.3f}",
        })
    cmp_df = pd.DataFrame(rows).sort_values("AUC v4", ascending=False)
    print(cmp_df.to_string(index=False))

    print("\n  Regression (sorted by v4 Derived AUC):")
    rrows = []
    for model in sorted(results["v3_full_year"]["regression"].keys()):
        v3 = results["v3_full_year"]["regression"][model]
        v4 = results["v4_seasonal"]["regression"][model]
        rrows.append({
            "Model": model,
            "RMSE v3":   f"{v3['RMSE']:.3f}",
            "RMSE v4":   f"{v4['RMSE']:.3f}",
            "R² v3":     f"{v3['R²']:.3f}",
            "R² v4":     f"{v4['R²']:.3f}",
            "DerAUC v3": f"{v3['Derived AUC']:.3f}",
            "DerAUC v4": f"{v4['Derived AUC']:.3f}",
            "ΔDerAUC":   f"{v4['Derived AUC'] - v3['Derived AUC']:+.3f}",
        })
    rcmp_df = pd.DataFrame(rrows).sort_values("DerAUC v4", ascending=False)
    print(rcmp_df.to_string(index=False))

    # Save raw results bundle
    with open(RESULTS_DIR / "experiment_1_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    cmp_df.to_csv(RESULTS_DIR / "experiment_1_classification_comparison.csv", index=False)
    rcmp_df.to_csv(RESULTS_DIR / "experiment_1_regression_comparison.csv", index=False)
    print("\n  ✓ Saved experiment_1_results.json")
    print("  ✓ Saved experiment_1_classification_comparison.csv")
    print("  ✓ Saved experiment_1_regression_comparison.csv")


if __name__ == "__main__":
    main()
