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
  clean_text: {
    label: "基础清洗",
    description: "去噪、清理空白并处理 HTML 与 URL。",
    category: "process",
    inputs: [{ port_id: "corpus_in", port_type: "CorpusTable", label: "语料输入" }],
    outputs: [{ port_id: "clean_corpus", port_type: "CleanCorpus", label: "清洗后语料" }],
    stepId: "cleaning"
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
