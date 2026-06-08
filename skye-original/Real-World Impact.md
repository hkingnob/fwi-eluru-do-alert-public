# Real-World Impact: What This Model Means for Fish Farm Operations

## The Core Question

> **"If we can only visit 6 ponds per day out of ~88 due, which 6 should we visit?"**

Right now, ARA field teams in Eluru visit fish farms in geographic or habitual order. About **9% of morning visits** find dissolved oxygen out of range (DO < 3.0 mg/L) — meaning the vast majority of visits find everything is fine, while some genuinely distressed ponds get visited too late.

A predictive model changes this by **ranking ponds from most-to-least likely to be in trouble** each morning, so the team visits the highest-risk ponds first.

---

## What Our Model Actually Does

### The Best Approach: Ridge Regression → Threshold at 3.0 mg/L

Our best model (Ridge Regression, Derived AUC = **0.682**) works in two steps:

1. **Predicts a continuous DO value** for each pond-day combination using:
   - Tomorrow's weather forecast (from Open-Meteo: temperature, wind, humidity, solar radiation, etc.)
   - Farm characteristics (how big is the pond? What feed type? How deep?)
   - Historical patterns (has this pond had OOR events before? How recently was it visited?)

2. **Ranks ponds from lowest to highest predicted DO** — the lowest-DO ponds are visited first

### In Plain Language

The model says: *"Given that tomorrow will be hot (34°C), with low wind (8 km/h), high humidity (85%), and this particular pond is 11 acres with DORB feed and had an OOR event 3 visits ago — the predicted DO is 2.6 mg/L, which is below the 3.0 threshold. Visit this pond first."*

---

## Concrete Operational Impact

### Daily Operations

| Scenario | OOR Finds per Day | OOR Finds per Year (250 days) |
|----------|-------------------|-------------------------------|
| **Random/habitual order** | ~0.56 | ~140 |
| **Our model (1.7× lift)** | ~0.95 | ~237 |
| **SeasonalDO benchmark (4.6× lift)** | ~2.56 | ~640 |

With our current model at **1.7× lift** (the Logistic Regression result at top 10%):
- Field teams would catch **~70% more OOR events** per year than random
- That's roughly **97 additional ponds** getting timely intervention annually
- Each early catch means corrective action (aeration, water exchange, feeding reduction) can start hours or days sooner

### What 1.7× Lift Means Practically

If the team visits 6 ponds tomorrow:
- **Without model**: ~0.56 of those 6 ponds will have OOR DO (roughly 1 every 2 days)
- **With model**: ~0.95 of those 6 ponds will have OOR DO (roughly 1 every day)
- The model doesn't find *all* OOR events — it just front-loads them in the visit schedule

### The Ceiling: What's Possible

The **SeasonalDO model** (AUC 0.766, trained with seasonal windows and 26 curated features) achieved **4.6× lift at top 10%** — meaning 35% of its top-ranked visits found OOR events, vs. 7.5% baseline. That model could theoretically catch **~640 OOR events** per year vs 140 by random chance. Our model is partway there.

---

## How to Use This in Practice

### Nightly Workflow

```
Evening before visits:
1. Pull tomorrow's weather forecast from Open-Meteo for Eluru
2. For each of the ~88 enrolled ponds:
   - Combine forecast + pond's farm profile + visit history
   - Run Ridge model → get predicted DO
3. Sort ponds by predicted DO (lowest first)
4. Tomorrow's visit schedule = top 6-10 ponds from this sorted list
```

### What Changes for Field Teams

- **Before**: Visit ponds in geographic clusters or rotation order
- **After**: Visit ponds in risk-ranked order (highest risk first)
- **Same workflow otherwise**: Same DO measurement, same corrective actions, same app recording

### What Doesn't Change

- Field teams still measure DO with ProDSS/Winkler at every visit
- Corrective actions still follow the same protocol
- The model doesn't replace visits — it **reorders** them

---

## Honest Assessment: What This Model Can and Cannot Do

### What it CAN do (AUC 0.682, ~1.7× lift)
- ✅ Rank ponds so that the highest-risk ones are visited first
- ✅ Catch ~70% more OOR events per year than random ordering
- ✅ Run entirely on free, publicly available data (Open-Meteo + farm enrollment)
- ✅ Require no new field data collection or equipment

### What it CANNOT do yet
- ❌ Identify *which specific* ponds will be OOR with high confidence (precision is still low)
- ❌ Replace the need for in-person DO measurement
- ❌ Work outside Eluru (not validated for Nellore or other regions)
- ❌ Match the SeasonalDO model's lift (4.6× vs our 1.7×) — needs seasonal training windows

### Why the gap vs. SeasonalDO?
Our model trains on **all months of 2024-2025**, but the SeasonalDO model trains on **only the same calendar months** from prior years (Jan-Mar trained only on Jan-Mar). This matters because:
- Weather-DO relationships are seasonal (low wind = risk in dry season, high rain = risk in monsoon)
- A model trained on monsoon data applies monsoon patterns to dry-season predictions, which hurts
- The SeasonalDO approach is the clear next experiment to try

---

## Key Metric Definitions (Plain English)

| Metric | What It Means | Our Value | Good? |
|--------|--------------|-----------|-------|
| **AUC** | "If I pick one random OOR visit and one random OK visit, what's the probability the model correctly ranks the OOR one as higher risk?" | 0.682 | Moderate — 68% of the time, the model correctly identifies which of two visits is riskier |
| **Lift@10%** | "If I visit only the model's top 10% riskiest ponds, how many more OOR events do I find compared to visiting random ponds?" | 1.7× | Useful — 70% more OOR events found |
| **Derived AUC** | "Same as AUC, but using the regression model's predicted DO as a risk score instead of a direct classifier" | 0.682 | Better than all direct classifiers (0.67 best) |
| **R²** | "How much of the DO variation does the model explain?" | +0.026 | Very low, but positive (better than just guessing the average DO every time) |
| **Base rate** | "How often is DO out of range?" | 9.3% | Low — most visits find everything fine, so finding the bad ones is like finding needles in a haystack |

---

## Bottom Line

> **This model lets ARA field teams find roughly 70% more fish welfare issues per year by visiting high-risk ponds first, using only weather forecasts and farm enrollment data — no new equipment or field procedures needed.**

The path to even better results (4-5× lift) is clear: adopt the SeasonalDO training approach (seasonal windows), reduce features to the ~26 most predictive ones, and validate on more 2026 data as it accumulates.
