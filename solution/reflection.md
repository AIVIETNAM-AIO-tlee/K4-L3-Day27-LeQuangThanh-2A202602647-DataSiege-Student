# Reflection (≤1 page)

### Which fault types were hardest to catch, and why?

1. **Subtle Distribution Shifts & Volume Variations in `data_batch`:**
   In the private phase, subtle faults like low-magnitude volume spikes/drops (e.g., row count 469–519 vs. clean mean ~500) and small amount shifts (e.g., mean amount ~85.7 vs. clean mean ~82.8) sit comfortably inside the $\pm 3\sigma$ bounds of normal pipeline operations. Because an isolated batch measurement does not provide enough statistical evidence to distinguish low-magnitude anomalies from natural stochastic jitter, setting thresholds aggressively to catch them incurs a heavy False Positive Rate (FPR) penalty. Given the scoring formula's $-30\%$ penalty on FPR, avoiding false alarms on normal variance was essential.

2. **Subtle Drift and Staleness in `embedding_batch`:**
   Subtle embedding centroid drift ($\sim 0.029 - 0.031$) and document age staleness ($\sim 31 - 37$ days) overlap directly with the clean stream distribution (where clean centroid shifts reach up to $0.0388$ and document age reaches $41$ days). A single snapshot check cannot distinguish subtle drift from normal semantic variability without sequential history.

3. **Subtle Runtime Jitter in `lineage_run`:**
   While structural lineage faults (`missing_upstream` and `orphan_output`) are cleanly and deterministically detectable ($100\%$ precision and recall), subtle duration anomalies ($\sim 4480 - 4740$ ms) blend into the upper tail of normal transformation executions (which peak around $4805$ ms). Maintaining the calibrated $3\sigma$ bound ($5134.98$ ms) was necessary to prevent false alerts.

---

### What would you change about your cost/coverage tradeoff, if you had another pass?

1. **Windowed / Cumulative Drift Detection via `ctx.state`:**
   Rather than evaluating each event in total isolation, I would leverage `ctx.state` to maintain rolling statistics (such as an Exponentially Weighted Moving Average - EWMA, or a CUSUM change-detection filter). Persistent low-magnitude shifts across 3–5 consecutive batches would cross cumulative confidence intervals, allowing the detector to catch subtle faults without triggering false alarms on transient spikes.

2. **Adaptive Tool Invocation & Budget Management:**
   In constrained-budget environments (like the Public phase's 220-credit limit vs. 240-credit full single-pass requirement), calling every 2.0-credit tool on every event produces a cost overage penalty. If given another pass, I would implement adaptive metering:
   - For high-confidence, low-frequency failure modes, sample every $k$-th batch when budget headroom is tight.
   - Reallocate credits dynamically based on `ctx.tools.budget_remaining()` to guarantee zero overage penalty while preserving maximum detection coverage on high-probability fault pillars.
