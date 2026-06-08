# Experiment #1: Seasonal Training Windows — Results

**Goal**: Per Skye's `Future Experiments.md`, train only on Jan–Mar of 2024 and 2025 (matching the test period months) instead of all of 2024–2025. He predicted this would lift AUC from ~0.68 to ~0.76+, matching Sol's SeasonalDO benchmark.

**What I did**: Re-ran Skye's exact `fish_welfare_model.py` pipeline twice — once unchanged (v3 baseline, full-year training) and once with the training data filtered to Jan–Mar of 2024–2025 (v4 seasonal). Same features, same models, same hyperparameters, same test set (Jan–Mar 2026, 312 rows).

**Run script**: `run_experiment_1.py` (in the repo folder).

---

## Headline result

**Seasonal training did not improve overall performance.**

| | v3 best | v4 best |
|---|---|---|
| Best classifier AUC | **0.671** (Logistic Regression) | **0.645** (LightGBM) |
| Best regression Derived AUC | **0.682** (Ridge) | **0.648** (LightGBM Reg) |
| Best Lift@10% | **1.74×** (Logistic) | **1.74×** (LightGBM) |
| Best Prec@10% | **16.1%** (Logistic) | **16.1%** (LightGBM) |

The best v4 model achieves the *same* operational lift as the best v3 model (1.74× at top 10%, ~16% precision). Headline AUC does not improve. We do **not** reach the 0.766 SeasonalDO benchmark with seasonal training alone.

Training rows dropped from **2,236 → 483** (−78%) — Jan–Mar 2024+2025 only. Test set unchanged.

---

## Where the seasonal change *did* help

Tree-based models (which were heavily overfitting in v3) recovered substantially, exactly as Skye predicted:

| Model | AUC v3 | AUC v4 | ΔAUC |
|---|---|---|---|
| LightGBM | 0.375 | **0.645** | **+0.269** |
| Random Forest | 0.407 | 0.543 | +0.136 |
| XGBoost | 0.459 | 0.524 | +0.066 |

Same direction in regression:

| Model | Derived AUC v3 | Derived AUC v4 | Δ |
|---|---|---|---|
| LightGBM (Reg) | 0.596 | **0.648** | +0.052 |
| XGBoost (Reg) | 0.562 | 0.625 | +0.064 |

So Skye's overfitting diagnosis was right — fewer, more on-distribution training rows let the trees stop memorizing noise. LightGBM in particular went from "worse than random" to the best classifier.

## Where the seasonal change *hurt*

Linear models — which were the v3 winners — collapsed:

| Model | AUC v3 | AUC v4 | ΔAUC |
|---|---|---|---|
| Logistic Regression | **0.671** | 0.446 | **−0.225** |
| SVM (RBF) | 0.493 | 0.467 | −0.026 |
| Ridge Regression (Derived AUC) | **0.682** | 0.399 | **−0.283** |
| Linear Regression (Derived AUC) | 0.637 | 0.335 | −0.302 |

The likely cause: 483 training rows can't support 59 features for regularized linear models — even with C=0.1 / α=10, the L2 penalty isn't strong enough to recover the signal from such a thin training set. The Open-Meteo lag features in particular need many training observations to estimate stable coefficients.

There's also a class-balance shift: train OOR jumped from 10.5% (full year) to 13.7% (Jan–Mar) while test OOR stayed at 9.3%. So v4 training is now further from the test class balance, which is mildly unfavourable for calibration of the linear classifiers.

---

## Why Skye's prediction missed

Skye flagged this risk in the same doc that proposed the experiment: *"Smaller training set may not support 71 features. Will need aggressive feature selection (see Experiment 3)."* What this run shows is that the risk dominates the gain — for linear models, the "fewer rows" cost outweighs the "less seasonal noise" benefit.

The clean operational read: **Experiment #1 alone is not enough**. The full SeasonalDO recipe combined seasonal windows *and* a tighter ~26-feature set (XGBoost with `max_depth=2` and early stopping). To replicate Sol's 0.766 we likely need #1 + #2 together, not #1 in isolation.

---

## What this means for "ready to hand off?"

Same answer as before but with a sharper number behind it: the headline operational metric (Lift@10% = 1.74×, Prec@10% = 16%) is unchanged from v3. Seasonal training is *not* the lever that pushes this from "promising" to "deploy." The next lever to try is #1 + #2 together — seasonal training plus pruning to ~26 hand-selected features — which Skye listed as his single highest-value experiment combination.

---

## Files produced (in `/Skye/Fishwelfare-Experiments-main/`)

- `run_experiment_1.py` — the runner (imports Skye's pipeline as a module)
- `classification_results__v3_full_year.csv`, `regression_results__v3_full_year.csv` — baseline reproduction
- `classification_results__v4_seasonal.csv`, `regression_results__v4_seasonal.csv` — seasonal-training results
- `experiment_1_classification_comparison.csv`, `experiment_1_regression_comparison.csv` — side-by-side
- `experiment_1_results.json` — full numeric bundle

---

## Suggested next step

Run **Experiment #2 (feature pruning to ~26 features) on top of #1**. Skye's recommended starting set: 19 base weather features + pond_area + pond_depth + 3 collapsed feed_type one-hots + pond_historical_oor_rate + prev_do + days_since_last_visit. With 483 rows × ~26 features, the linear models should recover, and the tree models should sharpen further. If that combination doesn't reach AUC 0.75+, then weather + farm features genuinely cap out around the current operational lift, and the conversation shifts to whether 1.7× lift is enough to deploy — or whether to wait for Sara's per-pond modeling work.
