import type {
  CorpusItem,
  DictionaryEntry,
  DictionaryKind,
  DictionarySet,
  FeatureTermRow,
  FrequencyRow,
  KeywordClusterRow,
  KeywordRow,
  ProjectManifest,
  ProjectSummary,
  RunRecord,
  WorkspaceSnapshot
} from "@textflow/shared-types";

const now = "2026-04-16T18:10:00+08:00";

const makeEntries = (items: Array<[string, string?, number?]>): DictionaryEntry[] =>
  items.map(([source, target, hits], index) => ({
    id: `${source}-${index}`,
    source,
    target,
    enabled: true,
    hits: hits ?? 0,
    tags: [],
    notes: "",
  }));

const sheet = (kind: DictionaryKind, name: string, items: Array<[string, string?, number?]>) => ({
  kind,
  name,
  version: "1.0.0",
  entries: makeEntries(items),
});

export const demoCorpus: CorpusItem[] = [
  {
    id: "doc-1",
    doc_id: "DOC-001",
    source_profile: "literature",
    title: "生成式 AI 在学术写作支持中的应用边界",
    raw_text: "生成式AI辅助写作正在改变研究流程，但也带来学术规范与引用透明度问题。",
    clean_text: "生成式ai辅助写作正在改变研究流程 但也带来学术规范与引用透明度问题",
    normalized_text: "生成式 ai 辅助 写作 正在 改变 研究 流程 但 也 带来 学术 规范 与 引用 透明度 问题",
    tokens: ["生成式", "ai", "辅助", "写作", "研究", "流程", "学术", "规范", "引用", "透明度", "问题"],
    phrase_hits: ["生成式 ai", "学术 规范"],
    filtered_tokens: ["生成式", "ai", "辅助", "写作", "研究", "流程", "学术", "规范", "引用", "透明度"],
    year: 2024,
    source: "Journal of Digital Humanities",
    author: "Wang; Li",
    institution: "复旦大学",
    country_or_region: "CN",
    category_or_tag: "academic writing",
    keyword_field: "generative ai; academic writing",
    extra_metadata: { source_db: "literature" },
    status: "ready",
    raw_hash: "hash-doc-1"
  },
  {
    id: "doc-2",
    doc_id: "DOC-002",
    source_profile: "wos",
    title: "Patent intelligence mining for battery supply chains",
    raw_text: "Battery recycling analytics reveals supply chain risks and patent hotspots across East Asia.",
    clean_text: "battery recycling analytics reveals supply chain risks and patent hotspots across east asia",
    normalized_text: "battery recycling analytics reveals supply chain risks patent hotspots east asia",
    tokens: ["battery", "recycling", "analytics", "reveals", "supply", "chain", "risks", "patent", "hotspots", "east", "asia"],
    phrase_hits: ["battery recycling", "supply chain"],
    filtered_tokens: ["battery", "recycling", "analytics", "supply_chain", "risks", "patent", "hotspots", "east_asia"],
    year: 2023,
    source: "WoS",
    author: "Smith; Tan",
    institution: "Tsinghua University",
    country_or_region: "CN",
    category_or_tag: "battery",
    keyword_field: "battery recycling; patent intelligence",
    extra_metadata: { accession_no: "WOS-7789" },
    status: "ready",
    raw_hash: "hash-doc-2"
  },
  {
    id: "doc-3",
    doc_id: "DOC-003",
    source_profile: "incopat",
    title: "智能制造语料中的工艺知识抽取",
    raw_text: "面向智能制造的工艺知识抽取，需要结合术语词典、规则治理和机构主题演化分析。",
    clean_text: "面向智能制造的工艺知识抽取 需要结合术语词典 规则治理和机构主题演化分析",
    normalized_text: "面向 智能制造 的 工艺知识 抽取 需要 结合 术语词典 规则治理 机构 主题 演化 分析",
    tokens: ["面向", "智能制造", "工艺知识", "抽取", "需要", "结合", "术语词典", "规则治理", "机构", "主题", "演化", "分析"],
    phrase_hits: ["智能制造", "工艺知识"],
    filtered_tokens: ["智能制造", "工艺知识", "抽取", "术语词典", "规则治理", "机构", "主题", "演化", "分析"],
    year: 2025,
    source: "IncoPat",
    author: "Chen",
    institution: "上海交通大学",
    country_or_region: "CN",
    category_or_tag: "manufacturing",
    keyword_field: "智能制造; 知识抽取",
    extra_metadata: { application_no: "CN20251234" },
    status: "ready",
    raw_hash: "hash-doc-3"
  }
];

const frequencyRows: FrequencyRow[] = [
  { term: "分析", tf: 6, df: 3, ratio: 0.14, word_length: 2, first_year: 2023, last_year: 2025, avg_per_doc: 2 },
  { term: "智能制造", tf: 4, df: 1, ratio: 0.09, word_length: 4, first_year: 2025, last_year: 2025, avg_per_doc: 4 },
  { term: "supply_chain", tf: 3, df: 1, ratio: 0.07, word_length: 12, first_year: 2023, last_year: 2023, avg_per_doc: 3 },
  { term: "生成式", tf: 3, df: 1, ratio: 0.07, word_length: 3, first_year: 2024, last_year: 2024, avg_per_doc: 3 },
  { term: "术语词典", tf: 2, df: 1, ratio: 0.05, word_length: 4, first_year: 2025, last_year: 2025, avg_per_doc: 2 }
];

const featureTerms: FeatureTermRow[] = [
  { term: "分析", score: 0.98, selected: true, source: "auto", rank: 1 },
  { term: "智能制造", score: 0.91, selected: true, source: "auto", rank: 2 },
  { term: "生成式", score: 0.89, selected: true, source: "auto", rank: 3 },
  { term: "supply_chain", score: 0.85, selected: true, source: "auto", rank: 4 },
  { term: "透明度", score: 0.82, selected: false, source: "manual", rank: 5 }
];

const keywordRows: KeywordRow[] = [
  { scope: "project", keyword: "分析", score: 0.98, rank: 1 },
  { scope: "project", keyword: "智能制造", score: 0.91, rank: 2 },
  { scope: "project", keyword: "生成式", score: 0.89, rank: 3 },
  { scope: "doc", doc_id: "DOC-001", keyword: "学术规范", score: 0.72, rank: 1 },
  { scope: "doc", doc_id: "DOC-002", keyword: "battery recycling", score: 0.7, rank: 1 }
];

const keywordClusters: KeywordClusterRow[] = [
  { term: "生成式", cluster_id: 0, distance_to_centroid: 0.12, is_label_term: true, topic_label: "生成式写作 / 学术规范" },
  { term: "学术规范", cluster_id: 0, distance_to_centroid: 0.2, is_label_term: true, topic_label: "生成式写作 / 学术规范" },
  { term: "supply_chain", cluster_id: 1, distance_to_centroid: 0.11, is_label_term: true, topic_label: "供应链 / 专利热点" },
  { term: "patent", cluster_id: 1, distance_to_centroid: 0.17, is_label_term: false, topic_label: "供应链 / 专利热点" },
  { term: "智能制造", cluster_id: 2, distance_to_centroid: 0.09, is_label_term: true, topic_label: "智能制造 / 工艺知识" }
];

const dictionarySet: DictionarySet = {
  id: "dict-v1",
  name: "默认词表集",
  version: "1.0.0",
  bound_to_project: true,
  sheets: {
    stopwords: sheet("stopwords", "停用词表", [["的", undefined, 24], ["和", undefined, 19], ["but", undefined, 4]]),
    custom_lexicon: sheet("custom_lexicon", "自定义词典", [["智能制造", undefined, 3], ["battery recycling", undefined, 1]]),
    phrase_lexicon: sheet("phrase_lexicon", "短语词典", [["supply chain", "supply_chain", 2], ["学术 规范", "学术规范", 1]]),
    synonym_map: sheet("synonym_map", "同义词表", [["generative ai", "生成式", 5], ["battery recycling", "battery_recycling", 1]]),
    near_synonym_map: sheet("near_synonym_map", "近义词表", [["文本挖掘", "分析", 2], ["知识抽取", "工艺知识", 1]]),
    standard_terms: sheet("standard_terms", "标准词库", [["供应链", "supply_chain", 3], ["机构主题", "topic", 2]]),
    exclusion_terms: sheet("exclusion_terms", "排除词表", [["etc", undefined, 1], ["misc", undefined, 0]]),
    regex_rules: sheet("regex_rules", "Regex 规则表", [["\\d{4}年", "YEAR_TOKEN", 3], ["https?://\\S+", "", 2]])
  }
};

const runRecord: RunRecord = {
  run_id: "run-20260416-1810",
  project_id: "project-demo",
  pipeline_version: "1.0.0",
  dictionary_version: "1.0.0",
  started_at: now,
  ended_at: "2026-04-16T18:12:00+08:00",
  status: "completed",
  warnings: ["1 篇文档在清洗后文本长度偏短，已保留并标记。"],
  errors: [],
  logs: [
    { timestamp: now, level: "info", step: "ingestion", message: "导入 3 篇文档，去重 0 篇。" },
    { timestamp: now, level: "info", step: "tokenization", message: "短语词典命中 4 次，自定义词典命中 3 次。" },
    { timestamp: now, level: "info", step: "analysis", message: "已生成频率、共现、关键词、聚类与机构主题结果。" }
  ],
  artifacts: [
    { step: "ingestion", output_files: ["metadata/corpus_table.csv"], record_count: 3, cache_hit: false },
    { step: "tokenization", output_files: ["intermediates/tokens.csv"], record_count: 3, cache_hit: false },
    { step: "analysis", output_files: ["outputs/frequency_table.csv", "outputs/report.html"], record_count: 9, cache_hit: false }
  ],
  params_snapshot_path: "runs/run-20260416-1810/params_snapshot.json",
  processed_document_count: 3,
  run_scope_summary: "处理对象为筛选资料：来源=Journal of Digital Humanities, IncoPat；年份=2024-2025，实际命中 3/3 篇文档。",
  recipe_id: "keyword_topic",
  output_bundle_id: "full_report",
  output_summary: "表格包、图表包、HTML 报告、审计表"
};

const manifest: ProjectManifest = {
  id: "project-demo",
  schema_version: "1.0.0",
  name: "新能源与生成式语料示例项目",
  description: "用于展示导入、预处理、关键词筛选、机构主题分析和报告输出的 V1 样例。",
  created_at: "2026-04-16T17:30:00+08:00",
  updated_at: now,
  version: "0.1.0",
  source_files: [
    { id: "source-1", name: "literature_sample.xlsx", source_type: "xlsx", relative_path: "corpus/imported/literature_sample.xlsx", imported_at: now, row_count: 2 },
    { id: "source-2", name: "patent_sample.json", source_type: "json", relative_path: "corpus/imported/patent_sample.json", imported_at: now, row_count: 1 }
  ],
  settings: {
    default_language: "mixed",
    preferred_theme: "paper",
    enable_auto_save: true,
    enable_update_check: false,
    default_export_formats: ["csv", "xlsx", "png", "html"]
  },
  paths: {
    root: "samples/projects/demo.tfproj",
    corpus_dir: "corpus",
    dictionaries_dir: "dictionaries",
    pipelines_dir: "pipelines",
    runs_dir: "runs",
    cache_dir: "cache",
    exports_dir: "exports"
  },
  import_template: {
    id: "template-literature",
    name: "文献混合模板",
    source_profile: "literature",
    description: "支持标题、摘要和 claims 拼接。",
    field_mappings: [
      { source_field: "title", target_field: "title", required: true },
      { source_field: "abstract", target_field: "raw_text", required: true },
      { source_field: "year", target_field: "year" },
      { source_field: "institution", target_field: "institution" }
    ],
    text_build: {
      mode: "concat_fields",
      fields: ["title", "abstract"],
      delimiter: "\n\n",
      skip_empty: true
    }
  },
  dictionary_set: dictionarySet,
  pipeline: {
    id: "pipeline-default",
    name: "默认 V1 流程",
    enabled_steps: ["ingestion", "cleaning", "normalization", "tokenization", "dictionary_application", "filtering", "analysis", "export"],
    cleaning: {
      strip_html: true,
      strip_urls: true,
      strip_email: false,
      strip_phone: false,
      normalize_whitespace: true,
      normalize_punctuation: true,
      full_half_width_normalize: true,
      lowercase_english: true,
      remove_emoji: false,
      remove_special_chars: false
    },
    normalization: {
      convert_traditional_to_simplified: false,
      normalize_numbers: false,
      normalize_time_expr: false,
      apply_regex_rules: true,
      regex_rule_priority: "rule_order"
    },
    tokenization: {
      language_mode: "mixed",
      tokenizer_backend: "default",
      use_custom_lexicon: true,
      use_phrase_lexicon: true,
      preserve_domain_phrases: true,
      split_hyphenated_terms: true,
      split_slash_terms: false,
      normalize_camel_case: true,
      keep_original_order: true,
      min_token_length_before_filter: 1
    },
    dictionary: {
      apply_standard_terms: true,
      apply_synonym_map: true,
      apply_near_synonym_map: true,
      apply_stopwords: true,
      apply_exclusion_terms: true,
      conflict_resolution: "priority"
    },
    filtering: {
      min_token_length: 2,
      filter_numeric_tokens: false,
      min_term_frequency: 1,
      filter_by_pos: false,
      keep_single_char_important_terms: true
    },
    analysis: {
      top_n: 200,
      cooccurrence_window: 5,
      min_cooccurrence: 2,
      feature_term_count: 1000,
      top_k_per_doc: 10,
      top_k_project: 100,
      topic_model_k: 3,
      keyword_cluster_k: 3,
      document_cluster_k: 3
    },
    export: {
      export_csv: true,
      export_xlsx: true,
      export_png: true,
      export_html_report: true,
      include_audit: true,
      chart_dpi: 320,
      watermark_enabled: false,
      watermark_text: "TextFlow Studio"
    },
    nodes: [],
    edges: [],
    node_configs: {},
    execution_order: ["ingestion", "cleaning", "normalization", "tokenization", "dictionary_application", "filtering", "analysis", "export"],
    run_scope: {
      mode: "filtered_subset",
      source_values: ["Journal of Digital Humanities", "IncoPat"],
      institution_values: [],
      category_values: [],
      year_from: 2024,
      year_to: 2025,
      selected_doc_ids: []
    },
    recipe_id: "keyword_topic",
    output_bundle_id: "full_report"
  },
  run_history: [runRecord],
  results: {
    frequency_table: frequencyRows,
    term_document_table: [
      { term: "分析", doc_id: "DOC-003", title: "智能制造语料中的工艺知识抽取", year: 2025, term_count_in_doc: 2, source: "IncoPat" },
      { term: "生成式", doc_id: "DOC-001", title: "生成式 AI 在学术写作支持中的应用边界", year: 2024, term_count_in_doc: 3, source: "Journal of Digital Humanities" }
    ],
    term_year_table: [
      { term: "分析", year: 2023, tf_in_year: 2, df_in_year: 1, ratio_in_year: 0.15 },
      { term: "分析", year: 2024, tf_in_year: 1, df_in_year: 1, ratio_in_year: 0.08 },
      { term: "分析", year: 2025, tf_in_year: 3, df_in_year: 1, ratio_in_year: 0.21 }
    ],
    cooccurrence_table: [
      { term_a: "生成式", term_b: "学术规范", cooccurrence_count: 3, score: 0.8 },
      { term_a: "supply_chain", term_b: "patent", cooccurrence_count: 2, score: 0.75 },
      { term_a: "智能制造", term_b: "工艺知识", cooccurrence_count: 4, score: 0.91 }
    ],
    selected_feature_terms: featureTerms,
    keyword_result: keywordRows,
    keyword_cluster_result: keywordClusters,
    institution_keyword_cooccurrence: [
      { institution: "复旦大学", keyword: "学术规范", cooccurrence_count: 2, year: 2024, score: 0.62 },
      { institution: "上海交通大学", keyword: "智能制造", cooccurrence_count: 3, year: 2025, score: 0.88 }
    ],
    institution_topic_cooccurrence: [
      { institution: "复旦大学", topic_id: 0, topic_label: "生成式写作 / 学术规范", cooccurrence_count: 2, representative_terms: ["生成式", "学术规范"], year: 2024 },
      { institution: "上海交通大学", topic_id: 2, topic_label: "智能制造 / 工艺知识", cooccurrence_count: 3, representative_terms: ["智能制造", "工艺知识"], year: 2025 }
    ],
    clustering_result: [
      { doc_id: "DOC-001", cluster_id: 0, x: -0.4, y: 0.3, title: "生成式 AI 在学术写作支持中的应用边界", year: 2024, source: "Journal of Digital Humanities" },
      { doc_id: "DOC-002", cluster_id: 1, x: 0.6, y: 0.4, title: "Patent intelligence mining for battery supply chains", year: 2023, source: "WoS" },
      { doc_id: "DOC-003", cluster_id: 2, x: 0.1, y: -0.5, title: "智能制造语料中的工艺知识抽取", year: 2025, source: "IncoPat" }
    ],
    audit_table: [
      { doc_id: "DOC-001", position: 1, source_term: "generative ai", target_term: "生成式", rule_type: "synonym_map", rule_source: "synonym_map.csv", rule_key: "generative ai", action: "replace" },
      { doc_id: "DOC-002", position: 4, source_term: "supply chain", target_term: "supply_chain", rule_type: "phrase_lexicon", rule_source: "phrase_lexicon.csv", rule_key: "supply chain", action: "replace" }
    ],
    report_files: ["runs/run-20260416-1810/report/report.html", "runs/run-20260416-1810/charts/frequency_trend.png"]
  }
};

export const demoProjectSummary: ProjectSummary = {
  id: manifest.id,
  name: manifest.name,
  description: manifest.description,
  path: "C:/Users/demo/Documents/TextFlow/demo.tfproj",
  updated_at: manifest.updated_at,
  document_count: demoCorpus.length,
  run_count: manifest.run_history.length
};

export const demoWorkspace: WorkspaceSnapshot = {
  recent_projects: [demoProjectSummary],
  current_project: manifest,
  corpus: demoCorpus,
  selected_run: runRecord
};

export const createSimulatedRun = (): RunRecord => ({
  ...runRecord,
  run_id: `run-${Date.now()}`,
  started_at: new Date().toISOString(),
  ended_at: new Date(Date.now() + 2_000).toISOString(),
  logs: [
    { timestamp: new Date().toISOString(), level: "info", step: "cleaning", message: "已按当前参数完成清洗与标准化。" },
    { timestamp: new Date().toISOString(), level: "info", step: "analysis", message: "已刷新词频、关键词与机构主题分析。" }
  ]
});
