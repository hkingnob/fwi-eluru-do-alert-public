# `data/`

## Contents

- **`2026_measurements_YTD_anonymized.csv`** — anonymised 2026 year-to-date ARA Eluru measurements. 513 morning non-follow-up visits across 79 dates from 2026-01-02 to 2026-05-04. Matches the format of FWI's [existing public data release](https://www.fishwelfareinitiative.org/post/data-release-2026).

## Anonymisation

The raw file in our internal repo contains farmer names and internal pond IDs. For this public version:

- The `Farmer` column has been removed.
- Internal pond IDs (e.g. `WG-MRR1`) have been replaced with opaque public IDs (e.g. `pond_283dc502`) using the same mapping FWI applies to its publicly-released datasets. For 5 ponds not yet in the public-ID key, stable hashed IDs were generated.

The `Observer` column has been retained because it appears in FWI's existing public data release and contains only FWI staff first names.

If you need the underlying anonymisation mapping (e.g. to merge this data with FWI's other published datasets), contact Haven at haven@fishwelfareinitiative.org.

## Where the historical training data lives

Training data (2024–2025 ARA Eluru visits) is in `../skye-original/public_ara_data/`. That dataset is in the same anonymised format as the file above. The Q1 2026 hold-out used during model evaluation is at `../skye-original/2026 ARA WQ WG Morning Non-Follow-up.csv`, also anonymised.
