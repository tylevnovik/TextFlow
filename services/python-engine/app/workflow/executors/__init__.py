"""Built-in workflow node executor categories."""

from .analysis import *  # noqa: F401,F403
from .corpus import *  # noqa: F401,F403
from .export import *  # noqa: F401,F403
from .graph import *  # noqa: F401,F403
from .legacy import *  # noqa: F401,F403
from .preprocessing import *  # noqa: F401,F403
from .technology import *  # noqa: F401,F403

from ..definitions.builtin import build_builtin_node_definitions
from .export import execute_legacy_passthrough

EXECUTORS_BY_TYPE = {
    "corpus_input": execute_corpus_input,
    "load_project_corpus": execute_corpus_input,
    "filter_corpus": execute_filter_corpus,
    "select_dictionary_tables": execute_select_dictionary_tables,
    "overlay_dictionary_rules": execute_overlay_dictionary_rules,
    "filter_by_metadata": execute_filter_by_metadata,
    "deduplicate_documents": execute_deduplicate_documents,
    "sample_corpus": execute_sample_corpus,
    "split_corpus": execute_split_corpus,
    "bucket_by_time": execute_bucket_by_time,
    "conditional_router": execute_conditional_router,
    "result_gate": execute_result_gate,
    "manual_review_gate": execute_manual_review_gate,
    "dictionary_input": execute_dictionary_input,
    "project_dictionary_set": execute_dictionary_input,
    "merge_corpora": execute_merge_corpora,
    "clean_text": execute_clean_text,
    "normalize_metadata": execute_normalize_metadata,
    "normalize_text": execute_normalize_text,
    "tokenize": execute_tokenize,
    "apply_dictionary_rules": execute_apply_dictionary_rules,
    "filter_terms": execute_filter_terms,
    "focus_terms": execute_focus_terms,
    "frequency_statistics": execute_frequency_statistics,
    "term_document_analysis": execute_term_document_analysis,
    "term_year_analysis": execute_term_year_analysis,
    "cooccurrence_analysis": execute_cooccurrence_analysis,
    "similarity_analysis": execute_similarity_analysis,
    "group_compare": execute_group_compare,
    "keyness_analysis": execute_keyness_analysis,
    "topic_modeling": execute_topic_modeling,
    "cluster_evaluation": execute_cluster_evaluation,
    "join_results": execute_join_results,
    "feature_term_selection": execute_feature_term_selection,
    "keyword_extraction": execute_keyword_extraction,
    "keyword_clustering": execute_keyword_clustering,
    "institution_keyword_analysis": execute_institution_keyword_analysis,
    "institution_topic_analysis": execute_institution_topic_analysis,
    "document_clustering": execute_document_clustering,
    "build_network": execute_build_network,
    "graph_metrics": execute_graph_metrics,
    "community_detection": execute_community_detection,
    "main_path_analysis": execute_main_path_analysis,
    "link_prediction": execute_link_prediction,
    "technology_indicators": execute_technology_indicators,
    "technology_classification": execute_technology_classification,
    "save_csv": execute_save_csv,
    "save_xlsx": execute_save_xlsx,
    "save_png": execute_save_png,
    "save_html_report": execute_save_html_report,
    "analyze_corpus": execute_legacy_analyze_corpus,
    "export_results": execute_legacy_export_results,
}


def register_builtin_node_executors(builder: Any) -> None:
    for definition in build_builtin_node_definitions(builder.runtime_profile_definition):
        runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
        executor_id = str(runtime.get("executor") or "")
        node_type = str(definition.get("type") or "")
        if not executor_id or not node_type:
            continue
        executor = EXECUTORS_BY_TYPE.get(node_type, execute_legacy_passthrough)
        builder.register_executor(executor_id, executor)

