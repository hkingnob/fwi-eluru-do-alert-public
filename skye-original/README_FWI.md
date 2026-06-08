# `skye-original/`

This is a snapshot of [github.com/SkyeNygaard/Fishwelfare-Experiments](https://github.com/SkyeNygaard/Fishwelfare-Experiments) as of late April 2026, embedded here as a self-contained subdirectory for reference and attribution.

## Why it's here

- The trained model in `model/` and the analysis scripts in `analysis/` build directly on Skye's pipeline (`fish_welfare_model.py`).
- Skye's anti-leakage documentation (`Data Leakage and Overfitting Prevention.md`) is the methodological foundation.
- His public anonymized training data (`public_ara_data/`) is what every model in this repo trained on.
- His feature catalog (`Feature Table.png`, `Top Features.md`) and Future Experiments doc (`Future Experiments.md`) shaped what experiments came next.

## Notable files

- `fish_welfare_model.py` — the v3 training pipeline. Imported by every script in `analysis/`.
- `public_ara_data/` — anonymized water-quality, enrolled-ponds, stocking-harvest, and dropouts CSVs covering 2021 through January 2026.
- `2026 ARA WQ WG Morning Non-Follow-up.csv` — anonymized Q1 2026 hold-out used for model evaluation.
- `weather_cache_eluru.csv` — Open-Meteo weather data, 2024-01-01 onward, cached locally for fast re-runs.
- `Data Leakage and Overfitting Prevention.md` — the methodology doc you should read before changing any feature engineering.
- `Future Experiments.md` — Skye's prioritized list of next experiments (most of which are now implemented in `analysis/`).
- `Real-World Impact.md` — Skye's original operational framing.
- `results_summary.md` — Skye's v3 model results.

## Possible improvement: convert to a git submodule

Right now this is a plain copy. If you want changes Skye makes upstream to flow in automatically, you could replace this directory with a git submodule:

```bash
git rm -r skye-original
git submodule add https://github.com/SkyeNygaard/Fishwelfare-Experiments.git skye-original
git commit -m "Convert skye-original/ to a submodule"
```

Note: doing that will require collaborators to run `git submodule update --init --recursive` after cloning. For a private repo shared with one collaborator (Jennifer), the plain-copy approach is probably simpler.

## Attribution

All credit for the pipeline, data preparation, and v3 model goes to Skye Nygaard. Issues with this work should be raised against the upstream repo where appropriate.
