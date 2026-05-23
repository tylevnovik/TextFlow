import type { WorkflowNodeType, WorkflowPort } from "@textflow/shared-types";

export interface WorkflowSchemaPort extends WorkflowPort {
  result_bundle_key?: string;
  png_chart_ids?: string[];
  include_in_html_audit?: boolean;
}

export interface GeneratedWorkflowNodeSchema {
  label: string;
  description: string;
  category: "input" | "process" | "analysis" | "output" | "utility" | "legacy";
  singleton?: boolean;
  hidden_from_toolbox?: boolean;
  inputs: WorkflowSchemaPort[];
  outputs: WorkflowSchemaPort[];
  stepId: string;
}

export const builtinWorkflowNodeSchema: Record<WorkflowNodeType, GeneratedWorkflowNodeSchema> = {
  corpus_input: {
    label: "语料输入",
    description: "选择项目语料，并在节点内圈定本次处理的文档范围。",
    category: "input",
    inputs: [],
    outputs: [{ port_id: "corpus", port_type: "CorpusTable", label: "语料" }],
    stepId: "scope"
  },
  dictionary_input: {
    label: "词表输入",
    description: "引用当前项目绑定的词表资源。",
    category: "input",
    inputs: [],
    outputs: [{ port_id: "dictionary_set", port_type: "DictionarySet", label: "词表" }],
    stepId: "resource"
  },
  merge_corpora: {
    label: "合并语料",
    description: "把多路语料汇合成一路，供下游统一处理。",
    category: "process",
    hidden_from_toolbox: true,
    inputs: [{ port_id: "corpus_in", port_type: "CorpusTable", label: "输入语料", allow_multiple: true }],
    outputs: [{ port_id: "corpus", port_type: "CorpusTable", label: "合并后语料" }],
    stepId: "merge"
  },
  select_dictionary_tables: {
    label: "选择词表分表",
    description: "只激活当前运行所需的词表分表，不改动项目默认词表。",
    category: "process",
    inputs: [{ port_id: "dictionary_set_in", port_type: "DictionarySet", label: "词表输入" }],
    outputs: [{ port_id: "dictionary_set", port_type: "DictionarySet", label: "已筛选词表" }],
    stepId: "resource"
  },
  overlay_dictionary_rules: {
    label: "叠加临时词表规则",
    description: "按本次运行临时追加词表规则，不写回项目默认词表。",
    category: "process",
    inputs: [{ port_id: "dictionary_set_in", port_type: "DictionarySet", label: "词表输入" }],
    outputs: [{ port_id: "dictionary_set", port_type: "DictionarySet", label: "叠加后词表" }],
    stepId: "resource"
  },
  filter_by_metadata: {
    label: "按元数据筛选",
    description: "按机构、来源、年份或扩展元数据字段筛选当前语料。",
    category: "process",
    inputs: [{ port_id: "corpus_in", port_type: "CorpusTable", label: "语料输入" }],
    outputs: [{ port_id: "filtered_corpus", port_type: "CorpusTable", label: "筛选后语料" }],
    stepId: "scope"
  },
  deduplicate_documents: {
    label: "文档去重",
    description: "按指定字段组合移除重复文档，保持结果可复现。",
    category: "process",
    inputs: [{ port_id: "corpus_in", port_type: "CorpusTable", label: "语料输入" }],
    outputs: [{ port_id: "deduped_corpus", port_type: "CorpusTable", label: "去重后语料" }],
    stepId: "scope"
  },
  sample_corpus: {
    label: "语料抽样",
    description: "按固定随机种子抽取样本，支持数量或比例模式。",
    category: "process",
    inputs: [{ port_id: "corpus_in", port_type: "CorpusTable", label: "语料输入" }],
    outputs: [{ port_id: "sampled_corpus", port_type: "CorpusTable", label: "抽样后语料" }],
    stepId: "scope"
  },
  split_corpus: {
    label: "语料切分",
    description: "按命名分组输出语料切分分配表，而不是复制多份全文数据。",
    category: "analysis",
    inputs: [{ port_id: "corpus_in", port_type: "CorpusTable", label: "语料输入" }],
    outputs: [{ port_id: "split_assignment_table", port_type: "AnyTable", label: "切分分配表", result_bundle_key: "split_assignments" }],
    stepId: "analysis"
  },
  bucket_by_time: {
    label: "时间分桶",
    description: "把年份或时间字段映射到可复用的时间桶，便于后续比较。",
    category: "analysis",
    inputs: [{ port_id: "corpus_in", port_type: "CorpusTable", label: "语料输入" }],
    outputs: [{ port_id: "time_bucket_table", port_type: "AnyTable", label: "时间分桶表", result_bundle_key: "time_bucket_assignments" }],
    stepId: "analysis"
  },
  conditional_router: {
    label: "条件路由",
    description: "用受控字段条件把语料或结果表拆成匹配与未匹配两路，不执行任意脚本。",
    category: "process",
    inputs: [
      { port_id: "corpus_in", port_type: "CorpusTable", label: "语料输入" },
      { port_id: "table_in", port_type: "AnyTable", label: "表格输入" }
    ],
    outputs: [
      { port_id: "matched_corpus", port_type: "CorpusTable", label: "匹配语料" },
      { port_id: "unmatched_corpus", port_type: "CorpusTable", label: "未匹配语料" },
      { port_id: "matched_table", port_type: "AnyTable", label: "匹配表格" },
      { port_id: "unmatched_table", port_type: "AnyTable", label: "未匹配表格" },
      { port_id: "route_summary", port_type: "AnyTable", label: "路由摘要", result_bundle_key: "conditional_route_summary" }
    ],
    stepId: "scope"
  },
  result_gate: {
    label: "结果门禁",
    description: "根据上游结果表中的摘要指标决定是否放行下游表格。",
    category: "analysis",
    inputs: [
      { port_id: "metric_table_in", port_type: "AnyTable", label: "指标表" },
      { port_id: "payload_in", port_type: "AnyTable", label: "待放行表格" }
    ],
    outputs: [
      { port_id: "passed_table", port_type: "AnyTable", label: "放行表格" },
      { port_id: "blocked_table", port_type: "AnyTable", label: "拦截表格" },
      { port_id: "gate_summary", port_type: "AnyTable", label: "门禁摘要", result_bundle_key: "result_gate_summary" }
    ],
    stepId: "analysis"
  },
  manual_review_gate: {
    label: "人工复核门禁",
    description: "等待指定复核任务达到目标状态后再放行下游表格。",
    category: "process",
    inputs: [{ port_id: "payload_in", port_type: "AnyTable", label: "待复核表格" }],
    outputs: [
      { port_id: "approved_payload", port_type: "AnyTable", label: "已放行表格" },
      { port_id: "blocked_payload", port_type: "AnyTable", label: "待复核表格" },
      { port_id: "review_gate_summary", port_type: "AnyTable", label: "复核门禁摘要", result_bundle_key: "review_gate_summary" }
    ],
    stepId: "resource"
  },
  clean_text: {
    label: "基础清洗",
    description: "去噪、清理空白并处理 HTML 与 URL。",
    category: "process",
    inputs: [{ port_id: "corpus_in", port_type: "CorpusTable", label: "语料输入" }],
    outputs: [{ port_id: "clean_corpus", port_type: "CleanCorpus", label: "清洗后语料" }],
    stepId: "cleaning"
  },
  normalize_metadata: {
    label: "元数据标准化",
    description: "标准化机构、国家/地区、年份和类别字段。",
    category: "process",
    inputs: [{ port_id: "corpus_in", port_type: "CorpusTable", label: "语料输入" }],
    outputs: [
      { port_id: "normalized_corpus", port_type: "CorpusTable", label: "标准化后语料" },
      { port_id: "metadata_audit_table", port_type: "MetadataAuditTable", label: "元数据审计表", result_bundle_key: "metadata_audit_table", include_in_html_audit: true }
    ],
    stepId: "normalization"
  },
  normalize_text: {
    label: "统一写法",
    description: "统一时间、数字与正则替换后的文本表达。",
    category: "process",
    inputs: [{ port_id: "corpus_in", port_type: "CleanCorpus", label: "清洗后语料" }],
    outputs: [{ port_id: "normalized_corpus", port_type: "NormalizedCorpus", label: "标准化语料" }],
    stepId: "normalization"
  },
  tokenize: {
    label: "切词",
    description: "执行中英文切词，并尽量保留短语。",
    category: "process",
    inputs: [{ port_id: "corpus_in", port_type: "NormalizedCorpus", label: "标准化语料" }],
    outputs: [{ port_id: "token_corpus", port_type: "TokenCorpus", label: "Token 语料" }],
    stepId: "tokenization"
  },
  apply_dictionary_rules: {
    label: "套用词表",
    description: "按停用词、同义词、标准词和排除词重写 token。",
    category: "process",
    inputs: [
      { port_id: "token_corpus_in", port_type: "TokenCorpus", label: "Token 输入" },
      { port_id: "dictionary_set_in", port_type: "DictionarySet", label: "词表输入" }
    ],
    outputs: [
      { port_id: "token_corpus", port_type: "TokenCorpus", label: "规则处理后 Token" },
      {
        port_id: "audit_table",
        port_type: "AuditTable",
        label: "审计表",
        result_bundle_key: "audit_table",
        include_in_html_audit: true
      }
    ],
    stepId: "dictionary_application"
  },
  filter_terms: {
    label: "过滤词项",
    description: "去掉过短、过少或不适合分析的词项。",
    category: "process",
    inputs: [{ port_id: "token_corpus_in", port_type: "TokenCorpus", label: "Token 输入" }],
    outputs: [{ port_id: "filtered_token_corpus", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    stepId: "filtering"
  },
  focus_terms: {
    label: "聚焦词项",
    description: "用特征词或关键词结果收窄下游分析词项，降低共现网络和图计算规模。",
    category: "process",
    inputs: [
      { port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" },
      { port_id: "term_table_in", port_type: "AnyTable", label: "候选词表" }
    ],
    outputs: [
      { port_id: "focused_token_corpus", port_type: "FilteredTokenCorpus", label: "聚焦后词项" },
      { port_id: "focus_term_summary", port_type: "AnyTable", label: "聚焦摘要", result_bundle_key: "focus_term_summary", include_in_html_audit: true }
    ],
    stepId: "filtering"
  },
  frequency_statistics: {
    label: "词频统计",
    description: "生成高频词、文档频次和占比统计。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [
      {
        port_id: "frequency_table",
        port_type: "FrequencyTable",
        label: "词频表",
        result_bundle_key: "frequency_table",
        png_chart_ids: ["frequency_top_terms"]
      }
    ],
    stepId: "analysis"
  },
  term_document_analysis: {
    label: "词项文档分析",
    description: "查看词项与文档的对应关系和文档内词频。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [
      {
        port_id: "term_document_table",
        port_type: "TermDocumentTable",
        label: "词项文档表",
        result_bundle_key: "term_document_table"
      }
    ],
    stepId: "analysis"
  },
  term_year_analysis: {
    label: "词项年份分析",
    description: "分析词项按年份的变化趋势。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [
      {
        port_id: "term_year_table",
        port_type: "TermYearTable",
        label: "词项年份表",
        result_bundle_key: "term_year_table"
      }
    ],
    stepId: "analysis"
  },
  cooccurrence_analysis: {
    label: "共现分析",
    description: "统计词项在窗口内的共现关系。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [
      {
        port_id: "cooccurrence_table",
        port_type: "CooccurrenceTable",
        label: "共现表",
        result_bundle_key: "cooccurrence_table"
      }
    ],
    stepId: "analysis"
  },
  similarity_analysis: {
    label: "相似度计算",
    description: "基于词项表示计算文档间相似度，输出可审计的文档对得分。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [
      {
        port_id: "similarity_table",
        port_type: "AnyTable",
        label: "相似度表",
        result_bundle_key: "similarity_table"
      }
    ],
    stepId: "analysis"
  },
  group_compare: {
    label: "分组比较",
    description: "按指定分组字段比较词项在不同群组中的频次、文档覆盖和归一化占比。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [
      {
        port_id: "group_metric_table",
        port_type: "AnyTable",
        label: "分组比较表",
        result_bundle_key: "group_compare_table"
      }
    ],
    stepId: "analysis"
  },
  keyness_analysis: {
    label: "关键性分析",
    description: "计算目标分组相对基准分组的 LLR 和相对比率，识别区分性词项。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [
      {
        port_id: "keyness_table",
        port_type: "AnyTable",
        label: "关键性结果表",
        result_bundle_key: "keyness_table"
      }
    ],
    stepId: "analysis"
  },
  topic_modeling: {
    label: "主题建模",
    description: "使用 NMF 或 LDA 对语料做轻量主题建模，输出主题词项、文档主题和主题摘要。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [
      {
        port_id: "topic_term_table",
        port_type: "AnyTable",
        label: "主题词项表",
        result_bundle_key: "topic_term_table"
      },
      {
        port_id: "document_topic_table",
        port_type: "AnyTable",
        label: "文档主题表",
        result_bundle_key: "document_topic_table"
      },
      {
        port_id: "topic_summary_table",
        port_type: "AnyTable",
        label: "主题摘要表",
        result_bundle_key: "topic_summary_table"
      }
    ],
    stepId: "analysis"
  },
  cluster_evaluation: {
    label: "聚类评估",
    description: "基于现有聚类结果计算轮廓系数、Davies-Bouldin 指标和簇规模分布。",
    category: "analysis",
    inputs: [{ port_id: "document_cluster_table_in", port_type: "DocumentClusterTable", label: "文档聚类输入" }],
    outputs: [
      {
        port_id: "cluster_evaluation_table",
        port_type: "AnyTable",
        label: "聚类评估表",
        result_bundle_key: "cluster_evaluation_table"
      }
    ],
    stepId: "analysis"
  },
  join_results: {
    label: "连接结果表",
    description: "按命名键连接两张结果表，支持内连接与外连接等受控模式。",
    category: "analysis",
    inputs: [
      { port_id: "left_table_in", port_type: "AnyTable", label: "左表" },
      { port_id: "right_table_in", port_type: "AnyTable", label: "右表" }
    ],
    outputs: [
      {
        port_id: "joined_table",
        port_type: "AnyTable",
        label: "连接结果表",
        result_bundle_key: "joined_table"
      }
    ],
    stepId: "analysis"
  },
  feature_term_selection: {
    label: "特征词筛选",
    description: "从语料中筛出进入后续聚类和主题建模的特征词。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [
      {
        port_id: "feature_term_table",
        port_type: "FeatureTermTable",
        label: "特征词表",
        result_bundle_key: "selected_feature_terms"
      }
    ],
    stepId: "analysis"
  },
  keyword_extraction: {
    label: "关键词提取",
    description: "从语料中抽取项目级和文档级关键词。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [
      {
        port_id: "keyword_table",
        port_type: "KeywordTable",
        label: "关键词表",
        result_bundle_key: "keyword_result",
        png_chart_ids: ["project_keywords", "keyword_wordcloud"]
      }
    ],
    stepId: "analysis"
  },
  keyword_clustering: {
    label: "关键词聚类",
    description: "把关键词聚成主题簇，生成标签和代表词。",
    category: "analysis",
    inputs: [{ port_id: "feature_term_table_in", port_type: "FeatureTermTable", label: "特征词输入" }],
    outputs: [
      {
        port_id: "keyword_cluster_table",
        port_type: "KeywordClusterTable",
        label: "关键词聚类表",
        result_bundle_key: "keyword_cluster_result"
      }
    ],
    stepId: "analysis"
  },
  institution_keyword_analysis: {
    label: "机构关键词分析",
    description: "分析不同机构在关键词层面的出现与共现强度。",
    category: "analysis",
    inputs: [{ port_id: "keyword_table_in", port_type: "KeywordTable", label: "关键词输入" }],
    outputs: [
      {
        port_id: "institution_keyword_table",
        port_type: "InstitutionKeywordTable",
        label: "机构关键词表",
        result_bundle_key: "institution_keyword_cooccurrence"
      }
    ],
    stepId: "analysis"
  },
  institution_topic_analysis: {
    label: "机构主题分析",
    description: "分析机构与主题的关系分布。",
    category: "analysis",
    inputs: [{ port_id: "keyword_cluster_table_in", port_type: "KeywordClusterTable", label: "主题输入" }],
    outputs: [
      {
        port_id: "institution_topic_table",
        port_type: "InstitutionTopicTable",
        label: "机构主题表",
        result_bundle_key: "institution_topic_cooccurrence",
        png_chart_ids: ["institution_topic_heatmap"]
      }
    ],
    stepId: "analysis"
  },
  document_clustering: {
    label: "文档聚类",
    description: "对文档做向量聚类，生成散点结果与簇标签。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [
      {
        port_id: "document_cluster_table",
        port_type: "DocumentClusterTable",
        label: "文档聚类表",
        result_bundle_key: "clustering_result",
        png_chart_ids: ["document_clusters"]
      }
    ],
    stepId: "analysis"
  },
  build_network: {
    label: "构建网络",
    description: "从共现表构建词项网络。",
    category: "analysis",
    inputs: [{ port_id: "cooccurrence_table_in", port_type: "CooccurrenceTable", label: "共现表输入" }],
    outputs: [
      { port_id: "graph_node_table", port_type: "GraphNodeTable", label: "网络节点表", result_bundle_key: "graph_node_table" },
      { port_id: "graph_edge_table", port_type: "GraphEdgeTable", label: "网络边表", result_bundle_key: "graph_edge_table" }
    ],
    stepId: "analysis"
  },
  graph_metrics: {
    label: "网络指标",
    description: "计算 PageRank、介数中心性等网络指标。",
    category: "analysis",
    inputs: [
      { port_id: "graph_node_table_in", port_type: "GraphNodeTable", label: "节点表输入" },
      { port_id: "graph_edge_table_in", port_type: "GraphEdgeTable", label: "边表输入" }
    ],
    outputs: [
      { port_id: "graph_metric_table", port_type: "GraphMetricTable", label: "网络指标表", result_bundle_key: "graph_metric_table" }
    ],
    stepId: "analysis"
  },
  community_detection: {
    label: "社区发现",
    description: "检测网络中的社区结构。",
    category: "analysis",
    inputs: [
      { port_id: "graph_node_table_in", port_type: "GraphNodeTable", label: "节点表输入" },
      { port_id: "graph_edge_table_in", port_type: "GraphEdgeTable", label: "边表输入" }
    ],
    outputs: [
      { port_id: "community_table", port_type: "CommunityTable", label: "社区表", result_bundle_key: "community_table" }
    ],
    stepId: "analysis"
  },
  main_path_analysis: {
    label: "主路径分析",
    description: "提取网络的主干路径。",
    category: "analysis",
    inputs: [
      { port_id: "graph_node_table_in", port_type: "GraphNodeTable", label: "节点表输入" },
      { port_id: "graph_edge_table_in", port_type: "GraphEdgeTable", label: "边表输入" }
    ],
    outputs: [
      { port_id: "main_path_table", port_type: "MainPathTable", label: "主路径表", result_bundle_key: "main_path_table" }
    ],
    stepId: "analysis"
  },
  link_prediction: {
    label: "链接预测",
    description: "预测网络中可能缺失的链接。",
    category: "analysis",
    inputs: [
      { port_id: "graph_node_table_in", port_type: "GraphNodeTable", label: "节点表输入" },
      { port_id: "graph_edge_table_in", port_type: "GraphEdgeTable", label: "边表输入" }
    ],
    outputs: [
      { port_id: "link_prediction_table", port_type: "LinkPredictionTable", label: "链接预测表", result_bundle_key: "link_prediction_table" }
    ],
    stepId: "analysis"
  },
  technology_indicators: {
    label: "技术指标",
    description: "基于词项年份趋势和网络指标计算新颖度、颠覆度和成熟度。",
    category: "analysis",
    inputs: [
      { port_id: "term_year_table_in", port_type: "TermYearTable", label: "词项年份表输入" },
      { port_id: "graph_metric_table_in", port_type: "GraphMetricTable", label: "网络指标输入" }
    ],
    outputs: [
      { port_id: "technology_indicator_table", port_type: "TechnologyIndicatorTable", label: "技术指标表", result_bundle_key: "technology_indicator_table" }
    ],
    stepId: "analysis"
  },
  technology_classification: {
    label: "技术分类",
    description: "根据技术指标将词项分类为新兴、颠覆性、核心或衰退。",
    category: "analysis",
    inputs: [
      { port_id: "technology_indicator_table_in", port_type: "TechnologyIndicatorTable", label: "技术指标表输入" }
    ],
    outputs: [
      { port_id: "technology_classification_table", port_type: "TechnologyClassificationTable", label: "技术分类表", result_bundle_key: "technology_classification_table" }
    ],
    stepId: "analysis"
  },
  save_csv: {
    label: "保存 CSV",
    description: "把上游表格结果写成 CSV 文件。",
    category: "output",
    inputs: [{ port_id: "table_in", port_type: "AnyTable", label: "表格输入", allow_multiple: true }],
    outputs: [{ port_id: "artifact", port_type: "ExportArtifact", label: "导出产物" }],
    stepId: "export"
  },
  save_xlsx: {
    label: "保存 XLSX",
    description: "把上游表格结果整理成 Excel 文件。",
    category: "output",
    inputs: [{ port_id: "table_in", port_type: "AnyTable", label: "表格输入", allow_multiple: true }],
    outputs: [{ port_id: "artifact", port_type: "ExportArtifact", label: "导出产物" }],
    stepId: "export"
  },
  save_png: {
    label: "保存 PNG",
    description: "把上游分析结果按默认图表规则渲染为 PNG。",
    category: "output",
    inputs: [{ port_id: "render_in", port_type: "AnyRenderable", label: "图像输入", allow_multiple: true }],
    outputs: [{ port_id: "artifact", port_type: "ExportArtifact", label: "导出产物" }],
    stepId: "export"
  },
  save_html_report: {
    label: "保存 HTML 报告",
    description: "根据上游分析结果生成 HTML 报告。",
    category: "output",
    inputs: [{ port_id: "report_in", port_type: "AnyAnalysisResult", label: "报告输入", allow_multiple: true }],
    outputs: [{ port_id: "artifact", port_type: "ExportArtifact", label: "导出产物" }],
    stepId: "export"
  },
  note: {
    label: "注释",
    description: "给画布上的某段流程添加说明。",
    category: "utility",
    inputs: [],
    outputs: [],
    stepId: "utility"
  },
  group: {
    label: "分组",
    description: "用于整理节点区域和视觉分组。",
    category: "utility",
    inputs: [],
    outputs: [],
    stepId: "utility"
  },
  load_project_corpus: {
    label: "读取项目语料",
    description: "旧版兼容节点：已由语料输入替代。",
    category: "legacy",
    hidden_from_toolbox: true,
    inputs: [],
    outputs: [{ port_id: "project_corpus", port_type: "ProjectCorpus", label: "项目语料" }],
    stepId: "resource"
  },
  filter_corpus: {
    label: "筛选处理对象",
    description: "旧版兼容节点：已并入语料输入节点。",
    category: "legacy",
    hidden_from_toolbox: true,
    inputs: [{ port_id: "project_corpus_in", port_type: "ProjectCorpus", label: "项目语料" }],
    outputs: [{ port_id: "scoped_corpus", port_type: "ScopedCorpus", label: "筛选后语料" }],
    stepId: "scope"
  },
  project_dictionary_set: {
    label: "项目词表",
    description: "旧版兼容节点：已由词表输入替代。",
    category: "legacy",
    hidden_from_toolbox: true,
    inputs: [],
    outputs: [{ port_id: "dictionary_set", port_type: "DictionarySet", label: "词表" }],
    stepId: "resource"
  },
  analyze_corpus: {
    label: "生成分析",
    description: "旧版兼容节点：已拆分为多个分析节点。",
    category: "legacy",
    hidden_from_toolbox: true,
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [
      { port_id: "analysis_bundle", port_type: "AnalysisBundle", label: "分析结果包" },
      { port_id: "audit_table", port_type: "AuditTable", label: "审计表" }
    ],
    stepId: "analysis"
  },
  export_results: {
    label: "导出结果",
    description: "旧版兼容节点：已拆分为多个输出节点。",
    category: "legacy",
    hidden_from_toolbox: true,
    inputs: [
      { port_id: "analysis_bundle_in", port_type: "AnalysisBundle", label: "分析结果" },
      { port_id: "audit_table_in", port_type: "AuditTable", label: "审计表" }
    ],
    outputs: [{ port_id: "export_bundle", port_type: "ExportBundle", label: "导出包" }],
    stepId: "export"
  }
};
