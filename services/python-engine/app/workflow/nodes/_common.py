from __future__ import annotations

from copy import deepcopy
from typing import Any

from ...domain.runtime_profile import default_runtime_profile

ANALYSIS_OUTPUT_FLAGS = [
    "include_frequency_statistics",
    "include_term_document_relations",
    "include_term_year_relations",
    "include_cooccurrence_analysis",
    "include_feature_term_selection",
    "include_keyword_extraction",
    "include_keyword_clustering",
    "include_institution_keyword_analysis",
    "include_institution_topic_analysis",
    "include_document_clustering",
    "include_similarity_analysis",
]


def port(
    port_id: str,
    port_type: str,
    label: str,
    *,
    allow_multiple: bool = False,
    result_bundle_key: str | None = None,
    png_chart_ids: list[str] | None = None,
    include_in_html_audit: bool = False,
) -> dict[str, Any]:
    payload = {
        "port_id": port_id,
        "port_type": port_type,
        "label": label,
    }
    if allow_multiple:
        payload["allow_multiple"] = True
    if result_bundle_key:
        payload["result_bundle_key"] = result_bundle_key
    if png_chart_ids:
        payload["png_chart_ids"] = list(png_chart_ids)
    if include_in_html_audit:
        payload["include_in_html_audit"] = True
    return payload


def bool_param(param_id: str, label: str, default: bool, description: str = "") -> dict[str, Any]:
    return {
        "param_id": param_id,
        "label": label,
        "kind": "boolean",
        "default_value": default,
        "description": description,
    }


def number_param(param_id: str, label: str, default: int | float | None, description: str = "") -> dict[str, Any]:
    return {
        "param_id": param_id,
        "label": label,
        "kind": "number",
        "default_value": default,
        "description": description,
    }


def string_param(param_id: str, label: str, default: str | None, description: str = "") -> dict[str, Any]:
    return {
        "param_id": param_id,
        "label": label,
        "kind": "string",
        "default_value": default,
        "description": description,
    }


def enum_param(
    param_id: str,
    label: str,
    default: str,
    options: list[tuple[str, str]],
    description: str = "",
) -> dict[str, Any]:
    return {
        "param_id": param_id,
        "label": label,
        "kind": "enum",
        "default_value": default,
        "description": description,
        "options": [{"value": value, "label": option_label} for value, option_label in options],
    }


def runtime(
    step_id: str,
    executor: str,
    *,
    cacheable: bool,
    previewable: bool,
    output_node: bool = False,
    parallel_safe: bool = False,
) -> dict[str, Any]:
    payload = {
        "step_id": step_id,
        "executor": executor,
        "cacheable": cacheable,
        "previewable": previewable,
        "output_node": output_node,
    }
    if parallel_safe:
        payload["parallel_safe"] = True
    return payload


def node_definition_from_base(
    base_definition: dict[str, Any],
    runtime_profile: dict[str, Any] | None = None,
    runtime_param_defaults: dict[str, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    definition = deepcopy(base_definition)
    if not runtime_param_defaults:
        return definition

    profile = deepcopy(runtime_profile if isinstance(runtime_profile, dict) else default_runtime_profile())
    params = definition.get("params") if isinstance(definition.get("params"), list) else []
    for param in params:
        if not isinstance(param, dict):
            continue
        param_id = str(param.get("param_id") or "")
        path = runtime_param_defaults.get(param_id)
        if not path:
            continue
        section_id, key = path
        section = profile.get(section_id) if isinstance(profile.get(section_id), dict) else {}
        value = section.get(key, param.get("default_value"))
        default_value = param.get("default_value")
        if isinstance(default_value, bool):
            value = bool(value)
        elif isinstance(default_value, int) and not isinstance(default_value, bool) and value is not None:
            value = int(value)
        elif isinstance(default_value, float) and value is not None:
            value = float(value)
        elif isinstance(default_value, str):
            value = str(value)
        param["default_value"] = value
    return definition


def node_config(node: dict[str, Any]) -> dict[str, Any]:
    return node.get("config") if isinstance(node.get("config"), dict) else {}


def noop_compiler(_context: Any, _node: dict[str, Any]) -> None:
    return None


def passthrough_compiler(_context: Any, _node: dict[str, Any]) -> None:
    return None


def analysis_passthrough_compiler(context: Any, _node: dict[str, Any]) -> None:
    context.enable_step("analysis")


def filtering_passthrough_compiler(context: Any, _node: dict[str, Any]) -> None:
    context.enable_step("filtering")


def scope_compiler(context: Any, node: dict[str, Any]) -> None:
    context.merge_section("run_scope", node_config(node))


def runtime_section_compiler(section_id: str, step_id: str):
    def compiler(context: Any, node: dict[str, Any]) -> None:
        context.merge_section(section_id, node_config(node))
        context.enable_step(step_id)

    return compiler


def dictionary_input_compiler(context: Any, node: dict[str, Any]) -> None:
    config = node_config(node)
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


def analyze_corpus_compiler(context: Any, node: dict[str, Any]) -> None:
    context.merge_section("analysis", {**{flag: True for flag in ANALYSIS_OUTPUT_FLAGS}, **node_config(node)})
    context.enable_step("analysis")


def export_results_compiler(context: Any, node: dict[str, Any]) -> None:
    context.enable_export(**node_config(node))


def empty_executor(_context: Any, _node: dict[str, Any], _inputs: dict[str, Any]) -> dict[str, Any]:
    return {}
