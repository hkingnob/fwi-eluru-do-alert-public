# Data Dictionary

This document describes all columns in each dataset.

> **Note:** ARA is a program that has evolved significantly over time. We have added, tested, and discontinued various parameters to refine our data collection process. The data we collect today is much more targeted compared to what we gathered during the program's early stages.
>
> Additionally, different measurement types require different parameters to be filled out in our forms. For example, we only suggest corrective actions when water quality parameters fall outside the acceptable range. As such, the field "Corrective actions requested" will not always be filled in. Similarly, some measurements (e.g., turbidity) are only taken in the morning, as we found that evening measurements show negligible differences.
>
> As a result, you may notice several empty or "NA" columns. These do not represent missing data but rather data that we deliberately chose not to collect.
>
> If you have any questions regarding this data, please feel free to contact us at [fwi.fish/contact](https://fwi.fish/contact).

---

## water_quality.csv

Water quality measurements collected during farm visits. We take most measurements in the morning and evening. For some parameters that don't change significantly throughout the day (e.g. turbidity and ammonia), we only collect the morning measurement.

### Key Data

| Column | Description |
|--------|-------------|
| `Sr. No` | Unique record identifier |
| `Date of data collection` | Date of measurement |
| `Time of data collection` | Exact time of measurement |
| `pond_id` | Anonymized pond identifier (replaces original Pond ID) |
| `region` | Geographic region derived from pond ID: Eluru (WG) or Nellore (NL) |
| `Type` | Time of day: Morning or Evening |

### Measurement Information

| Column | Description |
|--------|-------------|
| `Is follow up` | Whether this is a follow-up measurement. Per the [ARA Commitment](https://fwi.fish/commitment), farmers must maintain water quality in particular ranges. When water quality is outside of range, our team recommends a corrective action and returns to the farm in 1-3 days to follow up; otherwise, measurements are typically taken monthly. This column is "Yes" if this measurement was a follow-up visit. |
| `Is follow up possible` | Whether a follow-up measurement was possible to schedule |
| `Reason follow up not possible` | If follow-up was not possible, the reason why |
| `Group` | Internal grouping used to organize farms, based on either frequency of observed issues and/or participation in certain studies. Values include: Regular ara pond, Focus group 2/3/4, Ara v1 2 weekly, Ara v12 monthly, Ara v12 weekly, Outcome evaluation, and others. |
| `Pond status` | Treatment, Control, or Assessment. Note: "Assessment" farms were treated as control farms. Some controls may not be fully unbiased, so caution is advised when comparing treatment/control outcomes. |
| `Observer` | FWI staff member who recorded the measurement |
| `Equipment` | Measurement equipment used. Note: Using different equipment is one source of measurement variation, as different meters may measure the same water at slightly different values. In our experience, the most accurate measurements are: **DO: Winkler's Method** and **Ammonia: Photometer**. For pH and other parameters, any equipment listed is accurate as methods have remained consistent. |
| `Weather` | Weather conditions during measurement |

### Water Quality Measurements

| Column | Description |
|--------|-------------|
| `DO (mg/L)` | Dissolved oxygen in mg/L |
| `pH` | pH level |
| `Turbidity (in cm)` | Turbidity measured by Secchi disk in cm. Only collected during morning measurements. |
| `Ammonia—TAN (NH3-N) (mg/L)` | Total Ammonia Nitrogen in mg/L. Used until August 2025. See [Ammonia Protocol Change](#ammonia-measurement-protocol-change-august-2025) below. Also note only collected in morning. |
| `Ammonia—TAN (NH3) (mg/L)` | TAN expressed as NH₃ in mg/L. Used during transition period (Aug 2025 onwards) for comparison with new method. |
| `Ammonia—NH3 (mg/L)` | Unionized ammonia (NH₃) in mg/L. New primary metric from August 2025—the directly toxic form. |
| `Temp (in °C)` | Water temperature in Celsius |
| `TDS (ppt)` | Total dissolved solids in parts per thousand |
| `Alkalinity (mg/L)` | Alkalinity in mg/L |
| `Hardness (mg/L)` | Water hardness in mg/L |
| `Water color` | Visual water color description (e.g., Light green, Dark green, Saturated green, Transparent) |
| `Is WQ in range?` | Whether all parameters are within acceptable ranges per the ARA Commitment |
| `Parameters out of range` | List of parameters outside acceptable range, if any |

### Corrective Actions (FWI-Prescribed)

These columns relate to corrective actions that FWI staff recommend to farmers when water quality is out of range.

| Column | Description |
|--------|-------------|
| `Corrective actions requested` | Corrective actions recommended to the farmer |
| `Corrective actions requested (other)` | Other corrective actions requested (free text) |
| `Corrective actions amount requested` | Amount/dosage of corrective action requested |
| `Corrective actions` | Summary of corrective actions |
| `Corrective actions implemented` | Whether the farmer implemented the recommended actions: "Yes, all of them", "Only some", or "No, none of them" |
| `Corrective actions implementation date` | Date farmer implemented the actions |
| `Corrective actions taken` | Specific actions the farmer took |
| `Corrective actions taken (other)` | Other actions taken (free text) |
| `Corrective actions taken (details)` | Additional details about actions taken |
| `Non-prescribed corrective actions taken` | Any additional actions the farmer took beyond what was recommended |
| `Reason not implemented` | If farmer didn't implement actions, the reason why |
| `Water quality improved after corrective actions` | Whether targeted water quality parameters improved to required range after implementation |
| `Corrective action notes` | Additional notes about corrective actions |

### Self-Initiated Corrective Actions

These columns track corrective actions that farmers took on their own initiative, without FWI recommendation.

| Column | Description |
|--------|-------------|
| `Self-initiated corrective actions taken` | Actions the farmer took independently |
| `Self-initiated corrective actions implemented on (exact date)` | Exact date of self-initiated action |
| `Self-initiated corrective actions implemented (date range)` | Approximate date range (e.g., "0-7 days ago") |
| `Self-initiated corrective actions notes` | Notes about self-initiated actions |

### Behavioral Indicators

| Column | Description |
|--------|-------------|
| `Individuals air gulping` | Number of fish observed air gulping. Air gulping is usually a sign of low dissolved oxygen. |
| `Individuals tail splashing` | Number of fish observed tail splashing |

### Fish-Related Information

| Column | Description |
|--------|-------------|
| `Dead fish` | Number of dead fish found by FWI and the farmer since the last visit to the farm |
| `Notes (mortalities)` | Notes about fish mortalities |
| `Feed amount (kg)` | Amount of feed in kg |
| `Stocking density (per acre)` | Fish stocking density per acre |
| `Species` | Fish species in the pond |
| `Weight` | Weight of an individual fish in grams. **Note:** This weight is self-reported by the farmer and not measured by FWI. |
| `Notes` | General notes |
| `Have fish been helped` | Whether fish have been helped through interventions (Yes/No). See our Impact Page (www.fwi.fish/impact) for more on this process. |

### Acceptable Ranges ([ARA Commitment](https://fwi.fish/commitment))

| Parameter | Required Range | Ideal Range |
|-----------|----------------|-------------|
| Dissolved Oxygen (Morning) | 3 – 5 mg/L | 4 – 5 mg/L |
| Dissolved Oxygen (Evening) | 8 – 12 mg/L | 8 – 10 mg/L |
| pH | 6.5 – 8.5 | 7 – 8 |
| Ammonia (TAN) | < 0.5 mg/L (threshold until Aug 2025) | |
| Ammonia (NH₃) | < 0.05 mg/L (threshold from Aug 2025) | |

Note that we have previously included turbidity and temperature as critical parameters, so data from earlier years may include these for the in-range/out-of-range classification. We have since excluded some of these parameters because either they tend to not be as important as we previously thought or we cannot actively control them (in which case we still monitor them).

### Ammonia Measurement Protocol Change (August 2025)

In August 2025, FWI changed how ammonia is measured. For details, see: [Changes in our Ammonia Measurement Protocols](https://www.fishwelfareinitiative.org/post/ammonia-change)

**Why the change?** Unionized ammonia (NH₃) is the form that is directly toxic to fish. The proportion of toxic NH₃ in total ammonia increases with pH and temperature, so measuring only Total Ammonia Nitrogen (TAN) gives an incomplete picture of ammonia toxicity.

**The three ammonia columns:**

| Column | Period | Description |
|--------|--------|-------------|
| `Ammonia—TAN (NH3-N) (mg/L)` | Until Aug 2025 | Total Ammonia Nitrogen. Old measurement method. |
| `Ammonia—NH3 (mg/L)` | Aug 2025 onwards | Unionized ammonia (NH₃). New primary metric—the directly toxic form. |
| `Ammonia—TAN (NH3) (mg/L)` | Aug 2025 onwards | TAN expressed as NH₃. Used during transition for comparison. |

**Note:** During the transition period (Aug 2025 onwards), both old and new metrics may be tracked. Earlier records will only have the TAN column populated.

---

## enrolled_ponds_2026-02-02.csv

Snapshot of ponds enrolled in the ARA program as of February 2, 2026.

**Note:** "Enrolled" means the pond is participating in the ARA program. This is distinct from "active" ponds, which at FWI refers specifically to ponds that currently have fish stocked. An enrolled pond may be between production cycles (empty) but still part of the program.

| Column | Description |
|--------|-------------|
| `pond_id` | Anonymized pond identifier |
| `region` | Geographic region (Eluru or Nellore) |
| `Sr. No` | Record identifier |
| `Date added` | Date pond was added to the program |
| `Enrollment mechanism` | How the farmer was recruited to the program (e.g., "Organic" for organic outreach, "PwC" for PwC partnership referrals) |
| `Status` | Treatment or Control designation |
| `Current lifecycle stage` | Current production stage (Grow-out, Breed-out, Rearing, Nursery) |
| `Added by` | FWI staff member who added the pond |
| `Culture change` | Whether the farmer changed their culture type (e.g., "Grow out to breed out") |
| `Existing practices` | Practices the farmer was already doing before joining ARA |
| `Notes (existing practices)` | Additional notes on existing practices |
| `Fertilizers used` | Types of fertilizers used (e.g., DAP, Urea, Cow manure) |
| `Property area in acres` | Total property area in acres |
| `Pond area in acres` | Pond surface area in acres |
| `Depth in meters` | Pond depth in meters |
| `Measurements` | Number of water quality measurements taken at this pond |
| `Feed type` | Type of feed used (e.g., DORB, Mash, Pelleted feed) |
| `Feed source` | Where feed is sourced from (Local market, National supplier, etc.) |
| `Feed brand or name` | Brand name of feed used |

---

## stocking_harvest.csv

Stocking and harvest events for tracked ponds.

### Key Data

| Column | Description |
|--------|-------------|
| `pond_id` | Anonymized pond identifier |
| `region` | Geographic region (Eluru or Nellore) |
| `Sr. No` | Record identifier |
| `Type` | Event type: Stocking, Harvest, Partial stocking, Partial harvest |
| `Event date` | Date of the stocking or harvest event |
| `Initial entry` | Whether this is the first stocking/harvest record for this pond (Yes/No) |
| `Logged by` | FWI staff member who logged the event |
| `Created at` | Timestamp when the record was created |

### Lifecycle Information

| Column | Description |
|--------|-------------|
| `Lifecycle` | Production stage: Breed-out, Grow-out, Rearing, Nursery |
| `Lifecycle is updated accordingly on the master doc` | Internal tracking field |

### Species and Weight

| Column | Description |
|--------|-------------|
| `Species` | Fish species involved in the event |
| `Species ratio` | Ratio of different species (e.g., "9:1" for 90% one species, 10% another) |
| `Reported target weight in grams` | Target harvest weight in grams |
| `Average fish weight (in grams)` | Average weight of fish at event time |
| `Average weight of Catla (Catla catla) (in grams)` | Average weight of Catla species |
| `Average weight of Rohu (Labeo rohita) (in grams)` | Average weight of Rohu species |
| `Average weight of Mrigal (Cirrhinus cirrhosus) (in grams)` | Average weight of Mrigal species |
| `Average weight of Grass Carp (Ctenopharyngodon idella) (in grams)` | Average weight of Grass Carp species |
| `Average weight of Common Carp (Cyprinus carpio) (in grams)` | Average weight of Common Carp species |
| `Average weight of Roopchand (in grams)` | Average weight of Roopchand species |
| `Average weight of Whiteleg Shrimp (Litopenaeus vannamei) (in grams)` | Average weight of shrimp |
| `Average weight of Pangasius (in grams)` | Average weight of Pangasius species |

### Stocking Density

| Column | Description |
|--------|-------------|
| `Communicated stock density limit` | Stocking density limit communicated to farmer by FWI |
| `Current fish stocking density per acre` | Current fish stocking density |
| `Current shrimp stocking density per acre` | Current shrimp stocking density, for the few farms that have shrimp. We used to have more farms that did polyculture but now have very few. |
| `Intended fish stocking density (per acre)` | Planned fish stocking density per acre |
| `Intended fish stocking density (entire pond)` | Planned total fish count for entire pond |
| `Actual fish stocking density (per acre)` | Actual fish stocking density achieved |
| `Fish stocking density (entire pond)` | Actual total fish count in entire pond |
| `Intended shrimp stocking density (per acre)` | Planned shrimp stocking density per acre |
| `Intended shrimp stocking density (entire pond)` | Planned total shrimp count for entire pond |
| `Actual shrimp stocking density (per acre)` | Actual shrimp stocking density achieved |
| `Actual shrimp stocking density (entire pond)` | Actual total shrimp count in entire pond |

### Harvest Information

| Column | Description |
|--------|-------------|
| `Harvest reason` | Reason for harvest (Planned harvest, Planned sale, Disease outbreak) |
| `Fish harvested (total, in kg)` | Total fish harvested in kilograms |
| `Shrimp harvested (total, in kg)` | Total shrimp harvested in kilograms |
| `Fish left in the pond (total, in individuals)` | Number of fish remaining after partial harvest |
| `Shrimp left in the pond (total, in individuals)` | Number of shrimp remaining after partial harvest |

### Pond Preparation

| Column | Description |
|--------|-------------|
| `Did the farmer do pond preparation?` | Whether farmer prepared the pond before stocking (Yes/No) |
| `Explain what the farmer did for pond preparation` | Description of pond preparation activities |
| `Is the farmer planning to do pond preparation?` | Whether farmer plans to prepare pond (Yes/No) |
| `Explain what the farmer is planning to do for pond preparation` | Description of planned preparation |

### Impact Metrics

| Column | Description |
|--------|-------------|
| `Fish purchases diverted` | Number of fish not purchased due to stocking density reduction. **Note:** This is based on farmer self-reports, which is why these figures may differ from the data sheets linked on our [impact page](https://www.fwi.fish/impact). |
| `Shrimp purchases diverted` | Number of shrimp not purchased due to stocking density reduction. Based on farmer self-reports. |

### Notes

| Column | Description |
|--------|-------------|
| `Notes` | Additional notes about the stocking or harvest event |

### Data Verification

| Column | Description |
|--------|-------------|
| `Data verification method` | How the data was verified (Verbal communication, Picture of receipt, etc.) |
| `Data verified by` | Staff member who verified the data |

### Lifecycle Stages

- **Breed-out**: Fingerling/juvenile production phase
- **Grow-out**: Main growth phase to market size
- **Rearing**: Early rearing of fry/fingerlings
- **Nursery**: Initial nursing of fry

---

## dropouts.csv

Ponds that have left the ARA program.

| Column | Description |
|--------|-------------|
| `pond_id` | Anonymized pond identifier |
| `region` | Geographic region (Eluru or Nellore) |
| `Sr. No` | Record identifier |
| `Date of drop out` | Date the pond left the program |
| `Added by` | FWI staff member who recorded the dropout |
| `Tenancy type` | Whether the pond is Owned or Leased by the farmer |
| `Pond measurements` | Number of water quality measurements taken before dropout |
| `Reason` | Reason for leaving the program |
| `Further details on reason` | Additional context about the dropout reason |

### Dropout Reason Categories

| Category | Description |
|----------|-------------|
| Changed to farming crustaceans (e.g. shrimp) | Farmer switched to shrimp or other crustacean farming |
| Changed to farming another species of finfish | Farmer switched to different fish species not covered by ARA |
| Stopped farming fish | Farmer stopped aquaculture entirely |
| Other (mention below) | Other reasons (details in "Further details on reason" column) |

---

## Cross-Dataset Consistency

The `pond_id` column is consistent across all datasets. The same anonymized ID refers to the same physical pond in water_quality.csv, enrolled_ponds.csv, stocking_harvest.csv, and dropouts.csv.

The `region` column is derived from the original pond ID prefix and indicates the geographic area:
- **Eluru (WG)**: Coastal district in Andhra Pradesh (formerly part of West Godavari district, before the 2022 redistricting; internal pond IDs retain the "WG" prefix from the original designation)
- **Nellore (NL)**: Coastal district in Andhra Pradesh

---

## Data Collection Notes

- **Morning vs Evening**: Most water quality parameters are collected twice daily. Some parameters (like turbidity) are only collected in the morning as evening measurements showed negligible differences.

- **Follow-up measurements**: When water quality is out of range, FWI returns within 1-3 days to check if corrective actions were effective. Regular measurements occur approximately monthly.

- **Equipment variation**: Different measurement equipment may produce slightly different readings. The Equipment column indicates which tools were used for each measurement.

- **Self-reported data**: Fish weight is self-reported by farmers rather than measured by FWI staff.
