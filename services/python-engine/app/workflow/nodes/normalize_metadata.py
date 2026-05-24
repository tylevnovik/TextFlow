from __future__ import annotations

from typing import Any

from ._common import bool_param, passthrough_compiler, port, runtime, string_param
from ._support import _clone_corpus_rows, _report_corpus_progress, _scoped_corpus_from_inputs


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "normalize_metadata",
        "title": "元数据标准化",
        "category": "process",
        "description": "标准化机构、国家/地区、年份和类别字段。",
        "inputs": [
            port("corpus_in", "CorpusTable", "语料输入")
        ],
        "outputs": [
            port("normalized_corpus", "CorpusTable", "标准化后语料"),
            port("metadata_audit_table", "MetadataAuditTable", "元数据审计表", result_bundle_key="metadata_audit_table", include_in_html_audit=True),
        ],
        "params": [
            string_param("institution_aliases_text", "机构别名映射", ""),
            string_param("country_aliases_text", "国家别名映射", ""),
            string_param("category_aliases_text", "类别别名映射", ""),
            string_param("split_delimiters", "分隔符", ";；|"),
            bool_param("keep_first_institution", "仅保留首个机构", True),
            string_param("year_source_field", "年份来源字段", "year"),
        ],
        "runtime": runtime(
            "normalization",
            "workflow.normalize_metadata",
            cacheable=True,
            previewable=True,
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}

    def _parse_aliases(text: str) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for line in str(text or "").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t") if "\t" in line else line.split("|")
            if len(parts) >= 2:
                aliases[parts[0].strip()] = parts[1].strip()
        return aliases

    institution_aliases = _parse_aliases(config.get("institution_aliases_text"))
    country_aliases = _parse_aliases(config.get("country_aliases_text"))
    category_aliases = _parse_aliases(config.get("category_aliases_text"))

    country_map: dict[str, str] = {
        **country_aliases,
        "CN": "China",
        "中国": "China",
        "China": "China",
        "US": "United States",
        "USA": "United States",
        "United States": "United States",
        "美国": "United States",
    }

    split_delimiters = str(config.get("split_delimiters") or ";；|")
    keep_first = bool(config.get("keep_first_institution", True))
    year_source = str(config.get("year_source_field") or "year").strip() or "year"

    audit_rows: list[dict[str, Any]] = []
    total = len(corpus)

    for index, item in enumerate(corpus, start=1):
        doc_id = str(item.get("doc_id") or item.get("id") or "")
        changed = False

        # institution normalization
        institution = str(item.get("institution") or "").strip()
        if institution:
            for delim in split_delimiters:
                institution = institution.replace(delim, ";")
            parts = [p.strip() for p in institution.split(";") if p.strip()]
            if keep_first and parts:
                parts = parts[:1]
            normalized_parts = [institution_aliases.get(p, p) for p in parts]
            new_institution = "; ".join(normalized_parts)
            if new_institution != item.get("institution"):
                item["institution"] = new_institution
                if keep_first:
                    item.setdefault("extra_metadata", {})["institution_values"] = parts
                audit_rows.append({"doc_id": doc_id, "field": "institution", "old": institution, "new": new_institution})
                changed = True

        # country normalization
        country = str(item.get("country_or_region") or "").strip()
        if country:
            new_country = country_map.get(country, country)
            if new_country != country:
                item["country_or_region"] = new_country
                audit_rows.append({"doc_id": doc_id, "field": "country_or_region", "old": country, "new": new_country})
                changed = True

        # year normalization
        year_value = item.get(year_source)
        if year_value is not None:
            from ...ingestion import parse_optional_year
            parsed_year = parse_optional_year(year_value)
            if parsed_year is not None and parsed_year != item.get("year"):
                old_year = item.get("year")
                item["year"] = parsed_year
                audit_rows.append({"doc_id": doc_id, "field": "year", "old": old_year, "new": parsed_year})
                changed = True

        # category normalization
        category = str(item.get("category_or_tag") or "").strip()
        if category:
            new_category = category_aliases.get(category, category)
            if new_category != category:
                item["category_or_tag"] = new_category
                audit_rows.append({"doc_id": doc_id, "field": "category_or_tag", "old": category, "new": new_category})
                changed = True

        if changed:
            item.setdefault("extra_metadata", {})["metadata_normalization_audit"] = True

        _report_corpus_progress(context, node, index, total, "元数据标准化")

    context.shared["scoped_corpus"] = corpus
    return {"normalized_corpus": corpus, "metadata_audit_table": audit_rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
