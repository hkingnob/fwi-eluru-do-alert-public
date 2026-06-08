# Future Experiments

Possible directions to improve DO prediction performance, ordered from highest expected impact to lowest.

---

## 1. Seasonal Training Windows (HIGH IMPACT — proven by SeasonalDO)

**What**: Instead of training on all 2024-2025 data, train only on Jan-Mar of 2024 and 2025 to predict Jan-Mar 2026.

**Why**: The SeasonalDO model (AUC 0.766, 4.6× lift) proved this works. Weather-DO relationships are seasonal — low wind is a dry-season risk factor (reduces surface oxygen transfer), while heavy rain is a monsoon risk factor. Training on monsoon data dilutes dry-season patterns.

**How**:
```python
# Current (full-year training)
train = data[(data.year >= 2024) & (data.year <= 2025)]

# Proposed (seasonal window)
train = data[(data.year >= 2024) & (data.year <= 2025) & (data.month.isin([1, 2, 3]))]
```

**Expected outcome**: AUC should jump from ~0.68 to ~0.76+ based on SeasonalDO parity. Training set shrinks from 2,236 to ~400 rows, but the signal-to-noise ratio improves dramatically.

**Risk**: Smaller training set may not support 71 features. Will need aggressive feature selection (see Experiment 3).

---

## 2. Feature Selection: Reduce to Top ~26 Features (HIGH IMPACT)

**What**: Drop low-importance features to reduce overfitting, especially for tree-based models. Target 19 weather + 7 farm features (the SeasonalDO recipe).

**Why**: Our tree-based models (XGBoost, LightGBM, RF) degraded from AUC ~0.58 to ~0.37-0.45 when we added weather features — classic overfitting from too many features (71) on too few rows (2,236). The SeasonalDO model used only 26 features with XGBoost and achieved AUC 0.766.

**How**:
- Use permutation importance or SHAP values on the training set (NOT test set) to identify the top 26 features
- Or manually select: 19 base weather features + pond_area + pond_depth + feed_type (one-hot, collapsed to top 3) + pond_historical_oor_rate + prev_do + days_since_last_visit
- Remove lagged weather averages if they add noise

**Expected outcome**: Tree-based models should recover to AUC 0.55-0.70. Combined with seasonal training, could reach 0.75+.

---

## 3. Rank Product Ensemble (MEDIUM IMPACT — proven in Model Comparison)

**What**: Instead of one model, combine two complementary models via rank product:
- **Weather-Only model** (ranks days — "is tomorrow a bad DO day?")
- **Farm Management model** (ranks ponds — "which ponds are inherently riskier?")

**Why**: The Model Comparison's best overall model (AUC 0.709) used exactly this approach. Weather and farm features capture orthogonal risk dimensions:
- Weather predicts *temporal* risk (hot/still/cloudy → low DO for ALL ponds)
- Farm predicts *spatial* risk (overcrowded/shallow/wrong feed → low DO for SPECIFIC ponds)

**How**:
```python
# Train two separate models
weather_model.predict(X_weather)  → rank_weather (1 = highest risk day)
farm_model.predict(X_farm)        → rank_farm (1 = highest risk pond)

# Combine
combined_score = rank_weather * rank_farm  # rank product
# Sort by combined_score (ascending = highest risk)
```

**Expected outcome**: AUC 0.70+ (matching the Model Comparison benchmark).

---

## 4. XGBoost with Low max_depth and Early Stopping (MEDIUM IMPACT)

**What**: Use XGBoost with `max_depth=2` and `early_stopping_rounds` on a validation fold, as the SeasonalDO model did.

**Why**: The SeasonalDO model used `max_depth=2` with `best_iter=566`, meaning it found the optimal number of boosting rounds via early stopping. Our model uses `max_depth=3` with a fixed 200 estimators — too deep and possibly not enough rounds.

**How**:
```python
model = xgb.XGBClassifier(
    max_depth=2,  # shallower than current 3
    n_estimators=1000,  # allow more rounds
    early_stopping_rounds=50,
    eval_metric="auc",
    learning_rate=0.03,
)
model.fit(X_train, y_train, eval_set=[(X_val, y_val)])
```

**Risk**: Requires a validation split from the training data, reducing effective training size. Could use time-based split (2024 for validation, 2025 for training, or vice versa).

---

## 5. Continuous Monitor Calibration (MEDIUM IMPACT — unique data source)

**What**: Use the Data Campaign continuous monitor data (`Data-Campaign-Data/`) to understand the diurnal DO cycle and build a physics-informed feature.

**Why**: DO follows a predictable daily pattern: lowest at dawn (~6am), highest in afternoon. The monitoring data has continuous readings from paired ProDSS and IoT sensors, along with comparison data. This could yield:
- A "predicted dawn DO minimum" feature based on weather conditions
- Calibration of weather-DO relationships at finer temporal resolution

**How**:
1. Analyze the continuous monitor CSVs to extract diurnal DO curves
2. Model the dawn DO minimum as a function of weather (temp, wind, cloud cover)
3. Use this as a physics-informed feature in the main model

**Expected outcome**: Modest improvement (0.01-0.03 AUC) but adds interpretability. More useful for regression models.

---

## 6. Previous-Day Weather Features (MEDIUM IMPACT)

**What**: Use weather from the day *before* the visit rather than (or in addition to) the visit day.

**Why**: The Model Comparison doc found that previous-day weather had significant AUC (p<0.001 in LOOCV). DO responds to weather with a lag — a hot, still day depletes oxygen by the following morning. Our current 3-day and 7-day rolling averages partially capture this, but an explicit "yesterday's weather" feature might be more targeted.

**How**: Add explicit `weather_lag_1d` features (yesterday's temperature, wind, etc.) alongside or replacing the current rolling averages.

---

## 7. Stocking Event Detection (LOW-MEDIUM IMPACT)

**What**: Use the `stocking_harvest.csv` data to detect recent stocking events (adding fish to ponds), and compute biomass-adjusted feed rates.

**Why**: 
- Recently stocked ponds may have stress responses
- Biomass per acre (weight × density) is more predictive than density alone for oxygen demand
- The Model Comparison found biomass itself added no signal (p=0.81), but stocking *timing* was not tested

**How**:
1. Merge stocking data by pond_id
2. Compute "days since last stocking event"
3. Compute current estimated biomass (stocking count × estimated weight at current date)

---

## 8. Nellore Region Expansion (LOW IMPACT on current metrics — high operational value)

**What**: Train a separate model for Nellore ponds, or a combined model with region as a feature.

**Why**: The Eluru and Nellore regions have different characteristics:
- **Nellore**: mostly pelleted feed, different weather patterns, different practices
- **Eluru**: mixed feed types, different pond sizes
- The Model Comparison notes that a separate model may be needed for Nellore

**How**:
1. Filter the public_ara_data to Nellore morning non-follow-up visits
2. Download Open-Meteo weather for Nellore coordinates
3. Train/evaluate with the same pipeline

---

## 9. Dropout-Aware Features (LOW IMPACT)

**What**: Use the `dropouts.csv` data to identify ponds that have dropped out of the program and why, as a feature for remaining ponds.

**Why**: Dropout reasons might correlate with pond quality — if many neighbors dropped out due to "feed costs too high," remaining ponds in the area might be cutting corners.

---

## 10. Walk-Forward Cross-Validation (VALIDATION IMPROVEMENT)

**What**: Instead of a single train/test split, use expanding-window walk-forward validation.

**Why**: Our single 2024-2025 → 2026 split gives a single performance estimate with high variance (only 29 OOR events in test). Walk-forward would:
- Train on months 1-6, test on month 7
- Train on months 1-7, test on month 8
- ... and so on
- Average the metrics for a more robust estimate

**Risk**: Reduces the number of test samples per fold, making each individual fold's metrics noisier. But the average is more reliable.

---

## Experiment Priority Matrix

| # | Experiment | Expected AUC Improvement | Effort | Dependencies |
|---|-----------|-------------------------|--------|-------------|
| 1 | Seasonal training windows | +0.05 to +0.10 | Low | None |
| 2 | Feature selection (→ 26) | +0.05 to +0.15 (tree models) | Low | None |
| 3 | Rank product ensemble | +0.02 to +0.05 | Medium | None |
| 4 | XGBoost early stopping | +0.02 to +0.05 | Low | #2 (feature selection) |
| 5 | Continuous monitor calibration | +0.01 to +0.03 | High | Requires data exploration |
| 6 | Previous-day weather | +0.01 to +0.03 | Low | None |
| 7 | Stocking event detection | +0.00 to +0.02 | Medium | stocking_harvest.csv |
| 8 | Nellore expansion | N/A (new region) | Medium | Nellore weather data |
| 9 | Dropout-aware features | +0.00 to +0.01 | Low | dropouts.csv |
| 10 | Walk-forward CV | N/A (validation) | Medium | None |

**Recommended first experiments**: #1 + #2 together — seasonal training with reduced features. This directly replicates what made the SeasonalDO model successful and is the clearest path to AUC 0.75+.
