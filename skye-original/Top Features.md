
Feature	Source	Granularity	Available daily?	In SeasonalDO?	Notes
Weather — instantaneous & rolling
Air temperature	Open-Meteo	region	yes	yes	Top-2 feature. Warmer → less O₂ saturation + faster respiration. Use forecast for next-day.
Wind speed	Open-Meteo	region	yes	yes	Key dry-season factor. Low wind → poor surface O₂ transfer overnight.
Relative humidity	Open-Meteo	region	yes	yes	High humidity reduces evaporative cooling.
Cloud cover	Open-Meteo	region	yes	yes	Less sun → less photosynthesis → less O₂ built up during day.
Solar radiation / sunshine hours	Open-Meteo	region	yes	yes	Directly drives photosynthetic O₂ production.
Precipitation	Open-Meteo	region	yes	yes	Rain brings nutrient runoff → algal bloom risk. Also cools water.
Weather code (mode)	Open-Meteo	region	yes	yes	Categorical summary of conditions.
Weather — derived / not yet used
Overnight min temp (Tmin)	Open-Meteo	region	yes	no — new	Night low directly governs overnight O₂ depletion rate. Possibly more predictive than daytime temp.
Diurnal temp range	Open-Meteo (derived)	region	yes	no — new	Large swing = clear skies = strong daytime photosynthesis but fast overnight cooling.
Dewpoint temperature	Open-Meteo	region	yes	no — new	Better humidity proxy — directly measures moisture content vs relative humidity which shifts with temp.
Wind direction	Open-Meteo	region	yes	no — new	Sea breeze vs land breeze may matter near coast. Paper found low correlation though.
Atmospheric pressure	Open-Meteo	region	yes	no — new	Affects O₂ solubility. Low pressure = marginally less dissolved O₂ at saturation.
Cumulative heat (degree-days)	Derived from temp	region	yes	no — new	Multi-day heat accumulation. Sustained heat depletes O₂ more than a single hot day.
Evapotranspiration (ET₀)	Open-Meteo	region	yes	no — new	Proxy for evaporative/energy conditions. High ET₀ = hot, dry, windy — mixed effects on DO.
Farm management — static / slow-changing
Stocking density (per acre)	ARA visit data	farm	at visit	yes	More fish → more respiration. Updated at each visit, carry forward between visits.
Feed amount (kg)	ARA visit data	farm	at visit	yes	More feed → more organic decomposition → more O₂ consumed.
Feed type	ARA visit data	farm	at visit	yes	#1 feature in SeasonalDO. DORB, Mash, Other have different decomposition rates.
Pond area (acres)	ARA enrollment	farm	yes	yes	Larger ponds may buffer DO better. Static per farm.
Pond depth (m)	ARA enrollment	farm	yes	yes	Shallow ponds have more surface-to-volume → more gas exchange but also heat faster.
Species composition	ARA visit data	farm	at visit	no — new	Catla vs Rohu vs mix. Different metabolic rates. Data is available (100% fill).
Biomass (fish weight × density)	ARA visit data	farm	at visit	no — new	Weight available 77% of visits. Haven tested — "adds no signal" (p=0.81). But worth retrying as interaction with weather.
Farm management — not yet used
Feed rate (kg per fish)	Derived: feed / (density × area)	farm	at visit	no — new	Normalizes feed by biomass. Overfeeding relative to stock is the real O₂ driver.
Water color	ARA visit data	farm	at visit	no — new	Proxy for algal density. Dark/saturated green = dense phytoplankton = big overnight O₂ swings. 100% fill.
Pond-level historical DO mean	Derived from ARA history	farm	yes	no — new	Some ponds are chronically low. Encode as a static farm-level feature.
Pond OOR frequency (historical)	Derived from ARA history	farm	yes	no — new	Haven says persistence is weak (11% vs 9%). But cumulative frequency may still help.
Days since last visit / last OOR	Derived from ARA history	farm×day	yes	no — new	Long gap since visit = more uncertainty. Recent OOR = slightly elevated risk.
Temporal / seasonal
Month / week-of-year	Calendar	region	yes	implicit	OOR rates swing 1% (Apr) to 22% (Sep). SeasonalDO handles this via seasonal training windows, but an explicit feature could help within a season.
Day of farming cycle	ARA enrollment	farm×day	if known	no — new	Early cycle (small fish, light feed) vs late cycle (large biomass, heavy feeding). Approximated from stocking events.
Geographic / micro-environment
GPS coordinates (lat/lon)	Pond IDs key	farm	yes	no — new	204/241 Eluru ponds have coordinates. ~20×29 km area. Proximity to reservoirs, elevation differences may matter.
Village cluster	Pond IDs key	farm	yes	no — new	16 villages. Shared water source within village could create correlated DO events.
Pond-specific weather (interpolated)	Open-Meteo + GPS	farm×day	yes	no — new	Open-Meteo accepts lat/lon. Over a 20km area, micro-variations in rain/wind may add signal beyond single-point.
Satellite / remote sensing
Sentinel-2 spectral bands	Copernicus	farm	every 5 days	no	Haven skeptical. Two innovation challenges failed. DO has no direct optical signal. Cloud cover blocks many images. Probably skip.
NDVI / chlorophyll proxy	Sentinel-2 derived	farm	every 5 days	no	Green algae density proxy. In theory correlates with overnight O₂ swing. But earthen ponds are tiny relative to pixel size.
Continuous monitoring (16-farm campaign)
Hourly DO time series	Continuous WQ data	farm×hour	campaign only	no	Not for direct features — but invaluable for understanding DO dynamics: amplitude of daily swing, time of minimum, relationship to weather. Use for feature engineering insights.
Granularity:
region-level
farm-level
farm × day
Daily?
yes
at visit only
no
Status:
in SeasonalDO
new / untested
