# Experiments #3 (Rank-Product Ensemble) and #4 (XGB Early Stopping) — Results

**Goal**: Run the remaining two experiments from Skye's `Future Experiments.md` that have a real shot at beating the 1.74× lift ceiling we hit in v3, v4, v5, v6.

**What I did**:
- **#3 Rank-Product Ensemble**: Trained weather-only and farm/history-only Logistic Regression and Ridge Regression separately on v3 setup (full-year 2024-25 training, 312-row Q1 2026 test). Combined predictions via rank product as Skye specified.
- **#4 XGBoost(max_depth=2, lr=0.03, early_stopping=50)**: The closest reasonable reproduction of Sol's "SeasonalDO" recipe inside Skye's pipeline. Tested 4 variants — full-year vs. seasonal training, with each year used as validation.

**Run script**: `run_experiments_3_and_4.py`.

---

## Headline result

**For the first time, we have variants that meaningfully exceed the 1.74× ceiling on top-K precision.**

| Variant | AUC | Prec@5% | Prec@10% | **Lift@5%** | **Lift@10%** |
|---|---|---|---|---|---|
| **v3 baseline (Logistic, joint)** | 0.671 | 13.3% | 16.1% | 1.43× | 1.74× |
| **#3 Ridge weather-only** | 0.640 | 20.0% | **22.6%** | 2.15× | **2.43×** |
| **#3 LR weather-only** | 0.558 | 13.3% | **22.6%** | 1.43× | **2.43×** |
| **#4c XGB seasonal, val=2025** | 0.553 | **33.3%** | 19.4% | **3.59×** | **2.08×** |

But — these come with serious caveats. Read on.

---

## Experiment #3: Rank-Product Ensemble

Skye predicted this would lift AUC to 0.70+ (Sol's Model Comparison cited 0.709). It approximately matched but didn't exceed v3 baseline AUC, but produced an interesting decomposition.

| Model | AUC | Prec@5% | Prec@10% | Prec@20% | Lift@10% |
|---|---|---|---|---|---|
| LR weather-only | 0.558 | 13.3% | **22.6%** | 16.1% | **2.43×** |
| LR farm-only | 0.666 | 20.0% | 12.9% | 12.9% | 1.39× |
| LR rank-product | 0.684 | 6.7% | 12.9% | 17.7% | 1.39× |
| Ridge weather-only (DerAUC) | 0.640 | 20.0% | **22.6%** | 12.9% | **2.43×** |
| Ridge farm-only (DerAUC) | 0.571 | 6.7% | 9.7% | 17.7% | 1.04× |
| Ridge rank-product (DerAUC) | 0.681 | 20.0% | 12.9% | 16.1% | 1.39× |

**The rank-product combination didn't help.** Combined AUCs (~0.68) are essentially the same as v3 baseline (0.682). Top-K precision is similar to or worse than the individual single-axis models.

**But the weather-only models alone are strong on operational metrics**: Prec@10% = 22.6% and Lift@10% = 2.43× — substantially better than v3 baseline's 16.1% / 1.74×.

### What this actually means — important nuance

Weather-only models give every pond on the same day the **same prediction** (weather features don't vary by pond). With ~88 enrolled ponds and ~30 days in Q1 2026, the test set has ~10 ponds per day on average. So "top 10%" of weather-only predictions = **all ponds on roughly the top 3 worst-weather days**.

In other words, the weather-only model isn't ranking ponds — it's ranking *days*. The 22.6% Prec@10% means: on the worst 3 weather days, 22.6% of the visits found OOR (vs. the 9.3% baseline across all days). That's a strong "bad-day signal" but it's not a per-pond ranker.

This is genuinely operationally useful in a different way than v3. It suggests: **on a high-risk weather day, the model effectively says "send more staff today, prioritize chronic ponds."** It does not help you choose between ponds on a normal day.

The rank-product result (which adds back the per-pond signal but loses the top-K precision boost) suggests that the joint v3 model is already implicitly doing this decomposition — combining day-level weather risk with pond-level static risk, just less cleanly than running them separately.

---

## Experiment #4: XGBoost(max_depth=2, early_stopping=50)

This is the closest reasonable replication of Sol's "SeasonalDO" recipe inside Skye's pipeline. Four variants tested, varying the training filter and which year is used as the validation set for early stopping.

| Variant | Train rows | Best iter | AUC | Prec@5% | Prec@10% | Lift@10% |
|---|---|---|---|---|---|---|
| 4a full-year, val=2025 | 1,409 | 744 | 0.540 | 0% | 9.7% | 1.04× |
| 4b full-year, val=2024 | 1,409 | 854 | 0.490 | 6.7% | 9.7% | 1.04× |
| **4c seasonal Jan-Mar, val=2025** | **159** | 311 | 0.553 | **33.3%** | **19.4%** | **2.08×** |
| 4d seasonal Jan-Mar, val=2024 | 324 | 523 | 0.533 | 6.7% | 9.7% | 1.04× |

**4c is the standout**: Prec@5% = 33.3% (vs v3's 13.3%), Prec@10% = 19.4% (vs v3's 16.1%), Lift@5% = 3.59×, Lift@10% = 2.08×.

But the warning signs are serious:

1. **AUC is only 0.553** — barely above random. The model is bad at general ranking, but happens to be good at pulling the top few candidates to the top.

2. **Training set is 159 rows** (Jan-Mar 2024 only). Validation is 324 rows (Jan-Mar 2025). With 16 OOR events in the top 5% of test, getting 5–6 of them right gives 33% precision but is statistically thin.

3. **The flip-side variant 4d** (val=2024 instead of 2025) returns to baseline performance (Lift@10% = 1.04×). So 4c may be partly luck — the specific 2024 training rows happened to ID a pattern that holds in 2026.

4. **No equivalent variant of Sol's reported AUC 0.766** — closest we get is 0.553. Either Sol's number relied on a methodology detail not captured in Skye's pipeline (LOOCV, different feature set, different hyperparameters), or it didn't replicate cleanly to begin with. Worth interpreting Sol's benchmark with caution.

---

## Combined picture across all experiments

| Variant | Best AUC | Best Lift@10% | Key claim |
|---|---|---|---|
| v3 (Skye baseline) | **0.682** (Ridge) | 1.74× (Logistic) | Joint model, full features, full year |
| v4 (seasonal) | 0.648 (LightGBM Reg) | 1.74× (LightGBM) | No improvement over v3 |
| v5 (seasonal + pruning) | 0.493 (LightGBM Reg) | 0.00× | Hurt across the board |
| v6 (v5 + lagged weather) | 0.635 (LightGBM Reg) | 1.04× | Partial recovery |
| **#3 weather-only** (Ridge) | 0.640 | **2.43×** (worst-weather days) | Strong but ranks days, not ponds |
| **#4c XGB seasonal val=2025** | 0.553 | **2.08×** | Promising but high noise |
| #3 rank-product | 0.684 | 1.39× | Ties v3 AUC, no operational gain |

---

## What I actually think now

Two real things came out of these experiments. Both meaningful, neither clean.

**1. We have a credible "bad-weather-day alert" signal.** The Ridge weather-only model gives 2.43× lift on the top 10% — but the way to read that is "on the worst ~3 weather days of a quarter, OOR is ~22% instead of ~9%." That's the right interpretation, not "choose 10 ponds today." Operationally, that translates to: the model can flag "today is a high-risk DO day" with real signal. ARA could use it as a *trigger to do more visits or prioritize chronic-risk ponds on those days*, rather than a daily routing tool. This is genuinely simpler to deploy and harder to misuse — staff don't change routing on normal days, but on flagged days they shift effort. This may be the most operationally honest version of what the data supports.

**2. XGBoost early-stopping on seasonal data shows promise but is too noisy to commit to.** 4c is the highest top-K precision we've seen (33% Prec@5%, 19% Prec@10%), but with 159 training rows and an AUC barely above random, it could be partly luck. The flip-side variant (4d) returns to baseline. Before treating this as a real improvement, I'd want to see it stable across multiple validation splits and ideally a fresh test slice (Q2 2026 data when it arrives). The fact that the analogous variant with val=2024 doesn't reproduce the gain is a serious caution flag.

**3. Sol's 0.766 SeasonalDO benchmark probably didn't replicate cleanly to begin with.** Across two experiments specifically designed to approach that recipe (#1 alone, #1+#2 in the pruning runs, and #4 with the actual XGB hyperparameters), the closest AUC we get is around 0.65. Either Sol's methodology had a subtle leakage source (LOOCV across years, as Skye flagged, would do this), or the reported 0.766 used a feature set or tuning detail we don't have access to. Either way, the realistic ceiling for this family of models on FWI data appears to be in the AUC 0.65–0.70 range, with the operational ceiling around 1.7–2.5× lift depending on whether you're doing per-pond ranking or per-day flagging.

---

## Recommendation, updated

Given the experiments:

1. **Consider a "bad-weather-day flag" as the simplest deployable artifact**, instead of (or alongside) per-pond routing. The weather-only Ridge model gives a clean signal at ~2.4× lift on the worst-weather days. ARA could pilot this as a daily "high-risk weather alert" that triggers extra effort on chronic-risk ponds. This is much easier to validate operationally (you see a binary alert/no-alert prediction, easy to track) and harder to misinterpret than a continuous pond-level score.

2. **Don't deploy XGB-4c yet.** The Prec@5% = 33% is the most exciting number, but I don't trust it without a second held-out slice or a stability check across multiple validation seeds. Worth re-running once Q2 2026 data is available.

3. **The handoff to Programs decision now has a clearer fork**: either pitch the bad-weather-day alert (simple, defensible, modest welfare gain) or wait for Sara's per-pond model to land. Don't pitch the v3 daily ranking — the rank-product result confirms that v3 isn't really doing anything beyond what the weather-only model captures.

---

## Files produced (in `/Skye/Fishwelfare-Experiments-main/`)

- `run_experiments_3_and_4.py` — the runner
- `experiment_3_rank_product_results.csv`
- `experiment_4_xgb_earlystop_results.csv`
- `experiments_3_4_results.json`
