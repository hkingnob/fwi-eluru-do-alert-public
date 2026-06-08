Tier 1
Do first — high signal, low effort
Water color (algal density proxy)

already in data
never used as feature

Dark/saturated green = dense phytoplankton = large overnight DO crash. Recorded every visit at 100% fill. Encode as ordinal: transparent < light green < dark green < saturated green. Carry forward between visits. Likely the single most impactful unused feature.

Consecutive low-radiation days

Open-Meteo (derived)
free

Count days where solar radiation falls below a threshold. Multi-day cloud cover progressively depletes the oxygen "bank" without replenishment. A 3-day cloudy spell is far more dangerous than one cloudy day. Simple rolling feature from existing weather data.

Overnight minimum temperature

Open-Meteo
free

Night-time low directly governs overnight metabolic rate while photosynthesis is zero. Warm nights are the killer. Available as daily Tmin from Open-Meteo — more causally relevant than the daytime or instantaneous temperatures currently used.

Feed rate per fish (derived ratio)

already in data
never derived

feed_amount / (stocking_density x pond_area). Overfeeding relative to stock is the real biological driver of organic oxygen demand. Currently feed and density are separate features — the ratio captures the interaction the model has to learn implicitly.

Pond historical OOR frequency

derived from ARA history
free

Fraction of past visits where this pond had DO < 3 mg/L. Some ponds are structurally vulnerable (bad water source, poor circulation, low-lying). Even though single-visit persistence is weak (11% vs 9%), cumulative tendency captures chronic risk. Compute from historical data per pond.

Tier 2
Worth trying — moderate effort, plausible signal
ERA5-Land soil temperature (0-7cm)

Copernicus CDS
free
9km, hourly

Shallow earthen ponds are thermally coupled to the surrounding soil. Soil temperature at 7cm depth may track pond water temperature better than air temperature, especially overnight when air cools faster than the thermal mass of water/soil. Available back to 1950, 5-day lag to real-time.

Cumulative heat (degree-days above threshold)

Open-Meteo (derived)
free

Accumulated thermal stress over 3-7 days. Sustained heat depletes DO more than a single hot day — microbial activity ramps up, oxygen solubility drops, and the system doesn't recover overnight. Sum of (daily Tmax - 30C) for days above 30C over a rolling window.

Per-pond weather via GPS coordinates

Open-Meteo + pond key
free

Query Open-Meteo at each pond's lat/lon instead of a single regional point. Over a 20x29km area, interpolation + elevation correction may yield modest differentiation, especially for rainfall (convective storms are very localized). 204 of 241 ponds have GPS.

Village cluster as categorical feature

in pond key
free

16 villages in the Eluru region. Ponds in the same village likely share water source, canal access, and micro-climate. Village fixed effects could capture unmeasured local factors. Simple one-hot or target encoding.

Reservoir / barrage water levels

CWC / AP WRIMS / data.gov.in
free
daily, may need scraping

Dowleswaram Barrage on the Godavari feeds the West Godavari canal system. Low reservoir = less water inflow to ponds = stagnation = DO problems. CWC publishes daily levels for 123 major reservoirs. The AP Water Resources dept (APWRIMS) has a dashboard. Data access may require manual scraping or PDF parsing.

Diurnal temperature range (Tmax - Tmin)

Open-Meteo (derived)
free

Large diurnal swing = clear sky = strong daytime photosynthesis but sharp overnight cooling. Small swing = overcast or humid = suppressed photosynthesis. Captures a weather "regime" in one number. Trivial to compute.

Dewpoint temperature

Open-Meteo
free

Better moisture proxy than relative humidity, which changes with air temperature throughout the day. High dewpoint = muggy conditions where overnight evaporative cooling is suppressed. Available directly from Open-Meteo.

Tier 3
Creative / speculative — try if tiers 1-2 aren't enough
Agricultural calendar (rice paddy cycle)

ICAR / Ministry of Agriculture
free
seasonal, manual lookup

West Godavari is a major rice district. Post-fertilization runoff brings nutrients into shared water channels, triggering algal blooms in fish ponds. The Kharif (Jun-Oct) and Rabi (Nov-Mar) crop cycles have known planting/fertilization windows. Encode as "weeks since likely fertilization event."

Lunar phase / tidal cycle

astronomical calculation
free

West Godavari is a coastal delta — some ponds may connect to tidal waterways. Spring tides (full/new moon) increase water exchange. Also, full moon provides overnight illumination that theoretically allows minimal algal photosynthesis. Deterministic from date — zero cost to include, easy to test.

Aerosol optical depth (haze/smoke)

Copernicus CAMS
free
~40km, daily

Agricultural burning is common in Andhra Pradesh. Dense haze dims sunlight without appearing as "cloud" in weather models, suppressing photosynthesis. CAMS provides free global AOD data. May explain days where solar radiation models overestimate what actually reaches the pond.

ERA5-Land soil moisture

Copernicus CDS
free
9km, hourly

Saturated soil = higher groundwater table = more seepage into/out of ponds. Dry soil = less water exchange, shallower ponds. Captures hydrological conditions that weather alone doesn't. Available at same resolution as soil temperature.

Nighttime cloud cover (separate from daytime)

Open-Meteo (hourly)
free

Cloudy nights trap heat (greenhouse effect), keeping water warmer and metabolic rates higher. Clear nights allow radiative cooling, which slows respiration. Open-Meteo has hourly cloud cover — average from 7pm to 6am as a distinct feature from daytime cloud cover.

Nighttime hours (photoperiod)

astronomical calculation
free

Duration of darkness = duration of respiration without photosynthesis. At 16.6N latitude, ranges from ~10.5h (June) to ~13h (December). Modest effect but easy to compute from latitude + date. May interact with temperature.

Wind direction (not just speed)

Open-Meteo
free

Sea breeze vs land breeze in a coastal delta region. Onshore winds may bring cooler, more humid air. The research paper found low DO-wind direction correlation, but in a different setting (inland China). Worth testing for a coastal delta.

Evapotranspiration (ET0)

Open-Meteo / ERA5-Land
free

Integrated measure of atmospheric "drying power" combining temperature, wind, humidity, and radiation. High ET0 = conditions that promote pond water loss and concentration of nutrients/organisms. Available from both Open-Meteo and ERA5-Land.

Tier 4
Probably skip — low expected signal or high friction
Satellite imagery (Sentinel-2 spectral bands)

Copernicus
every 5 days, cloud-blocked

Two funded innovation challenges found no signal. DO has no direct optical signature. Ponds are tiny relative to pixel size. Cloud cover blocks many acquisitions. Haven is skeptical. The model comparison shows all satellite models failed (AUC 0.45-0.58, none significant). Don't revisit.

NASA POWER meteorological data

NASA POWER API
50km resolution

Resolution is 5x coarser than Open-Meteo. The entire Eluru region would be a single pixel. No additional variables beyond what Open-Meteo + ERA5-Land already provide. Not worth the effort.

IMD (India Meteorological Department) station data

IMD / data.gov.in
no stable API, sporadic coverage

No public API. Data access is notoriously difficult. Nearest station may be far from the ponds. Open-Meteo already ingests global model data that incorporates IMD observations. Not worth the access friction.

Atmospheric pressure

Open-Meteo
free

Affects O2 solubility but the effect is tiny — a 10 hPa pressure change shifts saturation DO by ~0.1 mg/L. The research paper found correlation < 0.1 with DO. Unlikely to add signal beyond temperature and humidity which already proxy for pressure systems.

