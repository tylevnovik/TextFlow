from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from .common import json_ready, utc_now_iso
from .runtime_profile import default_runtime_profile

def workflow_payload_hash(workflow_definition: dict[str, Any] | None) -> str:
    payload = workflow_execution_payload(workflow_definition)
    encoded = json.dumps(json_ready(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def workflow_execution_payload(workflow_definition: dict[str, Any] | None) -> dict[str, Any]:
    workflow = workflow_definition if isinstance(workflow_definition, dict) else {}
    return {
        "workflow_id": str(workflow.get("workflow_id") or ""),
        "version": str(workflow.get("version") or ""),
        "graph_mode": str(workflow.get("graph_mode") or ""),
        "source": str(workflow.get("source") or ""),
        "meta": deepcopy(workflow.get("meta") if isinstance(workflow.get("meta"), dict) else {}),
        "nodes": [
            workflow_node_execution_payload(node)
            for node in workflow.get("nodes", [])
            if isinstance(node, dict)
        ],
        "edges": [
            workflow_edge_execution_payload(edge)
            for edge in workflow.get("edges", [])
            if isinstance(edge, dict)
        ],
    }


def workflow_node_execution_payload(node: dict[str, Any] | None) -> dict[str, Any]:
    payload = node if isinstance(node, dict) else {}
    ui_state = payload.get("ui_state") if isinstance(payload.get("ui_state"), dict) else {}
    return {
        "node_id": str(payload.get("node_id") or ""),
        "node_type": str(payload.get("node_type") or ""),
        "config": deepcopy(payload.get("config") if isinstance(payload.get("config"), dict) else {}),
        "ui_state": {
            "bypassed": bool(ui_state.get("bypassed")),
        },
        "runtime_meta": deepcopy(payload.get("runtime_meta") if isinstance(payload.get("runtime_meta"), dict) else {}),
        "inputs": [
            workflow_port_execution_payload(port)
            for port in payload.get("inputs", [])
            if isinstance(port, dict)
        ],
        "outputs": [
            workflow_port_execution_payload(port)
            for port in payload.get("outputs", [])
            if isinstance(port, dict)
        ],
    }


def workflow_port_execution_payload(port: dict[str, Any] | None) -> dict[str, Any]:
    payload = port if isinstance(port, dict) else {}
    normalized = {
        "port_id": str(payload.get("port_id") or ""),
        "port_type": str(payload.get("port_type") or ""),
    }
    if payload.get("allow_multiple"):
        normalized["allow_multiple"] = True
    return normalized


def workflow_edge_execution_payload(edge: dict[str, Any] | None) -> dict[str, Any]:
    payload = edge if isinstance(edge, dict) else {}
    return {
        "from_node": str(payload.get("from_node") or ""),
        "from_port": str(payload.get("from_port") or ""),
        "to_node": str(payload.get("to_node") or ""),
        "to_port": str(payload.get("to_port") or ""),
    }


def default_workflow_definition(
    runtime_profile: dict[str, Any] | None = None,
    *,
    workflow_id: str = "wf-default",
    name: str = "默认工作流",
    source: str = "system_default",
) -> dict[str, Any]:
    runtime_profile_definition = deepcopy(runtime_profile if isinstance(runtime_profile, dict) else default_runtime_profile())
    enabled_steps = set(runtime_profile_definition.get("enabled_steps") or [])
    timestamp = utc_now_iso()
    node_positions = {
        "dictionary_input": {"x": 120, "y": 80},
        "corpus_input": {"x": 120, "y": 330},
        "merge_corpora": {"x": 520, "y": 330},
        "clean_text": {"x": 900, "y": 330},
        "normalize_text": {"x": 1280, "y": 330},
        "tokenize": {"x": 1680, "y": 330},
        "apply_dictionary_rules": {"x": 2060, "y": 330},
        "filter_terms": {"x": 2460, "y": 330},
        "frequency_statistics": {"x": 2860, "y": 80},
        "term_document_analysis": {"x": 2860, "y": 340},
        "term_year_analysis": {"x": 2860, "y": 600},
        "cooccurrence_analysis": {"x": 2860, "y": 860},
        "feature_term_selection": {"x": 2860, "y": 1120},
        "keyword_extraction": {"x": 3240, "y": 80},
        "keyword_clustering": {"x": 3240, "y": 340},
        "institution_keyword_analysis": {"x": 3240, "y": 600},
        "institution_topic_analysis": {"x": 3240, "y": 860},
        "document_clustering": {"x": 3240, "y": 1120},
        "save_csv": {"x": 3620, "y": 80},
        "save_xlsx": {"x": 3620, "y": 340},
        "save_png": {"x": 3620, "y": 600},
        "save_html_report": {"x": 3620, "y": 860},
    }
    default_node_size = {"w": 230, "h": 190}

    def workflow_port(
        port_id: str,
        port_type: str,
        label: str,
        *,
        allow_multiple: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "port_id": port_id,
            "port_type": port_type,
            "label": label,
        }
        if allow_multiple:
            payload["allow_multiple"] = True
        return payload

    def workflow_node(
        node_id: str,
        node_type: str,
        label: str,
        inputs: list[dict[str, Any]],
        outputs: list[dict[str, Any]],
        config: dict[str, Any],
        step_id: str,
    ) -> dict[str, Any]:
        return {
            "node_id": node_id,
            "node_type": node_type,
            "label": label,
            "position": deepcopy(node_positions[node_type]),
            "size": deepcopy(default_node_size),
            "inputs": deepcopy(inputs),
            "outputs": deepcopy(outputs),
            "config": deepcopy(config),
            "ui_state": {
                "collapsed": False,
                "bypassed": False,
            },
            "runtime_meta": {
                "step_id": step_id,
                "node_impl_version": "2.0.0",
            },
        }

    def make_edge(
        edge_id: str,
        from_node: str,
        from_port: str,
        to_node: str,
        to_port: str,
    ) -> dict[str, Any]:
        return {
            "edge_id": edge_id,
            "from_node": from_node,
            "from_port": from_port,
            "to_node": to_node,
            "to_port": to_port,
        }

    export_definition = deepcopy(runtime_profile_definition.get("export") or {})
    run_scope_definition = deepcopy(runtime_profile_definition.get("run_scope") or {})

    filtered_sequence: list[str] = ["corpus_input"]
    if "cleaning" in enabled_steps:
        filtered_sequence.append("clean_text")
    if "normalization" in enabled_steps:
        filtered_sequence.append("normalize_text")
    filtered_sequence.append("tokenize")
    if "dictionary_application" in enabled_steps:
        filtered_sequence.append("apply_dictionary_rules")
    if "filtering" in enabled_steps:
        filtered_sequence.append("filter_terms")

    starter_nodes: list[dict[str, Any]] = []

    starter_nodes.append(
        workflow_node(
            "node-corpus-input",
            "corpus_input",
            "语料输入",
            [],
            [workflow_port("corpus", "CorpusTable", "语料")],
            {
                "resource_mode": "project_corpus",
                "resource_id": "project:corpus",
                **run_scope_definition,
            },
            "scope",
        )
    )
    starter_nodes.append(
        workflow_node(
            "node-dictionary-input",
            "dictionary_input",
            "词表输入",
            [],
            [workflow_port("dictionary_set", "DictionarySet", "词表")],
            {
                "resource_mode": "project_dictionary",
                "resource_id": "project:dictionary_set",
                "use_custom_lexicon": True,
                "use_phrase_lexicon": True,
                "apply_regex_rules": True,
                "apply_standard_terms": True,
                "apply_synonym_map": True,
                "apply_near_synonym_map": True,
                "apply_stopwords": True,
                "apply_exclusion_terms": True,
            },
            "resource",
        )
    )

    if "clean_text" in filtered_sequence:
        starter_nodes.append(
            workflow_node(
                "node-clean-text",
                "clean_text",
                "基础清洗",
                [workflow_port("corpus_in", "CorpusTable", "语料输入")],
                [workflow_port("clean_corpus", "CleanCorpus", "清洗后语料")],
                deepcopy(runtime_profile_definition.get("cleaning") or {}),
                "cleaning",
            )
        )
    if "normalize_text" in filtered_sequence:
        starter_nodes.append(
            workflow_node(
                "node-normalize-text",
                "normalize_text",
                "统一写法",
                [workflow_port("corpus_in", "CleanCorpus", "清洗后语料")],
                [workflow_port("normalized_corpus", "NormalizedCorpus", "标准化语料")],
                deepcopy(runtime_profile_definition.get("normalization") or {}),
                "normalization",
            )
        )
    starter_nodes.append(
        workflow_node(
            "node-tokenize",
            "tokenize",
            "切词",
            [workflow_port("corpus_in", "NormalizedCorpus", "标准化语料")],
            [workflow_port("token_corpus", "TokenCorpus", "Token 语料")],
            deepcopy(runtime_profile_definition.get("tokenization") or {}),
            "tokenization",
        )
    )
    if "apply_dictionary_rules" in filtered_sequence:
        starter_nodes.append(
            workflow_node(
                "node-apply-dictionary-rules",
                "apply_dictionary_rules",
                "套用词表",
                [
                    workflow_port("token_corpus_in", "TokenCorpus", "Token 输入"),
                    workflow_port("dictionary_set_in", "DictionarySet", "词表输入"),
                ],
                [
                    workflow_port("token_corpus", "TokenCorpus", "规则处理后 Token"),
                    workflow_port("audit_table", "AuditTable", "审计表"),
                ],
                deepcopy(runtime_profile_definition.get("dictionary") or {}),
                "dictionary_application",
            )
        )
    if "filter_terms" in filtered_sequence:
        starter_nodes.append(
            workflow_node(
                "node-filter-terms",
                "filter_terms",
                "过滤词项",
                [workflow_port("token_corpus_in", "TokenCorpus", "Token 输入")],
                [workflow_port("filtered_token_corpus", "FilteredTokenCorpus", "分析词项")],
                deepcopy(runtime_profile_definition.get("filtering") or {}),
                "filtering",
            )
        )

    starter_nodes.extend(
        [
            workflow_node(
                "node-frequency-statistics",
                "frequency_statistics",
                "词频统计",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("frequency_table", "FrequencyTable", "词频表")],
                {"top_n": int((runtime_profile_definition.get("analysis") or {}).get("top_n", 200))},
                "analysis",
            ),
            workflow_node(
                "node-term-document-analysis",
                "term_document_analysis",
                "词项文档分析",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("term_document_table", "TermDocumentTable", "词项文档表")],
                {},
                "analysis",
            ),
            workflow_node(
                "node-term-year-analysis",
                "term_year_analysis",
                "词项年份分析",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("term_year_table", "TermYearTable", "词项年份表")],
                {},
                "analysis",
            ),
            workflow_node(
                "node-cooccurrence-analysis",
                "cooccurrence_analysis",
                "共现分析",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("cooccurrence_table", "CooccurrenceTable", "共现表")],
                {
                    "cooccurrence_window": int((runtime_profile_definition.get("analysis") or {}).get("cooccurrence_window", 5)),
                    "min_cooccurrence": int((runtime_profile_definition.get("analysis") or {}).get("min_cooccurrence", 2)),
                },
                "analysis",
            ),
            workflow_node(
                "node-feature-term-selection",
                "feature_term_selection",
                "特征词筛选",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("feature_term_table", "FeatureTermTable", "特征词表")],
                {
                    "feature_term_count": (runtime_profile_definition.get("analysis") or {}).get("feature_term_count", 1000),
                },
                "analysis",
            ),
            workflow_node(
                "node-keyword-extraction",
                "keyword_extraction",
                "关键词提取",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("keyword_table", "KeywordTable", "关键词表")],
                {
                    "top_k_per_doc": int((runtime_profile_definition.get("analysis") or {}).get("top_k_per_doc", 10)),
                    "top_k_project": int((runtime_profile_definition.get("analysis") or {}).get("top_k_project", 100)),
                },
                "analysis",
            ),
            workflow_node(
                "node-keyword-clustering",
                "keyword_clustering",
                "关键词聚类",
                [workflow_port("feature_term_table_in", "FeatureTermTable", "特征词输入")],
                [workflow_port("keyword_cluster_table", "KeywordClusterTable", "关键词聚类表")],
                {
                    "keyword_cluster_k": int((runtime_profile_definition.get("analysis") or {}).get("keyword_cluster_k", 4)),
                    "topic_model_k": int((runtime_profile_definition.get("analysis") or {}).get("topic_model_k", 4)),
                },
                "analysis",
            ),
            workflow_node(
                "node-institution-keyword-analysis",
                "institution_keyword_analysis",
                "机构关键词分析",
                [workflow_port("keyword_table_in", "KeywordTable", "关键词输入")],
                [workflow_port("institution_keyword_table", "InstitutionKeywordTable", "机构关键词表")],
                {},
                "analysis",
            ),
            workflow_node(
                "node-institution-topic-analysis",
                "institution_topic_analysis",
                "机构主题分析",
                [workflow_port("keyword_cluster_table_in", "KeywordClusterTable", "主题输入")],
                [workflow_port("institution_topic_table", "InstitutionTopicTable", "机构主题表")],
                {
                    "topic_model_k": int((runtime_profile_definition.get("analysis") or {}).get("topic_model_k", 4)),
                },
                "analysis",
            ),
            workflow_node(
                "node-document-clustering",
                "document_clustering",
                "文档聚类",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("document_cluster_table", "DocumentClusterTable", "文档聚类表")],
                {
                    "document_cluster_k": int((runtime_profile_definition.get("analysis") or {}).get("document_cluster_k", 4)),
                },
                "analysis",
            ),
        ]
    )

    if bool(export_definition.get("export_csv", True)):
        starter_nodes.append(
            workflow_node(
                "node-save-csv",
                "save_csv",
                "保存 CSV",
                [workflow_port("table_in", "AnyTable", "表格输入", allow_multiple=True)],
                [workflow_port("artifact", "ExportArtifact", "导出产物")],
                {"file_prefix": "tables", "export_csv": True},
                "export",
            )
        )
    if bool(export_definition.get("export_xlsx", True)):
        starter_nodes.append(
            workflow_node(
                "node-save-xlsx",
                "save_xlsx",
                "保存 XLSX",
                [workflow_port("table_in", "AnyTable", "表格输入", allow_multiple=True)],
                [workflow_port("artifact", "ExportArtifact", "导出产物")],
                {"file_prefix": "tables", "export_xlsx": True},
                "export",
            )
        )
    if bool(export_definition.get("export_png", True)):
        starter_nodes.append(
            workflow_node(
                "node-save-png",
                "save_png",
                "保存 PNG",
                [workflow_port("render_in", "AnyRenderable", "图像输入", allow_multiple=True)],
                [workflow_port("artifact", "ExportArtifact", "导出产物")],
                {
                    "file_prefix": "charts",
                    "chart_dpi": int(export_definition.get("chart_dpi", 320)),
                },
                "export",
            )
        )
    if bool(export_definition.get("export_html_report", True)):
        starter_nodes.append(
            workflow_node(
                "node-save-html-report",
                "save_html_report",
                "保存 HTML 报告",
                [workflow_port("report_in", "AnyAnalysisResult", "报告输入", allow_multiple=True)],
                [workflow_port("artifact", "ExportArtifact", "导出产物")],
                {
                    "file_prefix": "report",
                    "include_audit": bool(export_definition.get("include_audit", True)),
                },
                "export",
            )
        )

    node_by_type = {
        str(node["node_type"]): node
        for node in starter_nodes
    }

    def single_output_port(node_type: str) -> str | None:
        node = node_by_type.get(node_type)
        if not isinstance(node, dict):
            return None
        outputs = node.get("outputs")
        if not isinstance(outputs, list) or not outputs:
            return None
        first_port = outputs[0]
        return str(first_port.get("port_id") or "") if isinstance(first_port, dict) else None

    edges: list[dict[str, Any]] = []
    edge_counter = 1

    for from_type, to_type in zip(filtered_sequence, filtered_sequence[1:]):
        from_node = node_by_type.get(from_type)
        to_node = node_by_type.get(to_type)
        from_port = single_output_port(from_type)
        to_port = str((to_node.get("inputs") or [{}])[0].get("port_id") or "") if isinstance(to_node, dict) else ""
        if from_node and to_node and from_port and to_port:
            edges.append(make_edge(f"edge-{edge_counter}", str(from_node["node_id"]), from_port, str(to_node["node_id"]), to_port))
            edge_counter += 1

    dictionary_node = node_by_type.get("dictionary_input")
    dictionary_apply_node = node_by_type.get("apply_dictionary_rules")
    if dictionary_node and dictionary_apply_node:
        edges.append(
            make_edge(
                f"edge-{edge_counter}",
                str(dictionary_node["node_id"]),
                "dictionary_set",
                str(dictionary_apply_node["node_id"]),
                "dictionary_set_in",
            )
        )
        edge_counter += 1

    last_process_node = None
    for node_type in ["filter_terms", "apply_dictionary_rules", "tokenize", "normalize_text", "clean_text", "corpus_input"]:
        candidate = node_by_type.get(node_type)
        if candidate:
            last_process_node = candidate
            break

    for analysis_type in [
        "frequency_statistics",
        "term_document_analysis",
        "term_year_analysis",
        "cooccurrence_analysis",
        "feature_term_selection",
        "keyword_extraction",
        "keyword_clustering",
        "institution_keyword_analysis",
        "institution_topic_analysis",
        "document_clustering",
    ]:
        analysis_node = node_by_type.get(analysis_type)
        if not analysis_node:
            continue
        if analysis_type == "keyword_clustering":
            feature_term_node = node_by_type.get("feature_term_selection")
            if feature_term_node:
                edges.append(
                    make_edge(
                        f"edge-{edge_counter}",
                        str(feature_term_node["node_id"]),
                        "feature_term_table",
                        str(analysis_node["node_id"]),
                        "feature_term_table_in",
                    )
                )
                edge_counter += 1
            continue
        if analysis_type == "institution_keyword_analysis":
            keyword_node = node_by_type.get("keyword_extraction")
            if keyword_node:
                edges.append(
                    make_edge(
                        f"edge-{edge_counter}",
                        str(keyword_node["node_id"]),
                        "keyword_table",
                        str(analysis_node["node_id"]),
                        "keyword_table_in",
                    )
                )
                edge_counter += 1
            continue
        if analysis_type == "institution_topic_analysis":
            cluster_node = node_by_type.get("keyword_clustering")
            if cluster_node:
                edges.append(
                    make_edge(
                        f"edge-{edge_counter}",
                        str(cluster_node["node_id"]),
                        "keyword_cluster_table",
                        str(analysis_node["node_id"]),
                        "keyword_cluster_table_in",
                    )
                )
                edge_counter += 1
            continue
        if last_process_node:
            from_port = str(((last_process_node.get("outputs") or [{}])[0]).get("port_id") or "")
            to_port = str(((analysis_node.get("inputs") or [{}])[0]).get("port_id") or "")
            if from_port and to_port:
                edges.append(
                    make_edge(
                        f"edge-{edge_counter}",
                        str(last_process_node["node_id"]),
                        from_port,
                        str(analysis_node["node_id"]),
                        to_port,
                    )
                )
                edge_counter += 1

    sink_mappings = {
        "save_csv": [
            "frequency_statistics",
            "term_document_analysis",
            "term_year_analysis",
            "cooccurrence_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "keyword_clustering",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "document_clustering",
        ],
        "save_xlsx": [
            "frequency_statistics",
            "term_document_analysis",
            "term_year_analysis",
            "cooccurrence_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "keyword_clustering",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "document_clustering",
        ],
        "save_png": [
            "frequency_statistics",
            "keyword_extraction",
            "keyword_clustering",
            "institution_topic_analysis",
            "document_clustering",
        ],
        "save_html_report": [
            "frequency_statistics",
            "term_document_analysis",
            "term_year_analysis",
            "cooccurrence_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "keyword_clustering",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "document_clustering",
        ],
    }

    for sink_type, source_types in sink_mappings.items():
        sink_node = node_by_type.get(sink_type)
        if not sink_node:
            continue
        sink_port = str(((sink_node.get("inputs") or [{}])[0]).get("port_id") or "")
        if not sink_port:
            continue
        for source_type in source_types:
            source_node = node_by_type.get(source_type)
            from_port = single_output_port(source_type)
            if not source_node or not from_port:
                continue
            edges.append(
                make_edge(
                    f"edge-{edge_counter}",
                    str(source_node["node_id"]),
                    from_port,
                    str(sink_node["node_id"]),
                    sink_port,
                )
            )
            edge_counter += 1
        if sink_type == "save_html_report" and dictionary_apply_node:
            edges.append(
                make_edge(
                    f"edge-{edge_counter}",
                    str(dictionary_apply_node["node_id"]),
                    "audit_table",
                    str(sink_node["node_id"]),
                    sink_port,
                )
            )
            edge_counter += 1

    return {
        "workflow_id": workflow_id,
        "name": name,
        "version": "2.0.0",
        "graph_mode": "dag",
        "source": source,
        "meta": {
            "template_id": str(runtime_profile_definition.get("recipe_id") or "standard_analysis"),
            "output_bundle_id": str(runtime_profile_definition.get("output_bundle_id") or "full_report"),
        },
        "nodes": starter_nodes,
        "edges": edges,
        "groups": [],
        "viewport": {
            "x": 0,
            "y": 0,
            "zoom": 0.82,
        },
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def workflow_port_compatible(source_type: str, target_type: str) -> bool:
    if source_type == target_type:
        return True
    table_source_types = {
        "FrequencyTable",
        "TermDocumentTable",
        "TermYearTable",
        "CooccurrenceTable",
        "FeatureTermTable",
        "KeywordTable",
        "KeywordClusterTable",
        "InstitutionKeywordTable",
        "InstitutionTopicTable",
        "DocumentClusterTable",
        "AuditTable",
        "MetadataAuditTable",
        "GraphNodeTable",
        "GraphEdgeTable",
        "GraphMetricTable",
        "CommunityTable",
        "MainPathTable",
        "LinkPredictionTable",
        "TechnologyIndicatorTable",
        "TechnologyClassificationTable",
    }
    renderable_source_types = {
        "FrequencyTable",
        "KeywordTable",
        "TermYearTable",
        "CooccurrenceTable",
        "DocumentClusterTable",
        "KeywordClusterTable",
        "InstitutionTopicTable",
        "AnalysisBundle",
        "AnyTable",
    }
    analysis_result_types = set(table_source_types) | {"AnalysisBundle", "AnyTable"}
    if target_type == "AnyTable" and source_type in table_source_types:
        return True
    if target_type == "AnyRenderable" and source_type in renderable_source_types:
        return True
    if target_type == "AnyAnalysisResult" and source_type in analysis_result_types:
        return True
    corpus_port_order = [
        "CorpusTable",
        "ProjectCorpus",
        "ScopedCorpus",
        "CleanCorpus",
        "NormalizedCorpus",
        "TokenCorpus",
        "FilteredTokenCorpus",
    ]
    try:
        source_index = corpus_port_order.index(source_type)
        target_index = corpus_port_order.index(target_type)
    except ValueError:
        if source_type in {"ProjectCorpus", "ScopedCorpus"} and target_type == "CorpusTable":
            return True
        if source_type == "CorpusTable" and target_type in {"ProjectCorpus", "ScopedCorpus"}:
            return True
        return False
    return source_index <= target_index


def workflow_find_port(node: dict[str, Any] | None, port_id: str, direction: str) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    ports = node.get(direction)
    if not isinstance(ports, list):
        return None
    for port in ports:
        if isinstance(port, dict) and str(port.get("port_id")) == port_id:
            return port
    return None


def normalize_workflow_edges(
    workflow_definition: dict[str, Any] | None,
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    edge_rows = workflow_definition.get("edges") if isinstance(workflow_definition, dict) else []
    if not isinstance(edge_rows, list):
        return []

    node_lookup = {
        str(node.get("node_id")): node
        for node in nodes
        if isinstance(node, dict) and node.get("node_id")
    }
    normalized: list[dict[str, Any]] = []

    for edge in edge_rows:
        if not isinstance(edge, dict):
            continue
        from_node_id = str(edge.get("from_node") or "")
        to_node_id = str(edge.get("to_node") or "")
        from_port_id = str(edge.get("from_port") or "")
        to_port_id = str(edge.get("to_port") or "")
        if not from_node_id or not to_node_id or from_node_id == to_node_id:
            continue
        from_node = node_lookup.get(from_node_id)
        to_node = node_lookup.get(to_node_id)
        from_port = workflow_find_port(from_node, from_port_id, "outputs")
        to_port = workflow_find_port(to_node, to_port_id, "inputs")
        if not isinstance(from_port, dict) or not isinstance(to_port, dict):
            continue
        if not workflow_port_compatible(str(from_port.get("port_type") or ""), str(to_port.get("port_type") or "")):
            continue

        target_allows_multiple = bool(to_port.get("allow_multiple"))
        if not target_allows_multiple:
            normalized = [
                existing
                for existing in normalized
                if not (
                    str(existing.get("to_node")) == to_node_id
                    and str(existing.get("to_port")) == to_port_id
                )
            ]
        if any(
            str(existing.get("from_node")) == from_node_id
            and str(existing.get("from_port")) == from_port_id
            and str(existing.get("to_node")) == to_node_id
            and str(existing.get("to_port")) == to_port_id
            for existing in normalized
        ):
            continue
        normalized.append(deepcopy(edge))

    return normalized


def workflow_reachable_node_ids(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> set[str]:
    incoming: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        key = (str(edge.get("to_node") or ""), str(edge.get("to_port") or ""))
        if not all(key):
            continue
        incoming.setdefault(key, []).append(edge)

    reachable = set()
    for node in nodes:
        if not isinstance(node, dict) or not node.get("node_id"):
            continue
        inputs = node.get("inputs")
        if isinstance(inputs, list) and not inputs:
            reachable.add(str(node["node_id"]))

    changed = True
    while changed:
        changed = False
        for node in nodes:
            if not isinstance(node, dict) or not node.get("node_id"):
                continue
            node_id = str(node["node_id"])
            if node_id in reachable:
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, list) or not inputs:
                continue
            if all(
                any(str(edge.get("from_node") or "") in reachable for edge in incoming.get((node_id, str(port.get("port_id") or "")), []))
                for port in inputs
                if isinstance(port, dict)
            ):
                reachable.add(node_id)
                changed = True
    return reachable


def workflow_active_node_ids_from_sinks(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    reachable_node_ids: set[str],
) -> set[str]:
    sink_node_types = {"save_csv", "save_xlsx", "save_png", "save_html_report", "export_results"}
    incoming_by_key: dict[str, list[dict[str, Any]]] = {}
    node_lookup = {str(node.get("node_id") or ""): node for node in nodes if isinstance(node, dict)}
    for edge in edges:
        to_node_id = str(edge.get("to_node") or "")
        to_port_id = str(edge.get("to_port") or "")
        incoming_by_key.setdefault(f"{to_node_id}:{to_port_id}", []).append(edge)

    sink_ids: list[str] = []
    for node in nodes:
        node_id = str(node.get("node_id") or "")
        if node_id not in reachable_node_ids:
            continue
        if str(node.get("node_type") or "") not in sink_node_types:
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, list):
            continue
        if all(incoming_by_key.get(f"{node_id}:{str(port.get('port_id') or '')}") for port in inputs if isinstance(port, dict)):
            sink_ids.append(node_id)

    active_ids = set(sink_ids)
    stack = sink_ids[:]
    while stack:
        current_id = stack.pop()
        current_node = node_lookup.get(current_id)
        if not isinstance(current_node, dict):
            continue
        inputs = current_node.get("inputs")
        if not isinstance(inputs, list):
            continue
        for port in inputs:
            if not isinstance(port, dict):
                continue
            for edge in incoming_by_key.get(f"{current_id}:{str(port.get('port_id') or '')}", []):
                from_node_id = str(edge.get("from_node") or "")
                if from_node_id and from_node_id not in active_ids:
                    active_ids.add(from_node_id)
                    stack.append(from_node_id)
    return active_ids
