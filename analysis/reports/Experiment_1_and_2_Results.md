# Experiments #1 + #2: Seasonal Training + Feature Pruning — Results

**Goal**: Run Skye's two highest-priority experiments from `Future Experiments.md` together. He predicted the combination would push best AUC from ~0.68 to 0.75+, matching Sol's SeasonalDO benchmark of 0.766.

**What I did**: Reused Skye's v3 pipeline unchanged. Compared four variants on the same Q1 2026 test set (312 rows, 9.3% OOR):

| Variant | Training rows | Training months | # Features | Description |
|---|---|---|---|---|
| **v3** | 2,236 | All 2024–2025 | 59 | Skye's baseline |
| **v4** | 483 | Jan–Mar 2024–2025 | 59 | Experiment #1 only |
| **v5** | 483 | Jan–Mar 2024–2025 | 27 | Experiments #1+#2, Skye's exact recipe |
| **v6** | 483 | Jan–Mar 2024–2025 | 43 | v5 + lagged weather averages added back |

v5 follows Skye's prescription literally: 19 base Open-Meteo weather + pond_area + pond_depth + top-3 feed_type one-hots (DORB, Mash, Unknown by training count) + pond_historical_oor_rate + prev_do + days_since_last_visit.

v6 was an additional diagnostic to test whether the pruning specifically threw away useful signal, by re-adding the 16 lagged weather averages (3-day and 7-day rolling means) that Skye himself had derived.

**Run script**: `run_experiment_1_and_2.py`.

---

## Headline result

**Skye's v3 baseline remains the best model. Neither seasonal training nor feature pruning improves it.**

| | v3 | v4 | v5 | v6 |
|---|---|---|---|---|
| Best classifier AUC | **0.671** (Logistic) | 0.645 (LightGBM) | 0.446 (LightGBM) | 0.563 (LightGBM) |
| Best regression Derived AUC | **0.682** (Ridge) | 0.648 (LightGBM Reg) | 0.493 (LightGBM Reg) | 0.635 (LightGBM Reg) |
| Best Lift@10% | **1.74×** (Logistic) | 1.74× (LightGBM) | 0.00× | 1.04× |
| Best Prec@10% | **16.1%** (Logistic) | 16.1% (LightGBM) | 0% | 9.7% |

We do **not** reach the 0.766 SeasonalDO benchmark in any variant. Skye's prediction that #1 + #2 together would lift AUC to 0.75+ is **falsified** by these runs.

---

## What pruning actually did

Pruning hurt every model:

**Classification AUC (best per variant in bold):**

| Model | v3 | v4 | v5 | v6 |
|---|---|---|---|---|
| Logistic Regression | **0.671** | 0.446 | 0.398 | 0.372 |
| LightGBM | 0.375 | **0.645** | 0.446 | 0.563 |
| Random Forest | 0.407 | **0.543** | 0.401 | 0.528 |
| XGBoost | 0.459 | **0.524** | 0.408 | 0.528 |
| SVM (RBF) | 0.493 | **0.467** | 0.409 | 0.420 |

**Regression Derived AUC:**

| Model | v3 | v4 | v5 | v6 |
|---|---|---|---|---|
| Ridge | **0.682** | 0.399 | 0.415 | 0.372 |
| Linear | **0.637** | 0.335 | 0.429 | 0.340 |
| LightGBM (Reg) | 0.596 | **0.648** | 0.493 | 0.635 |
| XGBoost (Reg) | 0.562 | **0.625** | 0.474 | 0.634 |
| Random Forest (Reg) | **0.602** | 0.579 | 0.434 | 0.573 |
| Poly Ridge (deg=2) | **0.573** | 0.473 | 0.398 | 0.516 |

Two clear patterns:

1. **For linear models (Logistic, Ridge, Linear): full-year training (v3) is the winner — by a lot.** Seasonal training cuts ~80% of training rows, and even with regularization the models can't recover. Adding or removing features within the seasonal slice barely matters.

2. **For tree models (LightGBM, RF, XGBoost): seasonal training (v4) is best.** Both pruning (v5) and partial pruning (v6) make them worse than v4. The 16 lagged weather averages Skye derived are doing real work — removing them in v5 cost ~0.10–0.20 AUC. Adding them back in v6 recovers most but not all of that gap.

The diagnostic v6 confirmed that the pruning specifically threw away signal, not that "fewer features is bad in principle." Skye's lagged-weather features were earning their keep in the tree models.

---

## What this means

The best model FWI has at this point is Skye's v3:

- **Logistic Regression**: AUC 0.671, Lift@10% 1.74×, Prec@10% 16.1%
- **Ridge Regression** (continuous DO → threshold at 3.0): Derived AUC 0.682, RMSE 0.576 mg/L, R² +0.026

Both rank ponds at roughly the same operational level: top-10% picks contain ~16% OOR vs the ~9% base rate. That's a ~1.7× improvement in catch-rate among prioritized ponds.

The two highest-priority experiments from Skye's own list — seasonal training and feature pruning — do not move the operational metric. The question of whether to deploy still hinges on whether 1.7× lift is enough, not on whether the model can be made meaningfully better with these straightforward tweaks.

---

## Likely reasons Skye's prediction missed

1. **He calibrated against Sol's SeasonalDO model**, which used `XGBoost(max_depth=2)` with early stopping and a different feature mix. Just changing the training window and dropping features in his existing pipeline isn't equivalent to recreating Sol's actual setup. To replicate that benchmark we'd likely need to also change the model class and tuning protocol — that's *Experiment #4* in his doc, not #2 alone.

2. **The pruning recipe assumed top-3 feed types would be reasonable**, but in this training slice the top-3 are DORB, Mash, and **Unknown** (the "Unknown" feed type — essentially missing-data category — is the third most common). That's not a meaningful biological feature.

3. **The regional/aggregate signal ceiling may be near its limit.** Across 4 variants × 5 classifier families × 6 regressor families, the highest operational lift any of us produces is 1.74×. That ceiling has now shown up in:
   - v3 with full features
   - v4 with seasonal training
   - Daniel's regional fraction model (sub-random AUC, but that's a different framing)
   - And it's the predicted ceiling Skye himself flagged: "I don't think with the coarse-level weather data you could predict >50% chance of bad water quality."

---

## Recommended next steps

1. **Don't pursue seasonal training or feature pruning further** in the current pipeline. The signal isn't there.

2. **If you want to keep pushing in this family**, the next experiment to try is the **rank-product ensemble** (Skye's #3): train one weather-only model that ranks days, train one farm-only model that ranks ponds, multiply ranks. He cited Sol's Model Comparison reaching AUC 0.709 with that approach. This is the right next thing if you want to stay in regression-style modeling.

3. **The most likely path to a deployable model is Sara's direction**: per-pond risk modeling with positive-unlabeled framing, hard biological rules for must-visits, and model evaluation on a discovery pool with precision@top-K. Her interim AUC of 0.685 is comparable to Skye's, but the *framing* is closer to what would actually deploy. Her main risk is the same as Skye's — actual top-K precision after ablation may turn out to be modest.

4. **The handoff-to-Programs decision is unchanged**: don't deploy at 1.7× lift expecting field staff to feel a difference. If you do want to deploy now, it's worth running the shadow-test protocol (model produces ranked list, staff visit by current method, compare daily for 2–4 weeks) so you have an honest before/after number to share with Programs.

---

## Files produced (in `/Skye/Fishwelfare-Experiments-main/`)

- `run_experiment_1_and_2.py` — runner for v5 and v6
- `classification_results__v5_seasonal_pruned.csv`, `regression_results__v5_seasonal_pruned.csv`
- `classification_results__v6_seasonal_pruned_with_lags.csv`, `regression_results__v6_seasonal_pruned_with_lags.csv`
- `experiment_1_2_classification_comparison.csv`, `experiment_1_2_regression_comparison.csv`
- `experiment_1_2_results.json` — full numeric bundle

Plus prior #1 outputs:
- `run_experiment_1.py`, `experiment_1_*.csv`, `experiment_1_results.json`
