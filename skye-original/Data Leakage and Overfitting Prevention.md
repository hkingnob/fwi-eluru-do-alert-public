# Data Leakage & Overfitting Prevention

This document explains every decision made to ensure the DO prediction model produces **honest, operationally realistic results** — not inflated metrics that would collapse in deployment.

---

## 1. Feature Leakage: What We Excluded and Why

The most dangerous form of leakage in this problem is using features **measured at the visit** to predict the outcome **of that visit**. If we include pH, water temperature, or behavioral signs, the model essentially learns "ponds with bad water quality … have bad water quality." That gives impressive AUC in testing but is useless operationally — you'd have to visit the pond to get the data needed to decide whether to visit the pond.

### Features EXCLUDED (measured at the visit)

| Feature | Why Excluded |
|---------|-------------|
| **pH** | Measured by ProDSS at the pond during the visit |
| **Water temperature (°C)** | Measured by ProDSS at the pond during the visit |
| **Ammonia (TAN, NH3)** | Measured by photometer at the pond during the visit |
| **Turbidity** | Measured by Secchi disk at the pond during the visit |
| **TDS, Alkalinity, Hardness** | Measured at the pond during the visit |
| **Water color** | Observed by field staff at the pond during the visit |
| **Weather at visit** | Observed by field staff during the visit (even though weather is broadly predictable, the one-hot categories like "Sunny, Foggy" reflect what was actually seen, not a forecast) |
| **Behavioral signs** (air gulping, tail splashing, dead fish) | Observed by field staff at the pond during the visit |
| **Feed amount (current visit)** | Recorded at the visit as the farmer's current feeding |
| **Stocking density (current visit)** | Reported at the visit |

### Features INCLUDED (available before the visit)

| Feature | Source | Rationale |
|---------|--------|-----------|
| **Pond area, depth** | Enrollment data | Static farm characteristics, known from day 1 |
| **Feed type** (one-hot) | Enrollment data | Slow-changing farm configuration. The SeasonalDO model found `feed_Other` was the #1 predictive feature |
| **Previous visit's feed amount** | Last visit record | Uses `shift(1)` — strictly the prior visit's value |
| **Previous visit's stocking density** | Last visit record | Uses `shift(1)` — strictly the prior visit's value |
| **Previous visit's DO** | Last visit record | Uses `shift(1)` — the DO from the *last* visit, not the current one |
| **Previous feed per fish** | Derived from shifted values | `prev_feed_amount / (prev_stocking_density × pond_area)` |
| **Historical OOR rate** | All prior visits | Running average of OOR outcomes from all previous visits to this pond |
| **Days since last visit** | Visit dates | Calendar gap, not dependent on visit outcome |
| **Number of previous visits** | Visit count | Cumulative count, measures experience with this pond |
| **Month** (one-hot) | Calendar | Known before the visit |
| **Season** (one-hot: dry/pre_monsoon/monsoon/post_monsoon) | Calendar | Known before the visit |
| **Day of week** | Calendar | Captures operational patterns (is there a Monday/Friday effect?) |
| **19 Open-Meteo daily weather vars** | Open-Meteo archive API | Historical weather (temp, wind, humidity, solar, precip, pressure, cloud cover). In deployment, these would come from day-ahead weather forecasts. See "Weather Features" section below. |
| **16 lagged weather averages** | Derived from Open-Meteo | 3-day and 7-day rolling averages of 8 key weather variables |
| **Temp range, humidity range** | Derived from Open-Meteo | Diurnal swing — affects DO through gas solubility and photosynthesis cycles |

---

## 2. Temporal Split: Train 2024–2025, Test 2026

### Why not random split?

A random train/test split would leak future information into the training set. If a pond's March 2026 visit is in the training set, the model "sees" 2026 patterns while trying to predict other 2026 visits. This is especially problematic with:  
- **Seasonally shifting OOR rates** (dry season has different risk factors than monsoon)
- **Year-over-year distribution shifts** in weather, feed practices, and measurement methods
- **Autocorrelated pond histories** (a pond's visits are not independent)

### Our split

| Set | Period | Rows | OOR Rate |
|-----|--------|------|----------|
| **Training** | Jan 2024 – Dec 2025 | 2,236 | 10.5% |
| **Test** | Jan – Mar 2026 | 312 | 9.3% |

This simulates the real deployment scenario: the model is trained on all available historical data and deployed to predict future visits. The 2024–2025 training period includes the switch to the Winkler method (which changed DO measurement values), giving the model exposure to the measurement regime used in 2026.

### Why this is the hardest honest test

The SeasonalDO model comparison document notes that **all five original models trained on full-year 2025 failed on 2026 data** (AUC dropped to 0.470). Weather-OOR relationships are seasonal — monsoon-era patterns don't apply to dry season. By training on 2024–2025 (which includes dry-season months from both years), we give the model the best chance to learn season-appropriate patterns.

### What we did NOT do

- **No walk-forward CV within the test set**: The 312 test rows are scored in a single batch, with no iterative retraining as 2026 data arrives. This avoids information leakage from later 2026 visits informing the model about earlier ones.
- **No LOOCV on the full dataset**: Models trained with LOOCV (as some models in the comparison document used) can inflate AUC because they see 2025 data from all months while predicting individual 2025 visits. Our model has never seen any 2026 data.

---

## 3. Overfitting Prevention

### The small-dataset problem

With 2,236 training rows, 312 test rows, and only ~10% positive rate (~235 OOR in training, ~29 in test), overfitting is a primary concern. Here's what we did:

### 3a. Removed granular temporal features

| Removed | Why |
|---------|-----|
| **`day_of_year`** | With 365 possible values, the model can memorize that "day 47 is high-risk" from a single year. This doesn't generalize. |
| **`week_of_year`** | Same issue — 52 buckets, each with ~40 training rows. Model memorizes noise. |

| Kept | Why |
|------|-----|
| **`month`** (one-hot, 12 values) | Months capture genuine seasonal patterns (monsoon, dry). Each bucket has ~100-200 training rows. |
| **`season`** (one-hot, 4 values) | Even coarser than month — each bucket has 400+ rows. |
| **`day_of_week`** (0–6) | Only 7 values, captures operational patterns, not calendar-specific dates. |

### 3b. Stronger regularization

All models use conservative hyperparameters designed to prevent memorization:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `max_depth` | 3 (ensemble) | Shallow trees = simpler decision boundaries |
| `min_child_weight` / `min_samples_leaf` | 10 | Each leaf must represent ≥10 observations |
| `subsample` / `colsample_bytree` | 0.8 | Each tree sees only 80% of rows and features (stochastic regularization) |
| `reg_alpha` (L1) | 1.0 | Encourages feature sparsity |
| `reg_lambda` (L2) | 5.0 | Penalizes large coefficients/splits |
| `C` (Logistic Regression) | 0.1 | Strong inverse regularization (smaller C = more regularization) |
| `n_estimators` | 200 | Moderate ensemble size (not 1000+) |
| Poly Ridge `alpha` | 100.0 | Heavy ridge penalty needed because degree-2 polynomial expansion creates hundreds of features from 34 inputs |
| Poly Ridge `interaction_only` | True | Only creates pairwise interaction terms, not squared terms — reduces feature explosion |

### 3c. Feature count discipline

We use **71 features** — a ratio of ~31 training samples per feature (2,236 / 71). This is lower than ideal, which is why:
- **Regularized linear models (Logistic Regression C=0.1, Ridge α=10) handle this well** and are our best performers
- **Tree-based models (RF, XGBoost, LightGBM) overfit** despite conservative hyperparameters — 71 features gives trees too many split candidates to find spurious patterns in 2,236 rows
- The SeasonalDO model used only 26 features (19 weather + 7 farm) — fewer features worked better for XGBoost there

### 3d. No data-dependent feature selection

We did **not** perform feature selection based on test-set performance. The feature set was chosen based on domain knowledge:
- What's available before a visit? → Include
- What's measured at the visit? → Exclude

No recursive feature elimination (RFE) or forward selection was used on the test set, which would inflate metrics.

---

## 4. Historical Feature Construction (No Leakage in Lag Features)

### How `pond_historical_oor_rate` is computed

```python
# For each visit, OOR rate is computed from ALL PREVIOUS visits only
for each visit in chronological order:
    oor_rate = mean(all prior OOR outcomes for this pond)
    # This visit's outcome is NOT included in its own oor_rate
```

This uses a **strictly expanding window** — each visit's historical rate reflects only what was known before that visit occurred.

### How lagged features work

```python
df["prev_do"] = df.groupby("pond_id")["do_mg_l"].shift(1)
df["prev_feed_amount"] = df.groupby("pond_id")["feed_amount"].shift(1)
```

`shift(1)` looks at the **immediately preceding visit** to the same pond. For the first visit to a pond, these are NaN (imputed with the training set median — a conservative choice).

### Cross-set contamination check

The historical OOR rate for 2026 test data ponds includes their 2024–2025 visit outcomes (which are in the training set). This is **not leakage** — it's exactly how the model would work in deployment: you know a pond's full history before visiting it. The model does NOT see any 2026 visit outcomes during training.

---

## 5. Weather Features: Why They Are Not Leakage

Weather features from Open-Meteo use **historical reanalysis data** — the actual weather that occurred on the day of each visit. This is a valid proxy for **weather forecasts** because:

1. **In deployment**, the model would use the day-ahead weather forecast from Open-Meteo for the visit date. Day-ahead forecasts for temperature, humidity, and wind are highly accurate (correlation >0.95 with actuals).
2. **Weather is area-level**, not pond-level — it's the same for all ~111 ponds. The Model Comparison doc notes "weather is uniform across the area — ranks days, not ponds."
3. **We use the ARA categorical weather field ("Sunny", "Foggy") as an EXCLUDED variable** because it's observed at the visit. The Open-Meteo data is a forecast-obtainable alternative.
4. **Lagged features** (3-day, 7-day rolling averages) use only past weather — they capture multi-day accumulation effects on DO (e.g., consecutive hot/still days depleting oxygen).

---

## 6. How to Interpret the Results

### Classification results (AUC 0.37–0.67)

- **Logistic Regression** achieved the best direct classification AUC (0.671)
- **Tree-based models overfit** — their AUC dropped below 0.50 (worse than random) because 71 features on 2,236 rows gives too many degrees of freedom
- The SeasonalDO model achieved AUC 0.766 using a **seasonal training window** (same calendar months only) with only 26 features — suggesting that both feature selection and training window matter

### Regression + thresholding is superior

- **Ridge Regression** achieves a Derived AUC of **0.682** (threshold predicted DO at 3.0 mg/L to classify), outperforming all direct classifiers
- This works because Ridge's strong L2 regularization (α=10) prevents the weather features from overfitting, while still extracting their real signal

### Why we're confident the results are honest

- The model has **never seen any 2026 data** during training
- All features are **available before the visit** in real operations
- **No hyperparameter tuning on the test set** was performed
- The results are consistent with the Model Comparison document: weather + farm features combined should give AUC in the 0.65-0.77 range depending on methodology

---

## 7. Summary Checklist

| Risk | Mitigation | Status |
|------|-----------|--------|
| Using at-visit measurements as features | Excluded all ProDSS/photometer/observation data | ✅ |
| Future data leaking into training | Strict temporal split: train ≤2025, test = 2026 | ✅ |
| Overfitting to specific calendar dates | Removed day_of_year, week_of_year; kept month/season | ✅ |
| Overfitting with too many features | 71 features with strong L1/L2 regularization; noted tree-model degradation | ✅ |
| Historical feature leakage | Expanding window (shift, cumulative mean), no current-visit data | ✅ |
| Test-set-based feature selection | Feature set based on domain knowledge only | ✅ |
| Polynomial feature explosion | interaction_only=True, alpha=100 ridge penalty | ✅ |
| Cross-set pond contamination | Historical features use only prior outcomes; model never sees 2026 labels | ✅ |
| Weather as leakage | Uses historical actuals as proxy for forecasts; ARA categorical weather still excluded | ✅ |
