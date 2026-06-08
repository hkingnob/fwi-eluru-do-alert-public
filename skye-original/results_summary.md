# Fish Welfare — DO Prediction Results (v3: Weather + Farm + Historical)

> [!IMPORTANT]
> **v3 adds 37 weather features from Open-Meteo** (19 daily variables + 16 lagged averages + 2 derived). No on-ground measurements used. Train 2024-2025, test 2026.

## What Changed (v2 → v3)

| Aspect | v2 (farm+historical only) | v3 (+ weather) |
|--------|--------------------------|----------------|
| **Weather** | None | 19 Open-Meteo daily vars + 3-day/7-day rolling averages |
| **Total features** | 34 | 71 |
| **Best Classification AUC** | 0.666 (Logistic Reg) | 0.671 (Logistic Reg) |
| **Best Regression Derived AUC** | 0.571 (Ridge) | **0.682 (Ridge)** ⬆ |
| **Regression R²** | -0.117 (all negative) | **+0.026 (first positive!)** ⬆ |

## Weather Data Source

- **API**: [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) (free, no API key)
- **Location**: Eluru center (16.64°N, 81.12°E) — all ponds within ~20 km
- **Variables**: temperature (max/min/mean + apparent), wind (speed/gusts/direction), humidity (max/min/mean), precipitation, solar radiation, evapotranspiration, dewpoint, pressure, cloud cover
- **Lagged features**: 3-day and 7-day rolling averages for 8 key variables
- **Cached locally**: `weather_cache_eluru.csv` (816 days)

## Binary Classification Results

| Model | AUC | F1 | Prec@5% | Lift@5% |
|-------|-----|-----|---------|---------|
| **Logistic Regression** | **0.671** | 0.259 | 0.133 | 1.4× |
| SVM (RBF) | 0.493 | 0.147 | 0.133 | 1.4× |
| XGBoost | 0.445 | 0.154 | 0.200 | 2.2× |
| Random Forest | 0.407 | 0.092 | 0.067 | 0.7× |
| LightGBM | 0.375 | 0.130 | 0.067 | 0.7× |

> [!WARNING]
> Tree-based models (RF, XGB, LGBM) got **worse** with weather features — they overfit with 71 features on 2,236 training rows. Logistic Regression, being heavily regularized (C=0.1), handles the dimensionality better and extracts real signal.

## Regression Results

| Model | RMSE (mg/L) | R² | Derived AUC |
|-------|-------------|-----|-------------|
| **Ridge Regression** | **0.576** | **+0.026** | **0.682** ⬆ |
| Linear Regression | 0.576 | +0.026 | 0.637 |
| XGBoost (Reg) | 0.609 | -0.087 | 0.646 |
| Random Forest (Reg) | 0.619 | -0.123 | 0.602 |
| LightGBM (Reg) | 0.621 | -0.130 | 0.596 |
| Poly Ridge (deg=2) | 0.799 | -0.871 | 0.573 |

> [!TIP]
> **Ridge Regression's Derived AUC of 0.682** is the best overall result — threshold the predicted DO at 3.0 mg/L to classify visits. This outperforms all direct classifiers and is approaching the SeasonalDO model's performance (AUC ~0.766).

## Key Findings

1. **Weather features improve regression substantially** — Ridge R² went from -0.117 to +0.026 (now positive, meaning it beats predicting the mean). Derived AUC jumped from 0.571 to 0.682.
2. **Weather features hurt tree-based classifiers** — 71 features with 2,236 rows gives trees too many knobs to overfit. The SeasonalDO model addressed this by using XGBoost with `max_depth=2` and a carefully tuned `best_iter`.
3. **Ridge Regression with thresholding is the best approach** — it combines the weather signal with strong L2 regularization, then converts to binary via a 3.0 mg/L threshold.
4. **Consistent with the Model Comparison doc** — the SeasonalDO model achieved AUC 0.766 using the same 19 weather features but with a seasonal training window (same calendar months only). Our model trains on ALL months 2024-2025, which dilutes seasonal patterns.

## Plots

![Classification comparison — ROC curves, precision-recall, and metrics](/Users/skyenygaard/.gemini/antigravity/brain/ef8532c9-c3d5-4a44-b003-22990ef2bf8f/classification_comparison.png)

![Regression comparison — actual vs predicted DO](/Users/skyenygaard/.gemini/antigravity/brain/ef8532c9-c3d5-4a44-b003-22990ef2bf8f/regression_comparison.png)

![Feature importance from XGBoost and LightGBM](/Users/skyenygaard/.gemini/antigravity/brain/ef8532c9-c3d5-4a44-b003-22990ef2bf8f/feature_importance.png)

## How to Run

```bash
uv run --with pandas --with openpyxl --with scikit-learn --with xgboost \
       --with lightgbm --with matplotlib --with seaborn --with requests \
       python3 fish_welfare_model.py
```

## Documentation
- [Data Leakage and Overfitting Prevention.md](file:///Users/skyenygaard/Programming/Fish-Welfare/Data%20Leakage%20and%20Overfitting%20Prevention.md) — Full anti-leakage documentation
- [fish_welfare_model.py](file:///Users/skyenygaard/Programming/Fish-Welfare/fish_welfare_model.py) — The pipeline script
- [weather_cache_eluru.csv](file:///Users/skyenygaard/Programming/Fish-Welfare/weather_cache_eluru.csv) — Cached Open-Meteo weather data
