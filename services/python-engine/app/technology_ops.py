from __future__ import annotations

from typing import Any


def technology_indicator_rows(
    term_year_rows: list[dict[str, Any]],
    graph_metric_rows: list[dict[str, Any]] | None = None,
    current_year: int | None = None,
) -> list[dict[str, Any]]:
    from collections import defaultdict

    current_year = current_year or 2024
    graph_lookup: dict[str, dict[str, float]] = {}
    if graph_metric_rows:
        for row in graph_metric_rows:
            graph_lookup[str(row.get("term") or "")] = {
                "betweenness": float(row.get("betweenness", 0.0) or 0.0),
                "pagerank": float(row.get("pagerank", 0.0) or 0.0),
                "closeness": float(row.get("closeness", 0.0) or 0.0),
            }

    term_data: dict[str, dict[str, Any]] = defaultdict(lambda: {"years": {}, "total_tf": 0, "total_df": 0})
    for row in term_year_rows:
        term = str(row.get("term") or "")
        year = int(row["year"]) if row.get("year") is not None else None
        tf = int(row.get("tf_in_year", 0) or 0)
        df = int(row.get("df_in_year", 0) or 0)
        if not term or year is None:
            continue
        td = term_data[term]
        td["years"][year] = {"tf": tf, "df": df}
        td["total_tf"] += tf
        td["total_df"] += df

    rows = []
    recent_years = {current_year, current_year - 1, current_year - 2}
    baseline_years = {y for y in range(current_year - 7, current_year - 2)}

    for term, td in term_data.items():
        years = td["years"]
        first_year = min(years) if years else None
        last_year = max(years) if years else None
        recent_tf = sum(years[y]["tf"] for y in years if y in recent_years)
        baseline_tf = sum(years[y]["tf"] for y in years if y in baseline_years)
        growth_rate = (recent_tf + 1) / (baseline_tf + 1)
        age_span = (last_year - first_year + 1) if first_year and last_year else 1

        # novelty: high when recent, low baseline, high recent share
        recency_score = 1.0 if first_year and first_year >= current_year - 3 else 0.3
        baseline_penalty = 1.0 / (1.0 + baseline_tf / max(1, td["total_tf"]))
        recent_share = recent_tf / max(1, td["total_tf"])
        novelty_score = min(1.0, recency_score * baseline_penalty * (1.0 + recent_share))

        # disruption: high growth + high betweenness bridge
        gm = graph_lookup.get(term, {})
        bridge_score = min(1.0, gm.get("betweenness", 0.0) * 5.0 + gm.get("pagerank", 0.0) * 2.0)
        disruption_score = min(1.0, (growth_rate / (1.0 + growth_rate)) * 0.7 + bridge_score * 0.3)

        # maturity: old, stable, high frequency
        maturity_score = min(1.0, (age_span / 10.0) * 0.4 + (baseline_tf / max(1, td["total_tf"])) * 0.6)

        rows.append(
            {
                "term": term,
                "first_year": first_year,
                "last_year": last_year,
                "total_tf": td["total_tf"],
                "total_df": td["total_df"],
                "recent_tf": recent_tf,
                "baseline_tf": baseline_tf,
                "growth_rate": round(growth_rate, 4),
                "novelty_score": round(novelty_score, 4),
                "disruption_score": round(disruption_score, 4),
                "maturity_score": round(maturity_score, 4),
                "betweenness": round(gm.get("betweenness", 0.0), 6),
                "pagerank": round(gm.get("pagerank", 0.0), 6),
            }
        )

    rows.sort(key=lambda r: (-r["novelty_score"], -r["disruption_score"], r["term"]))
    return rows


def technology_classification_rows(
    indicator_rows: list[dict[str, Any]],
    thresholds: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    t = thresholds or {}
    emerging_n = float(t.get("emerging_novelty", 0.65))
    emerging_g = float(t.get("emerging_growth", 1.5))
    disruptive_d = float(t.get("disruptive_disruption", 0.65))
    core_m = float(t.get("core_maturity", 0.65))
    decline_g = float(t.get("declining_growth", 0.75))
    decline_m = float(t.get("declining_maturity", 0.4))

    rows = []
    for ind in indicator_rows:
        cls = "monitor"
        reason = "指标处于中间区间，建议持续观察。"
        confidence = 0.5

        if ind["novelty_score"] >= emerging_n and ind["growth_rate"] >= emerging_g:
            cls = "emerging"
            reason = f"新颖度 {ind['novelty_score']:.2f} >= {emerging_n} 且增长率 {ind['growth_rate']:.2f} >= {emerging_g}。"
            confidence = min(1.0, (ind["novelty_score"] / emerging_n) * 0.5 + (ind["growth_rate"] / emerging_g) * 0.5)
        elif ind["disruption_score"] >= disruptive_d:
            cls = "disruptive"
            reason = f"颠覆度 {ind['disruption_score']:.2f} >= {disruptive_d}。"
            confidence = min(1.0, ind["disruption_score"] / disruptive_d)
        elif ind["maturity_score"] >= core_m:
            cls = "core"
            reason = f"成熟度 {ind['maturity_score']:.2f} >= {core_m}。"
            confidence = min(1.0, ind["maturity_score"] / core_m)
        elif ind["growth_rate"] <= decline_g and ind["maturity_score"] >= decline_m:
            cls = "declining"
            reason = f"增长率 {ind['growth_rate']:.2f} <= {decline_g} 且成熟度 {ind['maturity_score']:.2f} >= {decline_m}。"
            confidence = min(1.0, (decline_g / max(ind["growth_rate"], 0.01)) * 0.5 + (ind["maturity_score"] / decline_m) * 0.5)

        rows.append(
            {
                "term": ind["term"],
                "technology_class": cls,
                "confidence": round(confidence, 4),
                "primary_reason": reason,
                "novelty_score": ind["novelty_score"],
                "disruption_score": ind["disruption_score"],
                "maturity_score": ind["maturity_score"],
                "growth_rate": ind["growth_rate"],
            }
        )
    return rows
