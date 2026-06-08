# `analysis/`

Experiments, simulations, and write-ups behind the deployed model.

## Scripts (re-runnable)

| Script | What it does |
|---|---|
| **`run_deployment_simulation.py`** | Scores every YTD 2026 day with the model, then simulates 10 deployment policies (the user-proposed "HIGH × 1.5, others V−1", various capacity-neutral redistributions, alert-only, sanity checks). Outputs `results/ytd_daily_with_alerts.csv` and `results/ytd_policy_comparison.csv`. **This is the most operationally relevant script.** |
| `run_experiment_1.py` | Skye's Future Experiment #1: train on Jan–Mar of 2024 + 2025 only (seasonal window), test on Q1 2026. |
| `run_experiment_1_and_2.py` | #1 + #2 combined: seasonal training plus pruning to ~26 hand-selected features. Includes a v6 variant that adds back the lagged weather features. |
| `run_experiments_3_and_4.py` | #3 (rank-product ensemble: weather-only model × farm-only model) and #4 (XGBoost max_depth=2 with early stopping). |

All scripts assume `skye-original/` is one directory up. They import shared utilities from `skye-original/fish_welfare_model.py` and read training data from `skye-original/public_ara_data/`.

Outputs go to `analysis/results/`. The deployment simulation reads the raw YTD CSV from `data/2026_measurements_YTD.csv`.

## Reports (markdown writeups)

In `reports/`:

- **`Experiment_1_Seasonal_Training_Results.md`** — Did seasonal training help? (Short answer: no, not on its own.)
- **`Experiment_1_and_2_Results.md`** — Does feature pruning + seasonal training help? (Short answer: pruning actively hurt; the lagged-weather features are doing real work.)
- **`Experiments_3_and_4_Results.md`** — Rank-product ensemble and XGBoost early stopping. The most interesting findings are here, including the discovery that the model is essentially a "regional bad-day amplifier with a static pond-risk overlay."

## Results (CSV outputs)

In `results/`:

- `ytd_daily_with_alerts.csv` — every YTD 2026 day with model risk score, alert tier, observed visits, observed OOR.
- `ytd_policy_comparison.csv` — all 10 simulated deployment policies side-by-side: total visits, expected OOR catches, OOR rate, deltas vs baseline.
- `experiment_*_*_comparison.csv` — per-experiment classifier and regressor metrics across model variants.
- `experiment_*_results.json` — full numeric bundles for each experiment.

## Reproducibility

```bash
pip install pandas numpy scikit-learn xgboost lightgbm matplotlib seaborn openpyxl requests
cd analysis
python3 run_deployment_simulation.py
```

If you re-train the model (in `model/`), re-running these scripts will reflect the updated parameters.

## Key findings, two-line summary

The model's signal is real but modest: ~1.7× lift on Alert (Elevated+High combined) vs Normal days on YTD 2026 data. The earlier Q1-only validation looked stronger; with more data the realistic operational expectation is the YTD figure, not the Q1 figure.
