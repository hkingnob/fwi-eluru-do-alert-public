# FWI Eluru Daily DO Risk Alert — Public Mirror

This is the **publicly-shareable version** of Fish Welfare Initiative's internal repo for our weather-based daily dissolved-oxygen risk model. We've published it in the interest of transparency, so that other welfare organisations, researchers, and interested members of the public can see what we tried, what worked, what didn't, and what we plan to do next.

> **What is this?** A self-contained web app that flags daily DO-risk levels for Eluru, India, based on weather forecasts, plus all the model code, analysis, and write-ups behind it. Currently in field testing with our Programs team (June–August 2026). See the [blog post](https://www.fishwelfareinitiative.org) for the public-facing summary.

---

## Quick links

- **Web app**: [https://hkingnob.github.io/fwi-eluru-do-alert/](https://hkingnob.github.io/fwi-eluru-do-alert/) — open this in any browser to see today's forecast and risk level, look up historical days, and read the methodology.
- **One-page summary of the model + its limits**: visible in the web app itself (open `docs/index.html`).
- **What field staff will actually do during the test**: see the "Trial design" tab in the web app, or `analysis/reports/Calibration_Updates_June_2026.md`.
- **Why we're testing it this way (with caveats)**: `analysis/reports/Jennifer_Feedback_May_2026.md`.
- **Skye Nygaard's original repo** (the pipeline this is built on): [github.com/SkyeNygaard/Fishwelfare-Experiments](https://github.com/SkyeNygaard/Fishwelfare-Experiments).

---

## What this model does (and what it doesn't)

It predicts, for each upcoming day, whether **regional weather conditions in Eluru** are unusually associated with low dissolved oxygen at fish-farm ponds. It outputs one of three tiers — Normal, Elevated, or High — and the deployment-time recommendation treats Elevated and High as a single "Alert" tier.

On YTD 2026 data (513 morning visits across 79 days), Alert days had an OOR rate of ~11.6% vs ~6.7% on Normal days — a **1.7× per-visit lift**. In absolute terms, optimal reweighting of existing visits would catch about **~3 extra OOR events per quarter** on the same total visit budget. The signal is real but modest, and field-testing will tell us whether it holds outside the dry season.

It **does not** identify which specific ponds will have low DO — it predicts regional risk, not per-pond risk. It only targets dissolved oxygen, not multi-parameter water quality, which limits its translation to fishes-helped impact. See `analysis/reports/Calibration_Updates_June_2026.md` for the full set of caveats and how the framing has been refined.

---

## What's in this repo

```
fwi-eluru-do-alert-public/
├── README.md                         ← you are here
├── LICENSE                           MIT
├── docs/
│   └── index.html                    the self-contained web app
├── model/
│   ├── README.md
│   ├── model_for_webapp.json         trained Ridge regression — coefficients, scaler params, thresholds
│   ├── historical_oor_for_webapp.json daily FWI ground truth (anonymised aggregates) for the web app's Historical Lookup tab
│   ├── export_model_for_webapp.py    re-trains and re-exports the model
│   └── export_historical_oor.py      re-exports the per-date ground truth
├── analysis/
│   ├── README.md
│   ├── run_experiment_1.py           Experiment #1 (seasonal training)
│   ├── run_experiment_1_and_2.py     Experiments #1 + #2 (seasonal + feature pruning)
│   ├── run_experiments_3_and_4.py    Experiments #3 (rank-product) + #4 (XGB early stopping)
│   ├── run_deployment_simulation.py  the YTD deployment-policy simulation
│   ├── results/                      CSV outputs from all experiments
│   └── reports/
│       ├── Experiment_1_Seasonal_Training_Results.md
│       ├── Experiment_1_and_2_Results.md
│       ├── Experiments_3_and_4_Results.md
│       ├── Jennifer_Feedback_May_2026.md      ← read this
│       └── Calibration_Updates_June_2026.md   ← and this
├── data/
│   ├── README.md
│   └── 2026_measurements_YTD_anonymized.csv   513 visits, Jan–early May 2026; farmer names stripped, pond IDs remapped to opaque public IDs
└── skye-original/
    └── ...   snapshot of Skye Nygaard's pipeline, anonymised where needed
```

---

## A note on what was stripped from this public version

This mirror is built from FWI's internal repo by an automated script (`build_public_mirror.py`, kept in our internal-only repo) that removes:

- All farmer names and internal/private pond identifiers
- The mapping file that links anonymised pond IDs back to farmer details
- Any internal-only ops files (token setup notes, etc.)

What remains: the trained model, all analysis code, every experiment we ran, all the result CSVs and reports, and an anonymised version of the raw measurement data (matching the format of FWI's [existing public data release](https://www.fishwelfareinitiative.org/post/data-release-2026)). The model can be retrained end-to-end from what's in this repo.

If you spot anything that you think shouldn't be public, please contact Haven at haven@fishwelfareinitiative.org.

---

## Re-running the analysis

Dependencies (Python 3.10+):
```bash
pip install pandas numpy scikit-learn xgboost lightgbm matplotlib seaborn openpyxl requests
```

To re-train the model and re-export the JSON the web app uses:
```bash
cd model
python3 export_model_for_webapp.py
python3 export_historical_oor.py
```

To re-run any experiment from `analysis/`:
```bash
cd analysis
python3 run_deployment_simulation.py     # YTD deployment-policy comparison
python3 run_experiment_1.py              # seasonal training experiment
python3 run_experiment_1_and_2.py        # seasonal + feature pruning
python3 run_experiments_3_and_4.py       # rank-product ensemble + XGB early stopping
```

All scripts assume `skye-original/` is one directory up; they import `fish_welfare_model` from there for shared utilities.

---

## Attribution

This work builds on a Fish Welfare Initiative volunteer project. Major contributors:

- **Skye Nygaard** — built the underlying model and data pipeline (see `skye-original/` and his [Fishwelfare-Experiments repo](https://github.com/SkyeNygaard/Fishwelfare-Experiments)). The deployed model is his.
- **Daniel Lau, Sara, Tobi** — earlier experiments (different model families) that informed scope.
- **Jennifer Kirsch** (FWI Director of Programs) — substantive critique that shaped the field-test design (see `analysis/reports/Jennifer_Feedback_May_2026.md`).
- **Haven King-Nobles** (FWI ED) — project lead, web app, analysis assembly, blog post.

Weather data: [Open-Meteo](https://open-meteo.com) (free public API).

This repo is licensed under MIT (see `LICENSE`).

---

## Contact

Questions, issues, or feedback → **Haven** at haven@fishwelfareinitiative.org.

Field-test results will be published in a follow-up blog post once the June–August 2026 test concludes.
