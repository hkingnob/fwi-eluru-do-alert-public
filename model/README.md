# `model/`

Trained model artifacts and the scripts that produced them.

## Files

- **`model_for_webapp.json`** — the deployed model. Contains:
  - `feature_order`: the 37 weather features the model expects, in order.
  - `scaler_mean`, `scaler_std`: per-feature standardization parameters.
  - `ridge_coef`, `ridge_intercept`: the Ridge regression coefficients.
  - `imputer_median`: per-feature medians for missing-value imputation.
  - `thresholds_risk_score`: top-5%/10%/20% risk-score cutoffs derived from training data.
  - `openmeteo_var_map`: how Open-Meteo variable names map to model feature names.
  - `lag_var_names`: which 8 weather variables get 3-day and 7-day rolling averages.
  - `test_evaluation_q1_2026`: precomputed evaluation metrics on Q1 2026 hold-out.
  - `sanity_test_rows`: a few example test rows + their expected predictions (used to verify any port of the model logic).

- **`historical_oor_for_webapp.json`** — per-date FWI ground truth (visits, OOR count, OOR rate) for every date in 2024-01-01 → 2026-03-31. Used by the web app's Historical Lookup tab to compare model predictions against reality.

- **`export_model_for_webapp.py`** — re-trains the Ridge weather-only model from scratch using the 2024–2025 training data in `skye-original/public_ara_data/`, evaluates it on the Q1 2026 hold-out, and writes `model_for_webapp.json`.

- **`export_historical_oor.py`** — aggregates per-date OOR ground truth from the public FWI training data plus the Q1 2026 hold-out and writes `historical_oor_for_webapp.json`.

## Re-running

```bash
cd model
python3 export_model_for_webapp.py    # produces model_for_webapp.json
python3 export_historical_oor.py      # produces historical_oor_for_webapp.json
```

After regenerating, you'll need to re-embed both JSONs into `docs/index.html` if you want the web app to reflect the new values. (See the comments at the top of `docs/index.html` for the placeholder pattern.)

## Why Ridge regression on weather only?

Of the model variants tested in `analysis/`, this is the simplest one that performs as well as or better than more complex alternatives at the operational ranking task. See `analysis/reports/Experiments_3_and_4_Results.md` for the full comparison.

The model is intentionally lightweight: 37 features, a 3.5 KB JSON of parameters, runs in pure JavaScript in the browser. It deliberately uses no pond-specific features — only regional weather — because (a) Skye's experiments showed the per-pond signal in this dataset is weak, and (b) the operational use case is "is today a risky day for the region?" not "which specific pond is bad?"
