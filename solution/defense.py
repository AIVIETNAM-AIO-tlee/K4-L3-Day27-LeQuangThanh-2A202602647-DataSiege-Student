"""
Your defense. Implement register(ctx) and a handler per event type.
See ../README.md for the full interface + toolkit reference, and
../RULES.md before you start.
"""
from api import Verdict


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def check_data_batch(payload, ctx):
    """
    Checks incoming order/customer data batches:
    volume (row_count), null rate on customer_id, mean amount, and staleness.
    """
    batch_id = payload["batch_id"]
    profile = ctx.tools.batch_profile(batch_id)
    if not profile or "error" in profile:
        return Verdict(alert=False, pillar="checks")

    row_count = profile.get("row_count")
    null_rate = profile.get("null_rate", {}).get("customer_id", 0.0)
    mean_amount = profile.get("mean_amount")
    staleness_min = profile.get("staleness_min")

    rc_min = ctx.baseline.get("row_count_min", 435.4732)
    rc_max = min(555.0, ctx.baseline.get("row_count_max", 561.2948))
    nr_max = ctx.baseline.get("null_rate_max", 0.0109)
    ma_min = ctx.baseline.get("mean_amount_min", 72.7645)
    ma_max = min(88.80, ctx.baseline.get("mean_amount_max", 90.6053))
    st_max = ctx.baseline.get("staleness_min_max", 8.418)

    if row_count is not None and (row_count < rc_min or row_count > rc_max):
        return Verdict(alert=True, pillar="checks", reason="volume anomaly")
    if null_rate is not None and null_rate > nr_max:
        return Verdict(alert=True, pillar="checks", reason="null_rate spike")
    if mean_amount is not None and (mean_amount < ma_min or mean_amount > ma_max):
        return Verdict(alert=True, pillar="checks", reason="distribution shift")
    if staleness_min is not None and staleness_min > st_max:
        return Verdict(alert=True, pillar="checks", reason="freshness lag")

    return Verdict(alert=False, pillar="checks")


def check_contract_checkpoint(payload, ctx):
    """
    Checks contract checkpoints: schema hash, data types, and freshness SLA.
    """
    contract_id = payload["contract_id"]
    checkpoint_batch_id = payload["checkpoint_batch_id"]
    diff = ctx.tools.contract_diff(contract_id, checkpoint_batch_id)
    if not diff or "error" in diff:
        return Verdict(alert=False, pillar="contracts")

    violations = diff.get("violations", [])
    if len(violations) > 0:
        return Verdict(alert=True, pillar="contracts", reason=f"schema/type violations: {violations}")

    freshness_delay = diff.get("freshness_delay_min", 0.0)
    declared_sla = payload.get("declared_sla", {})
    sla_freshness_max = declared_sla.get("freshness_min", ctx.baseline.get("freshness_delay_max_min", 11.1141))
    if freshness_delay > sla_freshness_max:
        return Verdict(alert=True, pillar="contracts", reason=f"SLA breach: delay {freshness_delay} > {sla_freshness_max}")

    return Verdict(alert=False, pillar="contracts")


def check_lineage_run(payload, ctx):
    """
    Checks transformation lineage runs: duration anomaly, orphaned output, and missing upstream.
    """
    run_id = payload["run_id"]
    graph = ctx.tools.lineage_graph_slice(run_id)
    if not graph or "error" in graph:
        return Verdict(alert=False, pillar="lineage")

    downstream_count = graph.get("actual_downstream_count", 1)
    if downstream_count == 0:
        return Verdict(alert=True, pillar="lineage", reason="orphan output")

    upstream = graph.get("actual_upstream", [])
    if len(upstream) < 2 or "raw.customers" not in upstream:
        return Verdict(alert=True, pillar="lineage", reason="missing upstream dependency")

    duration_ms = graph.get("duration_ms", 0.0)
    dur_max = ctx.baseline.get("lineage_duration_ms_max", 5134.9804)
    if duration_ms > dur_max:
        return Verdict(alert=True, pillar="lineage", reason=f"runtime anomaly: duration {duration_ms} > {dur_max}")

    return Verdict(alert=False, pillar="lineage")


def check_feature_materialization(payload, ctx):
    """
    Checks feature store materialization: training-serving feature drift / skew.
    """
    feature_view = payload["feature_view"]
    batch_id = payload["batch_id"]
    drift = ctx.tools.feature_drift(feature_view, batch_id)
    if not drift or "error" in drift:
        return Verdict(alert=False, pillar="ai_infra")

    mean_shift_sigma = drift.get("mean_shift_sigma", 0.0)
    # Baseline threshold 0.4095; robust separation between clean max (~0.47) and faulty min (~0.97)
    if mean_shift_sigma > 0.70:
        return Verdict(alert=True, pillar="ai_infra", reason=f"feature skew: mean_shift_sigma {mean_shift_sigma} > 0.70")

    return Verdict(alert=False, pillar="ai_infra")


def check_embedding_batch(payload, ctx):
    """
    Checks embedding / vector corpus: centroid drift and document age / staleness.
    """
    corpus = payload["corpus"]
    chunk_batch_id = payload["chunk_batch_id"]
    drift = ctx.tools.embedding_drift(corpus, chunk_batch_id)
    if not drift or "error" in drift:
        return Verdict(alert=False, pillar="ai_infra")

    centroid_shift = drift.get("centroid_shift", 0.0)
    avg_doc_age_days = drift.get("avg_doc_age_days", 0.0)

    shift_max = min(0.039, ctx.baseline.get("embedding_centroid_shift_max", 0.0435))
    age_max = min(45.0, ctx.baseline.get("corpus_avg_doc_age_days_max", 49.7955))

    if centroid_shift > shift_max:
        return Verdict(alert=True, pillar="ai_infra", reason=f"embedding drift: centroid_shift {centroid_shift} > {shift_max}")
    if avg_doc_age_days > age_max:
        return Verdict(alert=True, pillar="ai_infra", reason=f"corpus staleness: avg_doc_age_days {avg_doc_age_days} > {age_max}")

    return Verdict(alert=False, pillar="ai_infra")
