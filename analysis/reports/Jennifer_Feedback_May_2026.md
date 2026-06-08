# Feedback on the Weather-Based Prediction Model

**Author:** Jennifer Kirsch, Director of Programs, Fish Welfare Initiative
**Date:** May 2026
**Context:** Reviewed shortly after the model and accompanying web app were shared internally. The points raised here directly shaped the field-test design currently being implemented (see [Calibration_Updates_June_2026.md](Calibration_Updates_June_2026.md) for what changed in response).

---

## Hesitations

### Model limitations

It seems surprising to me that a volunteer has figured something useful out by just using weather data. Possible but in my opinion unlikely. I expect that the lift/accuracy will decrease as we test it. I don't think that makes it less exciting but I do think that should determine how many resources we put into this.

To give you one example of things that make me concerned the model won't be very predictive based on weather alone: it predicted only one alert day for April while the true OOR rate was comparatively high (32 out of 332 initial measurements). This may suggest that weather isn't the only driving factor for OOR (which makes sense) and thus the model may be less useful in some months where this is the case.

### True lift

The 1.7× lift doesn't seem correctly interpreted to me. I still can't fully pin it down but there's something about the fact that we compare the OOR rate of what's currently happening on normal days vs. alert days — I feel that neglects the fact that we still send staff out on alert days right now and it's not necessarily clear that more measurements that day would mean more OOR.

The capacity-neutral reallocation policy (same total visits, weighted toward High days) caught only ~3 extra OOR events over the entire 4-month YTD period on 513 total visits. That's the ceiling from optimal reweighting. Adding 1–2 visits on a handful of Alert days would be a fraction of that. Adding one visit on an Alert day gives you an ~11.6% chance of finding OOR, vs a ~6.7% chance on a Normal day. The incremental value of that extra visit is roughly 5 percentage points — about 1-in-20 chance of catching an additional OOR event. The 1.7× framing makes it sound more significant than it is in absolute terms.

### Impact

While it could be the case that this model actually improves detection by 50%, given that all of these are DO instances, I doubt that this amounts to a considerable number of fishes helped. The majority of our fishes-helped instances (and all of them in 2025) stem from cases where DO *plus* another parameter were OOR. While there is a higher chance that pH or ammonia are OOR when DO is OOR, I would expect that only a fraction of these extra OOR measurements will be considered for our impact counting.

### Scale

I would tentatively say that this is not a highly scalable model, even if the prediction works out — unless we figure out some creative staff models. For example, extra on-call staff to take more measurements on alert days. Due to the measurement time limitation, we can't just have our staff take more measurements in a given day (apart from maybe 1–3 extra by being extra fast and using the full 2-hour window). However, there are a few limitations to alternate staff models:

- Geographical distribution of farms, where travel between villages can take 20–30 minutes — time we would lose during the measurement window.
- Complexity of measurements: DO samples require fixing. We couldn't just have a farmer or someone else take a sample without having the fixing reagents on-hand.

### Question

How does the model deal with changes over time? I understand it to be trained on pre-2026 data. Would we ever retrain it, or would predictions in e.g. 2029 still be based on pre-2026 data?

---

## Testing

Given my hesitations on the true lift (disagreement welcome!), I actually don't see much value in shadow-testing. Sure, it'll tell us if the model accuracy holds over seasons, but in my opinion it doesn't really give us further information on the true programmatic improvement.

**Instead of the shadow-testing, I would recommend we just implement this for some time with strong reevaluation points.** Implementation here would mean that we run the model and, on "alert" days, we deploy staff to 1–3 more ponds than on normal days. We then check whether these extra visits are OOR and compare that to the baseline OOR rate (our control, which we already have). We would also take follow-ups for any OOR, so we'd have insights into the "fishes helped" rate for these extra visits too.

I believe this implementation-testing is more useful because it tells us whether the additional measurements on "alert" days actually translate to OOR and, ultimately, impact. Despite my hesitations above, I think it's worth giving this a fair shot by testing it in-field.

Given that we are still completing data collection for the OE in May, I'd schedule the implementation-testing for **June through August** with **3-weekly reevaluation points**.
