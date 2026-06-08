# Calibration Updates Following Jennifer's Feedback

**Date:** June 2026
**Companion to:** [Jennifer_Feedback_May_2026.md](Jennifer_Feedback_May_2026.md)

When Jennifer (FWI's Director of Programs) reviewed the model and web app in May 2026, she raised several substantive concerns about how the headline result was being framed, how impact would translate, and how the model should be tested. Most of her points were well-founded; we updated the project accordingly. This document records what changed in response, so anyone reviewing the public materials can see the evolution from the initial framing to the current one.

---

## Changes made in response

### 1. Headline framing: "1.7× lift" replaced with absolute-impact context

**Before:** The web app and internal communications led with "Alert days have a 1.7× higher OOR rate than Normal days." Strictly true, but easy to misinterpret as a transformational improvement.

**After:** We added the absolute-impact framing alongside the relative one. The capacity-neutral reallocation simulation in `analysis/results/ytd_policy_comparison.csv` shows that **optimal reweighting of existing visits catches ~3 extra OOR events over 4 months on 513 total visits** — extrapolated to roughly +9 catches per year against a baseline of ~135. That's a ~7% absolute improvement, not the 70% the per-visit lift could suggest. Both numbers are now quoted together so users can see the gap between per-visit productivity and total operational gain.

### 2. April 2026 failure mode now disclosed

Jennifer's spot-check found that the model fired only one Alert day in April 2026 despite a higher-than-baseline OOR rate that month. We verified this directly in `analysis/results/ytd_daily_with_alerts.csv`: April had 18 days with visits, 1 model-fired Alert, 17 OOR events out of 144 visits (11.8% — above the YTD baseline). The model missed five high-OOR clusters that month.

This is now explicitly flagged in the web app's Limitations section and in the analysis reports. It supports the broader point that weather alone is not the full driver of OOR risk in non-dry-season months.

### 3. Welfare impact framing made explicit

Jennifer noted that **the majority of FWI's "fishes helped" instances (and all 2025 instances) involved DO plus another parameter (e.g. pH, ammonia) being out of range simultaneously**, not DO alone. Since our model only predicts DO risk, catching more DO-only events only partially translates to additional welfare impact. This caveat is now in the web app's Limitations section and in the blog post text.

### 4. Testing approach changed from shadow-test to implementation-test

**Before:** The originally proposed test was a 12-week shadow log — staff would record the alert tier alongside normal visits, with no operational change. Decision criterion at week 12: Alert OOR ≥ 1.5× Normal OOR with 90% CI lower bound above 1.0.

**After:** Per Jennifer's recommendation, we replaced this with an **implementation test**: from June through August 2026, on Alert days staff actually deploy 1–3 extra visits, and we measure the OOR rate of those marginal visits against the baseline. This directly answers the operational question ("do the *extra* visits catch OOR?") rather than the indirect one ("does the per-visit rate gap replicate?"). Reevaluation points every 3 weeks.

The reasoning: marginal-visit OOR rate is structurally different from average-visit OOR rate, because the marginal pond visited is typically lower-priority than the ones staff would normally choose. The shadow test wouldn't have measured this; the implementation test does.

### 5. Retraining cadence acknowledged

Jennifer asked how the model handles changes over time. We've now committed to quarterly retraining as part of the deployment plan — the existing `model/export_model_for_webapp.py` and `model/export_historical_oor.py` scripts will be re-run with new data each quarter and the resulting JSONs re-embedded in the web app.

---

## What did not change

Jennifer's note that "this is not a highly scalable model" is correct, and we accept it. The model's value, even if everything works, is a modest improvement in the order of detection (catching some OOR events a few days sooner) rather than a transformational change in visit capacity or coverage. We're proceeding with the implementation test precisely because the deployment cost is near-zero, but we have not over-claimed scalability.

The fundamental ceiling — that a regional weather model can rank days but not differentiate ponds — is also accepted. Future modeling work, if undertaken, would need different feature sources (per-pond observations, farm-management variables, or biological rules) to break through that ceiling. See `skye-original/Future Experiments.md` for the experiments we have already tested and ruled out.

---

## How to read the rest of these materials

If you're looking at this repo to evaluate the work:

- Start with the top-level `README.md` for orientation.
- Open the [live web app](https://hkingnob.github.io/fwi-eluru-do-alert/) to see what the model actually outputs and how it's framed for staff.
- Read [Jennifer_Feedback_May_2026.md](Jennifer_Feedback_May_2026.md) for the critique that shaped the current version.
- Read the experiment reports (`Experiment_1_Seasonal_Training_Results.md`, etc.) for what was tried at the modeling level and why most of it didn't move the operational metric.
- Look at `ytd_policy_comparison.csv` for the deployment-policy simulation that grounds the absolute-impact numbers.

Anything that's still framed in the older "1.7× lift" way without the absolute-impact context should be considered stale — please flag it to Haven.
