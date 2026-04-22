from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from .defaults import default_pipeline

if TYPE_CHECKING:
    from .node_registry import NodeRegistryBuilder


def _port(
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


def _bool_param(param_id: str, label: str, default: bool, description: str = "") -> dict[str, Any]:
    return {
        "param_id": param_id,
        "label": label,
        "kind": "boolean",
        "default_value": default,
        "description": description,
    }


def _number_param(param_id: str, label: str, default: int | float | None, description: str = "") -> dict[str, Any]:
    return {
        "param_id": param_id,
        "label": label,
        "kind": "number",
        "default_value": default,
        "description": description,
    }


def _string_param(param_id: str, label: str, default: str | None, description: str = "") -> dict[str, Any]:
    return {
        "param_id": param_id,
        "label": label,
        "kind": "string",
        "default_value": default,
        "description": description,
    }


def _enum_param(
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


def _runtime(
    step_id: str,
    executor: str,
    *,
    cacheable: bool,
    previewable: bool,
    output_node: bool = False,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "executor": executor,
        "cacheable": cacheable,
        "previewable": previewable,
        "output_node": output_node,
    }


def _analysis_node(
    node_type: str,
    title: str,
    description: str,
    *,
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    params: list[dict[str, Any]],
    executor: str,
) -> dict[str, Any]:
    return {
        "type": node_type,
        "title": title,
        "category": "analysis",
        "description": description,
        "inputs": inputs,
        "outputs": outputs,
        "params": params,
        "runtime": _runtime("analysis", executor, cacheable=True, previewable=True),
    }


def build_builtin_node_definitions(pipeline: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    pipeline_definition = deepcopy(pipeline if isinstance(pipeline, dict) else default_pipeline())
    analysis = deepcopy(pipeline_definition.get("analysis") or {})
    export = deepcopy(pipeline_definition.get("export") or {})

    return [
        {
            "type": "corpus_input",
            "title": "语料输入",
            "category": "input",
            "description": "选择项目语料，并在节点内圈定本次处理的文档范围。",
            "inputs": [],
            "outputs": [_port("corpus", "CorpusTable", "语料")],
            "params": [
                _enum_param(
                    "resource_mode",
                    "资源来源",
                    "project_corpus",
                    [("project_corpus", "项目语料")],
                    "MVP 先固定引用项目语料。",
                ),
                _enum_param(
                    "mode",
                    "处理范围",
                    "all_documents",
                    [
                        ("all_documents", "全部文档"),
                        ("filtered_subset", "筛选子集"),
                        ("selected_documents", "指定文档"),
                    ],
                ),
                _number_param("year_from", "起始年份", pipeline_definition["run_scope"].get("year_from")),
                _number_param("year_to", "结束年份", pipeline_definition["run_scope"].get("year_to")),
            ],
            "runtime": _runtime("scope", "scope.select_corpus", cacheable=False, previewable=True),
        },
        {
            "type": "dictionary_input",
            "title": "词表输入",
            "category": "input",
            "description": "引用当前项目绑定的词表资源。",
            "inputs": [],
            "outputs": [_port("dictionary_set", "DictionarySet", "词表")],
            "params": [
                _enum_param(
                    "resource_mode",
                    "资源来源",
                    "project_dictionary",
                    [("project_dictionary", "项目词表")],
                ),
                _string_param("resource_id", "资源 ID", "project:dictionary_set"),
                _bool_param("use_custom_lexicon", "使用自定义词典", True),
                _bool_param("use_phrase_lexicon", "使用短语词典", True),
                _bool_param("apply_regex_rules", "启用 Regex 规则", True),
                _bool_param("apply_standard_terms", "启用标准词", True),
                _bool_param("apply_synonym_map", "启用同义词", True),
                _bool_param("apply_near_synonym_map", "启用近义词", True),
                _bool_param("apply_stopwords", "启用停用词", True),
                _bool_param("apply_exclusion_terms", "启用排除词", True),
            ],
            "runtime": _runtime("resource", "resource.load_dictionary", cacheable=True, previewable=True),
        },
        {
            "type": "merge_corpora",
            "title": "合并语料",
            "category": "process",
            "description": "把多路语料汇合成一路，供下游统一处理。",
            "hidden_from_toolbox": True,
            "inputs": [_port("corpus_in", "CorpusTable", "输入语料", allow_multiple=True)],
            "outputs": [_port("corpus", "CorpusTable", "合并后语料")],
            "params": [
                _enum_param("strategy", "合并策略", "append", [("append", "追加"), ("dedupe", "去重追加")]),
            ],
            "runtime": _runtime("merge", "graph.merge_corpora", cacheable=False, previewable=True),
        },
        {
            "type": "clean_text",
            "title": "基础清洗",
            "category": "process",
            "description": "去噪、清理空白并处理 HTML 与 URL。",
            "inputs": [_port("corpus_in", "CorpusTable", "语料输入")],
            "outputs": [_port("clean_corpus", "CleanCorpus", "清洗后语料")],
            "params": [
                _bool_param("strip_html", "去 HTML", bool(pipeline_definition["cleaning"].get("strip_html", True))),
                _bool_param("strip_urls", "去 URL", bool(pipeline_definition["cleaning"].get("strip_urls", True))),
                _bool_param("strip_email", "去邮箱", bool(pipeline_definition["cleaning"].get("strip_email", False))),
                _bool_param("strip_phone", "去手机号", bool(pipeline_definition["cleaning"].get("strip_phone", False))),
                _bool_param(
                    "normalize_whitespace",
                    "统一空白",
                    bool(pipeline_definition["cleaning"].get("normalize_whitespace", True)),
                ),
                _bool_param(
                    "normalize_punctuation",
                    "统一标点",
                    bool(pipeline_definition["cleaning"].get("normalize_punctuation", True)),
                ),
                _bool_param(
                    "full_half_width_normalize",
                    "全半角归一",
                    bool(pipeline_definition["cleaning"].get("full_half_width_normalize", True)),
                ),
                _bool_param(
                    "lowercase_english",
                    "英文小写",
                    bool(pipeline_definition["cleaning"].get("lowercase_english", True)),
                ),
                _bool_param("remove_emoji", "去表情", bool(pipeline_definition["cleaning"].get("remove_emoji", False))),
                _bool_param(
                    "remove_special_chars",
                    "去特殊字符",
                    bool(pipeline_definition["cleaning"].get("remove_special_chars", False)),
                ),
            ],
            "runtime": _runtime("cleaning", "pipeline.clean_text", cacheable=True, previewable=True),
        },
        {
            "type": "normalize_text",
            "title": "统一写法",
            "category": "process",
            "description": "统一时间、数字与正则替换后的文本表达。",
            "inputs": [_port("corpus_in", "CleanCorpus", "清洗后语料")],
            "outputs": [_port("normalized_corpus", "NormalizedCorpus", "标准化语料")],
            "params": [
                _bool_param(
                    "convert_traditional_to_simplified",
                    "繁转简",
                    bool(pipeline_definition["normalization"].get("convert_traditional_to_simplified", False)),
                ),
                _bool_param(
                    "normalize_numbers",
                    "数字归一",
                    bool(pipeline_definition["normalization"].get("normalize_numbers", False)),
                ),
                _bool_param(
                    "normalize_time_expr",
                    "时间表达归一",
                    bool(pipeline_definition["normalization"].get("normalize_time_expr", False)),
                ),
                _bool_param(
                    "apply_regex_rules",
                    "应用 Regex 规则",
                    bool(pipeline_definition["normalization"].get("apply_regex_rules", True)),
                ),
                _enum_param(
                    "regex_rule_priority",
                    "Regex 优先策略",
                    str(pipeline_definition["normalization"].get("regex_rule_priority", "rule_order")),
                    [("rule_order", "按规则顺序"), ("first_match", "命中首条后停止")],
                ),
            ],
            "runtime": _runtime("normalization", "pipeline.normalize_text", cacheable=True, previewable=True),
        },
        {
            "type": "tokenize",
            "title": "切词",
            "category": "process",
            "description": "执行中英文切词，并尽量保留短语。",
            "inputs": [_port("corpus_in", "NormalizedCorpus", "标准化语料")],
            "outputs": [_port("token_corpus", "TokenCorpus", "Token 语料")],
            "params": [
                _enum_param(
                    "language_mode",
                    "语言模式",
                    str(pipeline_definition["tokenization"].get("language_mode", "mixed")),
                    [("auto", "自动"), ("zh", "中文"), ("en", "英文"), ("mixed", "中英混合")],
                ),
                _enum_param(
                    "tokenizer_backend",
                    "切词引擎",
                    str(pipeline_definition["tokenization"].get("tokenizer_backend", "default")),
                    [("default", "默认")],
                ),
                _bool_param(
                    "use_custom_lexicon",
                    "使用自定义词典",
                    bool(pipeline_definition["tokenization"].get("use_custom_lexicon", True)),
                ),
                _bool_param(
                    "use_phrase_lexicon",
                    "使用短语词典",
                    bool(pipeline_definition["tokenization"].get("use_phrase_lexicon", True)),
                ),
                _bool_param(
                    "preserve_domain_phrases",
                    "保留领域短语",
                    bool(pipeline_definition["tokenization"].get("preserve_domain_phrases", True)),
                ),
                _bool_param(
                    "split_hyphenated_terms",
                    "拆分连字符",
                    bool(pipeline_definition["tokenization"].get("split_hyphenated_terms", True)),
                ),
                _bool_param(
                    "split_slash_terms",
                    "拆分斜杠词",
                    bool(pipeline_definition["tokenization"].get("split_slash_terms", False)),
                ),
                _bool_param(
                    "normalize_camel_case",
                    "拆分 CamelCase",
                    bool(pipeline_definition["tokenization"].get("normalize_camel_case", True)),
                ),
                _bool_param(
                    "keep_original_order",
                    "保留原始顺序",
                    bool(pipeline_definition["tokenization"].get("keep_original_order", True)),
                ),
                _number_param(
                    "min_token_length_before_filter",
                    "切词前最短长度",
                    int(pipeline_definition["tokenization"].get("min_token_length_before_filter", 1)),
                ),
            ],
            "runtime": _runtime("tokenization", "pipeline.tokenize", cacheable=True, previewable=True),
        },
        {
            "type": "apply_dictionary_rules",
            "title": "套用词表",
            "category": "process",
            "description": "按停用词、同义词、标准词和排除词重写 token。",
            "inputs": [
                _port("token_corpus_in", "TokenCorpus", "Token 输入"),
                _port("dictionary_set_in", "DictionarySet", "词表输入"),
            ],
            "outputs": [
                _port("token_corpus", "TokenCorpus", "规则处理后 Token"),
                _port(
                    "audit_table",
                    "AuditTable",
                    "审计表",
                    result_bundle_key="audit_table",
                    include_in_html_audit=True,
                ),
            ],
            "params": [
                _bool_param(
                    "apply_standard_terms",
                    "应用标准词",
                    bool(pipeline_definition["dictionary"].get("apply_standard_terms", True)),
                ),
                _bool_param(
                    "apply_synonym_map",
                    "应用同义词",
                    bool(pipeline_definition["dictionary"].get("apply_synonym_map", True)),
                ),
                _bool_param(
                    "apply_near_synonym_map",
                    "应用近义词",
                    bool(pipeline_definition["dictionary"].get("apply_near_synonym_map", True)),
                ),
                _bool_param(
                    "apply_stopwords",
                    "应用停用词",
                    bool(pipeline_definition["dictionary"].get("apply_stopwords", True)),
                ),
                _bool_param(
                    "apply_exclusion_terms",
                    "应用排除词",
                    bool(pipeline_definition["dictionary"].get("apply_exclusion_terms", True)),
                ),
                _enum_param(
                    "conflict_resolution",
                    "冲突处理",
                    str(pipeline_definition["dictionary"].get("conflict_resolution", "priority")),
                    [("priority", "按词表优先级"), ("first_match", "命中首条后停止")],
                ),
            ],
            "runtime": _runtime("dictionary_application", "pipeline.apply_dictionary_rules", cacheable=True, previewable=True),
        },
        {
            "type": "filter_terms",
            "title": "过滤词项",
            "category": "process",
            "description": "去掉过短、过少或不适合分析的词项。",
            "inputs": [_port("token_corpus_in", "TokenCorpus", "Token 输入")],
            "outputs": [_port("filtered_token_corpus", "FilteredTokenCorpus", "分析词项")],
            "params": [
                _number_param(
                    "min_term_frequency",
                    "最小词频",
                    int(pipeline_definition["filtering"].get("min_term_frequency", 1)),
                ),
                _number_param(
                    "min_token_length",
                    "最小词长",
                    int(pipeline_definition["filtering"].get("min_token_length", 2)),
                ),
                _bool_param(
                    "filter_numeric_tokens",
                    "过滤纯数字",
                    bool(pipeline_definition["filtering"].get("filter_numeric_tokens", False)),
                ),
                _bool_param(
                    "filter_by_pos",
                    "按词性过滤",
                    bool(pipeline_definition["filtering"].get("filter_by_pos", False)),
                ),
                _bool_param(
                    "keep_single_char_important_terms",
                    "保留关键单字词",
                    bool(pipeline_definition["filtering"].get("keep_single_char_important_terms", True)),
                ),
            ],
            "runtime": _runtime("filtering", "pipeline.filter_terms", cacheable=True, previewable=True),
        },
        _analysis_node(
            "frequency_statistics",
            "词频统计",
            "生成高频词、文档频次和占比统计。",
            inputs=[_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
            outputs=[
                _port(
                    "frequency_table",
                    "FrequencyTable",
                    "词频表",
                    result_bundle_key="frequency_table",
                    png_chart_ids=["frequency_top_terms"],
                )
            ],
            params=[_number_param("top_n", "Top N", int(analysis.get("top_n", 200)))],
            executor="analysis.frequency_statistics",
        ),
        _analysis_node(
            "term_document_analysis",
            "词项文档分析",
            "查看词项与文档的对应关系和文档内词频。",
            inputs=[_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
            outputs=[
                _port(
                    "term_document_table",
                    "TermDocumentTable",
                    "词项文档表",
                    result_bundle_key="term_document_table",
                )
            ],
            params=[],
            executor="analysis.term_document",
        ),
        _analysis_node(
            "term_year_analysis",
            "词项年份分析",
            "分析词项按年份的变化趋势。",
            inputs=[_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
            outputs=[
                _port(
                    "term_year_table",
                    "TermYearTable",
                    "词项年份表",
                    result_bundle_key="term_year_table",
                )
            ],
            params=[],
            executor="analysis.term_year",
        ),
        _analysis_node(
            "cooccurrence_analysis",
            "共现分析",
            "统计词项在窗口内的共现关系。",
            inputs=[_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
            outputs=[
                _port(
                    "cooccurrence_table",
                    "CooccurrenceTable",
                    "共现表",
                    result_bundle_key="cooccurrence_table",
                )
            ],
            params=[
                _number_param("cooccurrence_window", "共现窗口", int(analysis.get("cooccurrence_window", 5))),
                _number_param("min_cooccurrence", "最小共现次数", int(analysis.get("min_cooccurrence", 2))),
            ],
            executor="analysis.cooccurrence",
        ),
        _analysis_node(
            "feature_term_selection",
            "特征词筛选",
            "从语料中筛出进入后续聚类和主题建模的特征词。",
            inputs=[_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
            outputs=[
                _port(
                    "feature_term_table",
                    "FeatureTermTable",
                    "特征词表",
                    result_bundle_key="selected_feature_terms",
                )
            ],
            params=[
                _enum_param(
                    "feature_term_count",
                    "特征词规模",
                    str(analysis.get("feature_term_count", 1000)),
                    [("100", "Top 100"), ("500", "Top 500"), ("1000", "Top 1000"), ("all", "全部")],
                ),
            ],
            executor="analysis.feature_terms",
        ),
        _analysis_node(
            "keyword_extraction",
            "关键词提取",
            "从语料中抽取项目级和文档级关键词。",
            inputs=[_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
            outputs=[
                _port(
                    "keyword_table",
                    "KeywordTable",
                    "关键词表",
                    result_bundle_key="keyword_result",
                    png_chart_ids=["project_keywords", "keyword_wordcloud"],
                )
            ],
            params=[
                _number_param("top_k_per_doc", "每文档关键词数", int(analysis.get("top_k_per_doc", 10))),
                _number_param("top_k_project", "项目关键词数", int(analysis.get("top_k_project", 100))),
            ],
            executor="analysis.keyword_extraction",
        ),
        _analysis_node(
            "keyword_clustering",
            "关键词聚类",
            "把关键词聚成主题簇，生成标签和代表词。",
            inputs=[_port("feature_term_table_in", "FeatureTermTable", "特征词输入")],
            outputs=[
                _port(
                    "keyword_cluster_table",
                    "KeywordClusterTable",
                    "关键词聚类表",
                    result_bundle_key="keyword_cluster_result",
                )
            ],
            params=[
                _number_param("keyword_cluster_k", "关键词聚类数", int(analysis.get("keyword_cluster_k", 4))),
                _number_param("topic_model_k", "主题数量", int(analysis.get("topic_model_k", 4))),
            ],
            executor="analysis.keyword_clustering",
        ),
        _analysis_node(
            "institution_keyword_analysis",
            "机构关键词分析",
            "分析不同机构在关键词层面的出现与共现强度。",
            inputs=[_port("keyword_table_in", "KeywordTable", "关键词输入")],
            outputs=[
                _port(
                    "institution_keyword_table",
                    "InstitutionKeywordTable",
                    "机构关键词表",
                    result_bundle_key="institution_keyword_cooccurrence",
                )
            ],
            params=[],
            executor="analysis.institution_keyword",
        ),
        _analysis_node(
            "institution_topic_analysis",
            "机构主题分析",
            "分析机构与主题的关系分布。",
            inputs=[_port("keyword_cluster_table_in", "KeywordClusterTable", "主题输入")],
            outputs=[
                _port(
                    "institution_topic_table",
                    "InstitutionTopicTable",
                    "机构主题表",
                    result_bundle_key="institution_topic_cooccurrence",
                    png_chart_ids=["institution_topic_heatmap"],
                )
            ],
            params=[
                _number_param("topic_model_k", "主题数量", int(analysis.get("topic_model_k", 4))),
            ],
            executor="analysis.institution_topic",
        ),
        _analysis_node(
            "document_clustering",
            "文档聚类",
            "对文档做向量聚类，生成散点结果与簇标签。",
            inputs=[_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
            outputs=[
                _port(
                    "document_cluster_table",
                    "DocumentClusterTable",
                    "文档聚类表",
                    result_bundle_key="clustering_result",
                    png_chart_ids=["document_clusters"],
                )
            ],
            params=[
                _number_param("document_cluster_k", "文档聚类数", int(analysis.get("document_cluster_k", 4))),
            ],
            executor="analysis.document_clustering",
        ),
        {
            "type": "save_csv",
            "title": "保存 CSV",
            "category": "output",
            "description": "把上游表格结果写成 CSV 文件。",
            "inputs": [_port("table_in", "AnyTable", "表格输入", allow_multiple=True)],
            "outputs": [_port("artifact", "ExportArtifact", "导出产物")],
            "params": [_string_param("file_prefix", "文件名前缀", "tables")],
            "runtime": _runtime("export", "export.save_csv", cacheable=False, previewable=True, output_node=True),
        },
        {
            "type": "save_xlsx",
            "title": "保存 XLSX",
            "category": "output",
            "description": "把上游表格结果整理成 Excel 文件。",
            "inputs": [_port("table_in", "AnyTable", "表格输入", allow_multiple=True)],
            "outputs": [_port("artifact", "ExportArtifact", "导出产物")],
            "params": [_string_param("file_prefix", "文件名前缀", "tables")],
            "runtime": _runtime("export", "export.save_xlsx", cacheable=False, previewable=True, output_node=True),
        },
        {
            "type": "save_png",
            "title": "保存 PNG",
            "category": "output",
            "description": "把上游分析结果按默认图表规则渲染为 PNG。",
            "inputs": [_port("render_in", "AnyRenderable", "图像输入", allow_multiple=True)],
            "outputs": [_port("artifact", "ExportArtifact", "导出产物")],
            "params": [
                _string_param("file_prefix", "文件名前缀", "charts"),
                _number_param("chart_dpi", "PNG 分辨率（DPI）", int(export.get("chart_dpi", 320))),
            ],
            "runtime": _runtime("export", "export.save_png", cacheable=False, previewable=True, output_node=True),
        },
        {
            "type": "save_html_report",
            "title": "保存 HTML 报告",
            "category": "output",
            "description": "根据上游分析结果生成 HTML 报告。",
            "inputs": [_port("report_in", "AnyAnalysisResult", "报告输入", allow_multiple=True)],
            "outputs": [_port("artifact", "ExportArtifact", "导出产物")],
            "params": [
                _string_param("file_prefix", "文件名前缀", "report"),
                _bool_param("include_audit", "附带审计摘要", bool(export.get("include_audit", True))),
            ],
            "runtime": _runtime("export", "export.save_html_report", cacheable=False, previewable=True, output_node=True),
        },
        {
            "type": "note",
            "title": "注释",
            "category": "utility",
            "description": "给画布上的某段流程添加说明。",
            "inputs": [],
            "outputs": [],
            "params": [_string_param("text", "注释内容", "备注")],
            "runtime": _runtime("utility", "ui.note", cacheable=False, previewable=False),
        },
        {
            "type": "group",
            "title": "分组",
            "category": "utility",
            "description": "用于整理节点区域和视觉分组。",
            "inputs": [],
            "outputs": [],
            "params": [_string_param("title", "分组标题", "分组")],
            "runtime": _runtime("utility", "ui.group", cacheable=False, previewable=False),
        },
        {
            "type": "load_project_corpus",
            "title": "读取项目语料",
            "category": "legacy",
            "description": "旧版兼容节点：已由语料输入替代。",
            "hidden_from_toolbox": True,
            "inputs": [],
            "outputs": [_port("project_corpus", "ProjectCorpus", "项目语料")],
            "params": [],
            "runtime": _runtime("resource", "legacy.load_project_corpus", cacheable=False, previewable=False),
        },
        {
            "type": "filter_corpus",
            "title": "筛选处理对象",
            "category": "legacy",
            "description": "旧版兼容节点：已并入语料输入节点。",
            "hidden_from_toolbox": True,
            "inputs": [_port("project_corpus_in", "ProjectCorpus", "项目语料")],
            "outputs": [_port("scoped_corpus", "ScopedCorpus", "筛选后语料")],
            "params": [],
            "runtime": _runtime("scope", "legacy.filter_corpus", cacheable=False, previewable=False),
        },
        {
            "type": "project_dictionary_set",
            "title": "项目词表",
            "category": "legacy",
            "description": "旧版兼容节点：已由词表输入替代。",
            "hidden_from_toolbox": True,
            "inputs": [],
            "outputs": [_port("dictionary_set", "DictionarySet", "词表")],
            "params": [],
            "runtime": _runtime("resource", "legacy.project_dictionary_set", cacheable=False, previewable=False),
        },
        {
            "type": "analyze_corpus",
            "title": "生成分析",
            "category": "legacy",
            "description": "旧版兼容节点：已拆分为多个分析节点。",
            "hidden_from_toolbox": True,
            "inputs": [_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
            "outputs": [
                _port("analysis_bundle", "AnalysisBundle", "分析结果包"),
                _port("audit_table", "AuditTable", "审计表"),
            ],
            "params": [],
            "runtime": _runtime("analysis", "legacy.analyze_corpus", cacheable=True, previewable=False),
        },
        {
            "type": "export_results",
            "title": "导出结果",
            "category": "legacy",
            "description": "旧版兼容节点：已拆分为多个输出节点。",
            "hidden_from_toolbox": True,
            "inputs": [
                _port("analysis_bundle_in", "AnalysisBundle", "分析结果"),
                _port("audit_table_in", "AuditTable", "审计表"),
            ],
            "outputs": [_port("export_bundle", "ExportBundle", "导出包")],
            "params": [],
            "runtime": _runtime("export", "legacy.export_results", cacheable=False, previewable=False, output_node=True),
        },
    ]


def builtin_node_definition_map(pipeline: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    return {
        str(definition.get("type") or ""): definition
        for definition in build_builtin_node_definitions(pipeline)
        if definition.get("type")
    }


def register_builtin_node_definitions(builder: "NodeRegistryBuilder") -> None:
    for definition in build_builtin_node_definitions(builder.pipeline_definition):
        builder.register_definition(definition)
