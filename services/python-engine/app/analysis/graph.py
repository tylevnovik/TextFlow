from __future__ import annotations

from typing import Any

import networkx as nx


def build_term_graph_tables(
    cooccurrence_rows: list[dict[str, Any]],
    min_edge_weight: int = 1,
    max_edges: int = 5000,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    g = nx.Graph()
    for row in cooccurrence_rows:
        weight = int(row.get("cooccurrence_count", 0) or 0)
        if weight < min_edge_weight:
            continue
        a = str(row.get("term_a") or "")
        b = str(row.get("term_b") or "")
        if not a or not b or a == b:
            continue
        if g.has_edge(a, b):
            g[a][b]["weight"] += weight
        else:
            g.add_edge(a, b, weight=weight)

    edges = [
        {"term_a": u, "term_b": v, "weight": int(d["weight"])}
        for u, v, d in g.edges(data=True)
    ]
    edges.sort(key=lambda e: -e["weight"])
    edges = edges[:max_edges]

    node_set = set()
    for e in edges:
        node_set.add(e["term_a"])
        node_set.add(e["term_b"])

    nodes = [{"term": term, "degree": int(g.degree(term))} for term in sorted(node_set)]
    return nodes, edges


def graph_metric_rows(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not nodes or not edges:
        return []
    g = nx.Graph()
    for edge in edges:
        g.add_edge(edge["term_a"], edge["term_b"], weight=edge.get("weight", 1))

    try:
        pagerank = nx.pagerank(g, weight="weight")
    except Exception:
        pagerank = {}

    try:
        betweenness = nx.betweenness_centrality(g, weight="weight")
    except Exception:
        betweenness = {}

    try:
        closeness = nx.closeness_centrality(g)
    except Exception:
        closeness = {}

    rows = []
    for node in nodes:
        term = node["term"]
        rows.append(
            {
                "term": term,
                "degree": int(g.degree(term)) if term in g else 0,
                "pagerank": round(float(pagerank.get(term, 0.0)), 6),
                "betweenness": round(float(betweenness.get(term, 0.0)), 6),
                "closeness": round(float(closeness.get(term, 0.0)), 6),
            }
        )
    return rows


def community_rows(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    method: str = "greedy_modularity",
) -> list[dict[str, Any]]:
    if not nodes or not edges:
        return []
    g = nx.Graph()
    for edge in edges:
        g.add_edge(edge["term_a"], edge["term_b"], weight=edge.get("weight", 1))

    if method == "greedy_modularity":
        try:
            communities = nx.community.greedy_modularity_communities(g, weight="weight")
        except Exception:
            communities = []
    elif method == "label_propagation":
        try:
            communities = nx.community.label_propagation_communities(g)
        except Exception:
            communities = []
    else:
        communities = []

    rows = []
    for community_id, community in enumerate(communities):
        for term in community:
            rows.append({"term": term, "community_id": community_id, "community_size": len(community)})
    return rows


def main_path_rows(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    mode: str = "directed_citation_or_weighted_backbone",
) -> list[dict[str, Any]]:
    if not nodes or not edges:
        return []

    g = nx.DiGraph() if mode == "directed_citation_or_weighted_backbone" else nx.Graph()
    for edge in edges:
        g.add_edge(edge["term_a"], edge["term_b"], weight=edge.get("weight", 1))

    if mode == "directed_citation_or_weighted_backbone":
        try:
            if nx.is_directed_acyclic_graph(g):
                # longest path in DAG by weight
                all_paths = []
                for source in g.nodes():
                    for target in g.nodes():
                        if source != target and nx.has_path(g, source, target):
                            path = nx.dag_longest_path(g, weight="weight")
                            if path not in all_paths:
                                all_paths.append(path)
                if all_paths:
                    longest = max(all_paths, key=len)
                    return [
                        {
                            "term": term,
                            "position": index,
                            "path_length": len(longest),
                            "main_path_mode": "directed_longest_path",
                        }
                        for index, term in enumerate(longest)
                    ]
        except Exception:
            pass
        # fallback: weighted PageRank backbone
        try:
            pr = nx.pagerank(g, weight="weight")
            sorted_nodes = sorted(pr.items(), key=lambda x: -x[1])
            return [
                {
                    "term": term,
                    "position": index,
                    "pagerank": round(score, 6),
                    "path_length": len(sorted_nodes),
                    "main_path_mode": "weighted_backbone",
                }
                for index, (term, score) in enumerate(sorted_nodes)
            ]
        except Exception:
            pass
    else:
        # cooccurrence backbone: maximum spanning tree
        try:
            mst = nx.maximum_spanning_tree(g, weight="weight")
            sorted_edges = sorted(mst.edges(data=True), key=lambda e: -e[2].get("weight", 1))
            seen = set()
            rows = []
            for u, v, d in sorted_edges:
                for term in (u, v):
                    if term not in seen:
                        seen.add(term)
                        rows.append(
                            {
                                "term": term,
                                "position": len(rows),
                                "edge_weight": d.get("weight", 1),
                                "path_length": len(mst.edges()),
                                "main_path_mode": "cooccurrence_backbone",
                            }
                        )
            return rows
        except Exception:
            pass

    return []


def link_prediction_rows(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    top_n: int = 200,
) -> list[dict[str, Any]]:
    if not nodes or not edges:
        return []
    g = nx.Graph()
    for edge in edges:
        g.add_edge(edge["term_a"], edge["term_b"], weight=edge.get("weight", 1))

    try:
        preds = nx.jaccard_coefficient(g)
        rows = [
            {"term_a": u, "term_b": v, "score": round(float(p), 6)}
            for u, v, p in preds
        ]
        rows.sort(key=lambda r: -r["score"])
        return rows[:top_n]
    except Exception:
        return []
