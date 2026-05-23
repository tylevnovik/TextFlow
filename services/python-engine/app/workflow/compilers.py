from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..defaults import (
    default_runtime_profile,
    normalize_workflow_edges,
    workflow_active_node_ids_from_sinks,
    workflow_reachable_node_ids,
)
from .registry import NodeCompileContext, NodeRegistry, NodeRegistryBuilder

ANALYSIS_OUTPUT_FLAG_MAP = {
    "frequency_statistics": "include_frequency_statistics",
    "term_document_analysis": "include_term_document_relations",
    "term_year_analysis": "include_term_year_relations",
    "cooccurrence_analysis": "include_cooccurrence_analysis",
    "similarity_analysis": "include_similarity_analysis",
    "feature_term_selection": "include_feature_term_selection",
    "keyword_extraction": "include_keyword_extraction",
    "keyword_clustering": "include_keyword_clustering",
    "institution_keyword_analysis": "include_institution_keyword_analysis",
    "institution_topic_analysis": "include_institution_topic_analysis",
    "document_clustering": "include_document_clustering",
}

ANALYSIS_OUTPUT_FLAGS = list(ANALYSIS_OUTPUT_FLAG_MAP.values())
MODERN_ANALYSIS_NODE_TYPES = set(ANALYSIS_OUTPUT_FLAG_MAP)


def _analysis_patch(context: NodeCompileContext, **patch: Any) -> None:
    context.merge_section("analysis", patch)
    context.enable_step("analysis")


def _enable_analysis_output(context: NodeCompileContext, node_type: str, **patch: Any) -> None:
    flag_name = ANALYSIS_OUTPUT_FLAG_MAP.get(node_type)
    if flag_name:
        patch = {flag_name: True, **patch}
    _analysis_patch(context, **patch)


def classify_output_bundle(export_config: dict[str, Any]) -> str:
    if (
        export_config.get("export_csv")
        and export_config.get("export_xlsx")
        and export_config.get("export_png")
        and export_config.get("export_html_report")
        and export_config.get("include_audit")
    ):
        return "full_report"
    if (
        export_config.get("export_csv")
        and export_config.get("export_xlsx")
        and not export_config.get("export_png")
        and not export_config.get("export_html_report")
        and export_config.get("include_audit")
    ):
        return "tables_only"
    if (
        not export_config.get("export_csv")
        and not export_config.get("export_xlsx")
        and export_config.get("export_png")
        and export_config.get("export_html_report")
        and not export_config.get("include_audit")
    ):
        return "charts_and_report"
    if (
        export_config.get("export_csv")
        and not export_config.get("export_xlsx")
        and not export_config.get("export_png")
        and export_config.get("export_html_report")
        and export_config.get("include_audit")
    ):
        return "audit_archive"
    return "custom"


def _compile_scope(context: NodeCompileContext, node: dict[str, Any]) -> None:
    context.merge_section("run_scope", node.get("config") if isinstance(node.get("config"), dict) else {})


def _compile_dictionary_input(context: NodeCompileContext, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    tokenization = context.compiled.get("tokenization") if isinstance(context.compiled.get("tokenization"), dict) else {}
    normalization = context.compiled.get("normalization") if isinstance(context.compiled.get("normalization"), dict) else {}
    dictionary = context.compiled.get("dictionary") if isinstance(context.compiled.get("dictionary"), dict) else {}
    context.merge_section(
        "tokenization",
        {
            "use_custom_lexicon": bool(config.get("use_custom_lexicon", tokenization.get("use_custom_lexicon", True))),
            "use_phrase_lexicon": bool(config.get("use_phrase_lexicon", tokenization.get("use_phrase_lexicon", True))),
        },
    )
    context.merge_section(
        "normalization",
        {
            "apply_regex_rules": bool(config.get("apply_regex_rules", normalization.get("apply_regex_rules", True))),
        },
    )
    context.merge_section(
        "dictionary",
        {
            "apply_standard_terms": bool(config.get("apply_standard_terms", dictionary.get("apply_standard_terms", True))),
            "apply_synonym_map": bool(config.get("apply_synonym_map", dictionary.get("apply_synonym_map", True))),
            "apply_near_synonym_map": bool(
                config.get("apply_near_synonym_map", dictionary.get("apply_near_synonym_map", True))
            ),
            "apply_stopwords": bool(config.get("apply_stopwords", dictionary.get("apply_stopwords", True))),
            "apply_exclusion_terms": bool(
                config.get("apply_exclusion_terms", dictionary.get("apply_exclusion_terms", True))
            ),
        },
    )


def _compile_passthrough_node(_context: NodeCompileContext, _node: dict[str, Any]) -> None:
    return None


def _compile_analysis_passthrough_node(context: NodeCompileContext, _node: dict[str, Any]) -> None:
    context.enable_step("analysis")


def _compile_filtering_passthrough_node(context: NodeCompileContext, _node: dict[str, Any]) -> None:
    context.enable_step("filtering")


def _merge_runtime_section(section_id: str, step_id: str):
    def compiler(context: NodeCompileContext, node: dict[str, Any]) -> None:
        patch = node.get("config") if isinstance(node.get("config"), dict) else {}
        context.merge_section(section_id, patch)
        context.enable_step(step_id)

    return compiler


def _compile_frequency_statistics(context: NodeCompileContext, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    _enable_analysis_output(context, "frequency_statistics", top_n=int(config.get("top_n") or analysis.get("top_n", 200)))


def _compile_term_document_analysis(context: NodeCompileContext, _node: dict[str, Any]) -> None:
    _enable_analysis_output(context, "term_document_analysis")


def _compile_term_year_analysis(context: NodeCompileContext, _node: dict[str, Any]) -> None:
    _enable_analysis_output(context, "term_year_analysis")


def _compile_cooccurrence_analysis(context: NodeCompileContext, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    _enable_analysis_output(
        context,
        "cooccurrence_analysis",
        cooccurrence_window=int(config.get("cooccurrence_window") or analysis.get("cooccurrence_window", 5)),
        min_cooccurrence=int(config.get("min_cooccurrence") or analysis.get("min_cooccurrence", 2)),
    )


def _compile_feature_term_selection(context: NodeCompileContext, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    raw_value = config.get("feature_term_count")
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    feature_term_count = "all" if str(raw_value) == "all" else int(raw_value or analysis.get("feature_term_count", 1000))
    _enable_analysis_output(context, "feature_term_selection", feature_term_count=feature_term_count)


def _compile_keyword_extraction(context: NodeCompileContext, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    _enable_analysis_output(
        context,
        "keyword_extraction",
        top_k_per_doc=int(config.get("top_k_per_doc") or analysis.get("top_k_per_doc", 10)),
        top_k_project=int(config.get("top_k_project") or analysis.get("top_k_project", 100)),
    )


def _compile_keyword_clustering(context: NodeCompileContext, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    _enable_analysis_output(
        context,
        "keyword_clustering",
        include_feature_term_selection=True,
        keyword_cluster_k=int(config.get("keyword_cluster_k") or analysis.get("keyword_cluster_k", 4)),
        topic_model_k=int(config.get("topic_model_k") or analysis.get("topic_model_k", 4)),
    )


def _compile_institution_keyword_analysis(context: NodeCompileContext, _node: dict[str, Any]) -> None:
    _enable_analysis_output(
        context,
        "institution_keyword_analysis",
        include_keyword_extraction=True,
    )


def _compile_institution_topic_analysis(context: NodeCompileContext, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    _enable_analysis_output(
        context,
        "institution_topic_analysis",
        include_feature_term_selection=True,
        include_keyword_clustering=True,
        topic_model_k=int(config.get("topic_model_k") or analysis.get("topic_model_k", 4)),
    )


def _compile_document_clustering(context: NodeCompileContext, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis = context.compiled.get("analysis") if isinstance(context.compiled.get("analysis"), dict) else {}
    _enable_analysis_output(
        context,
        "document_clustering",
        document_cluster_k=int(config.get("document_cluster_k") or analysis.get("document_cluster_k", 4)),
    )


def _compile_analyze_corpus(context: NodeCompileContext, node: dict[str, Any]) -> None:
    patch = node.get("config") if isinstance(node.get("config"), dict) else {}
    context.merge_section("analysis", {**{flag: True for flag in ANALYSIS_OUTPUT_FLAGS}, **patch})
    context.enable_step("analysis")


def _compile_save_csv(context: NodeCompileContext, _node: dict[str, Any]) -> None:
    context.enable_export(export_csv=True)


def _compile_save_xlsx(context: NodeCompileContext, _node: dict[str, Any]) -> None:
    context.enable_export(export_xlsx=True)


def _compile_save_png(context: NodeCompileContext, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    chart_dpi = int(config.get("chart_dpi") or context.export_config.get("chart_dpi", 320))
    context.enable_export(export_png=True, chart_dpi=chart_dpi)


def _compile_save_html_report(context: NodeCompileContext, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    include_audit = bool(config.get("include_audit", context.export_config.get("include_audit", True)))
    context.enable_export(export_html_report=True, include_audit=include_audit)


def _compile_export_results(context: NodeCompileContext, node: dict[str, Any]) -> None:
    patch = node.get("config") if isinstance(node.get("config"), dict) else {}
    context.enable_export(**patch)


BUILTIN_NODE_COMPILERS = {
    "corpus_input": _compile_scope,
    "filter_corpus": _compile_scope,
    "select_dictionary_tables": _compile_passthrough_node,
    "overlay_dictionary_rules": _compile_passthrough_node,
    "filter_by_metadata": _compile_passthrough_node,
    "deduplicate_documents": _compile_passthrough_node,
    "sample_corpus": _compile_passthrough_node,
    "split_corpus": _compile_analysis_passthrough_node,
    "bucket_by_time": _compile_analysis_passthrough_node,
    "conditional_router": _compile_passthrough_node,
    "result_gate": _compile_analysis_passthrough_node,
    "manual_review_gate": _compile_passthrough_node,
    "dictionary_input": _compile_dictionary_input,
    "clean_text": _merge_runtime_section("cleaning", "cleaning"),
    "normalize_metadata": _compile_passthrough_node,
    "normalize_text": _merge_runtime_section("normalization", "normalization"),
    "tokenize": _merge_runtime_section("tokenization", "tokenization"),
    "apply_dictionary_rules": _merge_runtime_section("dictionary", "dictionary_application"),
    "filter_terms": _merge_runtime_section("filtering", "filtering"),
    "focus_terms": _compile_filtering_passthrough_node,
    "analyze_corpus": _compile_analyze_corpus,
    "frequency_statistics": _compile_frequency_statistics,
    "term_document_analysis": _compile_term_document_analysis,
    "term_year_analysis": _compile_term_year_analysis,
    "cooccurrence_analysis": _compile_cooccurrence_analysis,
    "similarity_analysis": _compile_analysis_passthrough_node,
    "group_compare": _compile_analysis_passthrough_node,
    "keyness_analysis": _compile_analysis_passthrough_node,
    "topic_modeling": _compile_analysis_passthrough_node,
    "cluster_evaluation": _compile_analysis_passthrough_node,
    "join_results": _compile_analysis_passthrough_node,
    "feature_term_selection": _compile_feature_term_selection,
    "keyword_extraction": _compile_keyword_extraction,
    "keyword_clustering": _compile_keyword_clustering,
    "institution_keyword_analysis": _compile_institution_keyword_analysis,
    "institution_topic_analysis": _compile_institution_topic_analysis,
    "document_clustering": _compile_document_clustering,
    "build_network": _compile_analysis_passthrough_node,
    "graph_metrics": _compile_analysis_passthrough_node,
    "community_detection": _compile_analysis_passthrough_node,
    "main_path_analysis": _compile_analysis_passthrough_node,
    "link_prediction": _compile_analysis_passthrough_node,
    "technology_indicators": _compile_analysis_passthrough_node,
    "technology_classification": _compile_analysis_passthrough_node,
    "save_csv": _compile_save_csv,
    "save_xlsx": _compile_save_xlsx,
    "save_png": _compile_save_png,
    "save_html_report": _compile_save_html_report,
    "export_results": _compile_export_results,
}


def register_builtin_node_compilers(builder: NodeRegistryBuilder) -> None:
    for node_type, compiler in BUILTIN_NODE_COMPILERS.items():
        builder.register_compiler(node_type, compiler)


def compile_runtime_profile_from_workflow(
    workflow_definition: dict[str, Any] | None,
    runtime_profile: dict[str, Any] | None = None,
    *,
    registry: NodeRegistry | None = None,
) -> dict[str, Any]:
    if registry is None:
        from .registry import build_node_registry

        registry = build_node_registry(runtime_profile)

    compiled = deepcopy(runtime_profile if isinstance(runtime_profile, dict) else default_runtime_profile())
    execution_order = list(compiled.get("execution_order") or default_runtime_profile()["execution_order"])
    nodes = workflow_definition.get("nodes") if isinstance(workflow_definition, dict) else []
    normalized_nodes = [node for node in nodes if isinstance(node, dict) and node.get("node_id")] if isinstance(nodes, list) else []
    normalized_edges = normalize_workflow_edges(workflow_definition, normalized_nodes)
    reachable_node_ids = workflow_reachable_node_ids(normalized_nodes, normalized_edges)
    active_node_ids = workflow_active_node_ids_from_sinks(normalized_nodes, normalized_edges, reachable_node_ids)
    if not active_node_ids:
        active_node_ids = set(reachable_node_ids)

    export_config = deepcopy(compiled.get("export") or {})
    export_config.update(
        {
            "export_csv": False,
            "export_xlsx": False,
            "export_png": False,
            "export_html_report": False,
        }
    )
    context = NodeCompileContext(
        compiled=compiled,
        enabled_steps={"ingestion"},
        export_config=export_config,
        active_node_ids=set(active_node_ids),
        active_node_types=set(),
        execution_order=execution_order,
        workflow_definition=workflow_definition if isinstance(workflow_definition, dict) else None,
    )

    active_nodes: list[dict[str, Any]] = []
    for node in normalized_nodes:
        node_id = str(node.get("node_id") or "")
        if node_id not in context.active_node_ids:
            continue
        ui_state = node.get("ui_state")
        if isinstance(ui_state, dict) and bool(ui_state.get("bypassed")):
            continue
        active_nodes.append(node)
        context.active_node_types.add(str(node.get("node_type") or ""))

    context.merge_section("analysis", {flag_name: False for flag_name in ANALYSIS_OUTPUT_FLAGS})

    for node in active_nodes:
        compiler = registry.compilers.get(str(node.get("node_type") or ""))
        if compiler is not None:
            compiler(context, node)

    compiled["export"] = context.export_config

    meta = workflow_definition.get("meta") if isinstance(workflow_definition, dict) else {}
    meta_output_bundle_id = ""
    if isinstance(meta, dict):
        compiled["recipe_id"] = str(meta.get("template_id") or compiled.get("recipe_id") or "standard_analysis")
        meta_output_bundle_id = str(meta.get("output_bundle_id") or "")

    compiled["enabled_steps"] = [
        step_id
        for step_id in execution_order
        if step_id == "ingestion" or step_id in context.enabled_steps
    ]
    compiled["execution_order"] = execution_order
    compiled["output_bundle_id"] = meta_output_bundle_id or classify_output_bundle(compiled.get("export") or {})
    return compiled
