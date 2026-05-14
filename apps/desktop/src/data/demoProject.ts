// This file is a lightweight non-Tauri fallback and component-test fixture.
// Official built-in sample projects are created by the Python sidecar in
// services/python-engine/app/sample_projects.py.
// Do not mirror large public sample corpora here.
import type {
  CorpusItem,
  DictionaryCollection,
  DictionaryEntry,
  DictionaryKind,
  DictionarySet,
  DictionaryTableResource,
  FeatureTermRow,
  FrequencyRow,
  KeywordClusterRow,
  KeywordRow,
  ProjectManifest,
  ProjectSummary,
  RunRecord,
  WorkflowDefinition,
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

const dictionaryKindOrder: DictionaryKind[] = [
  "stopwords",
  "custom_lexicon",
  "phrase_lexicon",
  "synonym_map",
  "near_synonym_map",
  "standard_terms",
  "exclusion_terms",
  "regex_rules"
];

const dictionaryCollectionMeta: Record<DictionaryKind, { name: string; description: string }> = {
  stopwords: { name: "停用词", description: "过滤虚词、套话和无分析意义的常用词。" },
  custom_lexicon: { name: "自定义词典", description: "告诉切词器哪些术语与专名要整体保留。" },
  phrase_lexicon: { name: "短语词典", description: "把固定搭配或多词短语作为一个整体处理。" },
  synonym_map: { name: "同义词表", description: "归并别名、替代表达和区域说法。" },
  near_synonym_map: { name: "近义词表", description: "保留更宽松的扩展归并规则，按需启用。" },
  standard_terms: { name: "标准词库", description: "把词形和写法统一成固定标准词。" },
  exclusion_terms: { name: "排除词表", description: "整批排除当前课题不想保留的人名、地名或噪声词。" },
  regex_rules: { name: "Regex 规则", description: "在清洗和标准化阶段使用的正则规则。" }
};

function table(
  kind: DictionaryKind,
  id: string,
  name: string,
  items: Array<[string, string?, number?]>,
  options: Partial<Pick<DictionaryTableResource, "description" | "source_url" | "built_in" | "editable" | "enabled" | "tags">> = {}
): DictionaryTableResource {
  return {
    id,
    kind,
    name,
    version: "2.0.0",
    description: options.description ?? "",
    source_url: options.source_url,
    built_in: options.built_in ?? false,
    editable: options.editable ?? true,
    enabled: options.enabled ?? true,
    tags: options.tags ?? [],
    entries: makeEntries(items)
  };
}

function collection(kind: DictionaryKind, tables: DictionaryTableResource[]): DictionaryCollection {
  return {
    kind,
    name: dictionaryCollectionMeta[kind].name,
    description: dictionaryCollectionMeta[kind].description,
    tables
  };
}

function buildDictionarySheetsFromCollections(collections: Record<DictionaryKind, DictionaryCollection>): DictionarySet["sheets"] {
  return dictionaryKindOrder.reduce<DictionarySet["sheets"]>((acc, kind) => {
    const entries: DictionaryEntry[] = [];
    const seen = new Set<string>();
    for (const currentTable of collections[kind]?.tables ?? []) {
      if (!currentTable.enabled) {
        continue;
      }
      for (const entry of currentTable.entries) {
        if (!entry.enabled) {
          continue;
        }
        const signature = `${entry.source.toLowerCase()}::${String(entry.target ?? "").toLowerCase()}`;
        if (seen.has(signature)) {
          continue;
        }
        seen.add(signature);
        entries.push(entry);
      }
    }
    acc[kind] = {
      kind,
      name: dictionaryCollectionMeta[kind].name,
      version: "2.0.0",
      entries
    };
    return acc;
  }, {} as DictionarySet["sheets"]);
}

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
  version: "2.0.0",
  bound_to_project: true,
  collections: {
    stopwords: collection("stopwords", [
      table("stopwords", "stopwords-project-custom", "项目自定义", [["本文", undefined, 2]], {
        description: "项目内可直接编辑的停用词补充。"
      }),
      table("stopwords", "builtin-stopwords-zh-iso", "中文通用停用词（stopwords-iso）", [["的", undefined, 24], ["和", undefined, 19], ["以及", undefined, 7]], {
        description: "stopwords-iso 中文停用词基线。",
        source_url: "https://github.com/stopwords-iso/stopwords-zh/blob/master/stopwords-zh.json",
        built_in: true,
        editable: false
      }),
      table("stopwords", "builtin-stopwords-en-iso", "English Stopwords (stopwords-iso)", [["about", undefined, 5], ["between", undefined, 3], ["but", undefined, 4]], {
        description: "stopwords-iso English stopwords baseline.",
        source_url: "https://github.com/stopwords-iso/stopwords-en/blob/master/stopwords-en.json",
        built_in: true,
        editable: false
      })
    ]),
    custom_lexicon: collection("custom_lexicon", [
      table("custom_lexicon", "custom-lexicon-project-custom", "项目自定义", [["智能制造", undefined, 3], ["battery recycling", undefined, 1]], {
        description: "项目内术语补充。"
      }),
      table("custom_lexicon", "builtin-custom-lexicon-thuocl-it", "IT 常用术语（THUOCL）", [["字符串", undefined, 3], ["配置文件", undefined, 2], ["环境变量", undefined, 1]], {
        description: "THUOCL IT 词库中的常用术语示例。",
        source_url: "https://github.com/thunlp/THUOCL/blob/master/data/THUOCL_IT.txt",
        built_in: true,
        editable: false
      }),
      table("custom_lexicon", "builtin-custom-lexicon-thuocl-medical", "医疗常用术语（THUOCL）", [["医疗", undefined, 1], ["诊断", undefined, 1], ["康复", undefined, 1]], {
        description: "THUOCL 医疗词库中的常用术语示例。",
        source_url: "https://github.com/thunlp/THUOCL/blob/master/data/THUOCL_medical.txt",
        built_in: true,
        editable: false
      })
    ]),
    phrase_lexicon: collection("phrase_lexicon", [
      table("phrase_lexicon", "phrase-lexicon-project-custom", "项目自定义", [["supply chain", "supply_chain", 2], ["学术 规范", "学术规范", 1]], {
        description: "项目内固定短语。"
      }),
      table("phrase_lexicon", "builtin-phrase-lexicon-thuocl-chengyu", "常见成语短语（THUOCL）", [["实事求是", undefined, 0], ["引人注目", undefined, 0], ["层出不穷", undefined, 0]], {
        description: "THUOCL 成语词库示例，默认关闭。",
        source_url: "https://github.com/thunlp/THUOCL/blob/master/data/THUOCL_chengyu.txt",
        built_in: true,
        editable: false,
        enabled: false
      })
    ]),
    synonym_map: collection("synonym_map", [
      table("synonym_map", "synonym-map-project-custom", "项目自定义", [["generative ai", "生成式", 5], ["battery recycling", "battery_recycling", 1]], {
        description: "项目内同义词归并。"
      }),
      table("synonym_map", "builtin-synonym-opencc-common", "港台常用词归并（OpenCC）", [["軟體", "软件", 0], ["資料", "数据", 0], ["網路", "网络", 0]], {
        description: "OpenCC TWPhrasesRev 中的常见港台用词对照。",
        source_url: "https://github.com/BYVoid/OpenCC/blob/master/data/dictionary/TWPhrasesRev.txt",
        built_in: true,
        editable: false
      })
    ]),
    near_synonym_map: collection("near_synonym_map", [
      table("near_synonym_map", "near-synonym-map-project-custom", "项目自定义", [["文本挖掘", "分析", 2], ["知识抽取", "工艺知识", 1]], {
        description: "项目内近义归并规则。"
      }),
      table("near_synonym_map", "builtin-near-synonym-opencc-extended", "港台扩展近义写法（OpenCC）", [["雲端", "云端", 0], ["顯示卡", "显卡", 0], ["視訊", "视频", 0]], {
        description: "OpenCC 扩展对照，默认关闭。",
        source_url: "https://github.com/BYVoid/OpenCC/blob/master/data/dictionary/TWPhrasesRev.txt",
        built_in: true,
        editable: false,
        enabled: false
      })
    ]),
    standard_terms: collection("standard_terms", [
      table("standard_terms", "standard-terms-project-custom", "项目自定义", [["供应链", "supply_chain", 3], ["机构主题", "topic", 2]], {
        description: "项目内标准词归一。"
      }),
      table("standard_terms", "builtin-standard-opencc", "繁简与常见异体归一（OpenCC）", [["彷彿", "仿佛", 0], ["回覆", "回复", 0], ["傢俱", "家具", 0]], {
        description: "OpenCC 中常见词形归一映射。",
        source_url: "https://github.com/BYVoid/OpenCC/blob/master/data/dictionary/TSPhrases.txt",
        built_in: true,
        editable: false
      }),
      table("standard_terms", "builtin-standard-misspell", "English Common Misspellings (misspell)", [["abberivation", "abbreviation", 0], ["accademy", "academy", 0], ["abandonned", "abandoned", 0]], {
        description: "client9/misspell 中的英文拼写纠正规则。",
        source_url: "https://github.com/client9/misspell/blob/master/words.go",
        built_in: true,
        editable: false
      })
    ]),
    exclusion_terms: collection("exclusion_terms", [
      table("exclusion_terms", "exclusion-terms-project-custom", "项目自定义", [["etc", undefined, 1], ["misc", undefined, 0]], {
        description: "项目内排除词。"
      }),
      table("exclusion_terms", "builtin-exclusion-thuocl-historical", "历史人物名（THUOCL）", [["毛泽东", undefined, 0], ["孔子", undefined, 0], ["默克尔", undefined, 0]], {
        description: "THUOCL 历史人物名，默认关闭。",
        source_url: "https://github.com/thunlp/THUOCL/blob/master/data/THUOCL_lishimingren.txt",
        built_in: true,
        editable: false,
        enabled: false
      }),
      table("exclusion_terms", "builtin-exclusion-thuocl-locations", "地域实体名（THUOCL）", [["中国", undefined, 0], ["北京市", undefined, 0], ["深圳市", undefined, 0]], {
        description: "THUOCL 地名词库示例，默认关闭。",
        source_url: "https://github.com/thunlp/THUOCL/blob/master/data/THUOCL_diming.txt",
        built_in: true,
        editable: false,
        enabled: false
      })
    ]),
    regex_rules: collection("regex_rules", [
      table("regex_rules", "regex-rules-project-custom", "项目自定义", [["\\d{4}年", "YEAR_TOKEN", 3], ["https?://\\S+", "", 2]], {
        description: "项目内 Regex 规则。"
      })
    ])
  },
  sheets: {} as DictionarySet["sheets"]
};

dictionarySet.sheets = buildDictionarySheetsFromCollections(dictionarySet.collections);

const runRecord: RunRecord = {
  run_id: "run-20260416-1810",
  project_id: "project-demo",
  workflow_version: "1.0.0",
  workflow_id: "wf-default",
  workflow_name: "关键词与主题工作流",
  workflow_hash: "sha256:demo-wf-default",
  dictionary_version: "2.0.0",
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

const workflowDefinitions: WorkflowDefinition[] = [
  {
    workflow_id: "wf-default",
    name: "关键词与主题工作流",
    version: "1.0.0",
    graph_mode: "dag",
    source: "system_default",
    meta: {
      template_id: "keyword_topic",
      output_bundle_id: "full_report"
    },
    nodes: [
      {
        node_id: "node-load-project-corpus",
        node_type: "load_project_corpus",
        label: "读取项目语料",
        position: { x: 120, y: 220 },
        inputs: [],
        outputs: [{ port_id: "project_corpus", port_type: "ProjectCorpus" }],
        config: {},
        ui_state: { collapsed: false, bypassed: false },
        runtime_meta: { step_id: "resource", node_impl_version: "1.0.0" }
      },
      {
        node_id: "node-filter-corpus",
        node_type: "filter_corpus",
        label: "筛选处理对象",
        position: { x: 360, y: 220 },
        inputs: [{ port_id: "project_corpus_in", port_type: "ProjectCorpus" }],
        outputs: [{ port_id: "scoped_corpus", port_type: "ScopedCorpus" }],
        config: {
          mode: "filtered_subset",
          source_values: ["Journal of Digital Humanities", "IncoPat"],
          institution_values: [],
          category_values: [],
          year_from: 2024,
          year_to: 2025,
          selected_doc_ids: []
        },
        ui_state: { collapsed: false, bypassed: false },
        runtime_meta: { step_id: "scope", node_impl_version: "1.0.0" }
      },
      {
        node_id: "node-project-dictionary-set",
        node_type: "project_dictionary_set",
        label: "项目词表",
        position: { x: 600, y: 60 },
        inputs: [],
        outputs: [{ port_id: "dictionary_set", port_type: "DictionarySet" }],
        config: {},
        ui_state: { collapsed: true, bypassed: false },
        runtime_meta: { step_id: "resource", node_impl_version: "1.0.0" }
      },
      {
        node_id: "node-runtime-dictionary-overlay",
        node_type: "overlay_dictionary_rules",
        label: "运行时词表叠加",
        position: { x: 960, y: 60 },
        inputs: [{ port_id: "dictionary_set_in", port_type: "DictionarySet" }],
        outputs: [{ port_id: "dictionary_set", port_type: "DictionarySet" }],
        config: {
          overlay_rows_text: "standard_terms|large language model|LLM|true\nsynonym_map|generative ai|生成式|true"
        },
        ui_state: { collapsed: false, bypassed: false },
        runtime_meta: { step_id: "resource", node_impl_version: "1.0.0" }
      },
      {
        node_id: "node-clean-text",
        node_type: "clean_text",
        label: "基础清洗",
        position: { x: 600, y: 220 },
        inputs: [{ port_id: "corpus_in", port_type: "ScopedCorpus" }],
        outputs: [{ port_id: "clean_corpus", port_type: "CleanCorpus" }],
        config: {
          strip_html: true,
          strip_urls: true,
          normalize_whitespace: true,
          normalize_punctuation: true
        },
        ui_state: { collapsed: false, bypassed: false },
        runtime_meta: { step_id: "cleaning", node_impl_version: "1.0.0" }
      },
      {
        node_id: "node-normalize-text",
        node_type: "normalize_text",
        label: "统一写法",
        position: { x: 840, y: 220 },
        inputs: [{ port_id: "corpus_in", port_type: "CleanCorpus" }],
        outputs: [{ port_id: "normalized_corpus", port_type: "NormalizedCorpus" }],
        config: {
          apply_regex_rules: true,
          convert_traditional_to_simplified: false
        },
        ui_state: { collapsed: false, bypassed: false },
        runtime_meta: { step_id: "normalization", node_impl_version: "1.0.0" }
      },
      {
        node_id: "node-tokenize",
        node_type: "tokenize",
        label: "切词",
        position: { x: 1080, y: 220 },
        inputs: [{ port_id: "corpus_in", port_type: "NormalizedCorpus" }],
        outputs: [{ port_id: "token_corpus", port_type: "TokenCorpus" }],
        config: {
          language_mode: "mixed",
          use_custom_lexicon: true,
          use_phrase_lexicon: true
        },
        ui_state: { collapsed: false, bypassed: false },
        runtime_meta: { step_id: "tokenization", node_impl_version: "1.0.0" }
      },
      {
        node_id: "node-apply-dictionary-rules",
        node_type: "apply_dictionary_rules",
        label: "套用词表",
        position: { x: 1320, y: 220 },
        inputs: [
          { port_id: "token_corpus_in", port_type: "TokenCorpus" },
          { port_id: "dictionary_set_in", port_type: "DictionarySet" }
        ],
        outputs: [{ port_id: "token_corpus", port_type: "TokenCorpus" }],
        config: {
          apply_standard_terms: true,
          apply_synonym_map: true,
          apply_stopwords: true
        },
        ui_state: { collapsed: false, bypassed: false },
        runtime_meta: { step_id: "dictionary_application", node_impl_version: "1.0.0" }
      },
      {
        node_id: "node-filter-terms",
        node_type: "filter_terms",
        label: "过滤噪声",
        position: { x: 1560, y: 220 },
        inputs: [{ port_id: "token_corpus_in", port_type: "TokenCorpus" }],
        outputs: [{ port_id: "filtered_token_corpus", port_type: "FilteredTokenCorpus" }],
        config: {
          min_token_length: 2,
          min_term_frequency: 1
        },
        ui_state: { collapsed: false, bypassed: false },
        runtime_meta: { step_id: "filtering", node_impl_version: "1.0.0" }
      },
      {
        node_id: "node-analyze-corpus",
        node_type: "analyze_corpus",
        label: "生成分析",
        position: { x: 1800, y: 220 },
        inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus" }],
        outputs: [
          { port_id: "analysis_bundle", port_type: "AnalysisBundle" },
          { port_id: "audit_table", port_type: "AuditTable" }
        ],
        config: {
          feature_term_count: 1000,
          top_k_project: 100,
          topic_model_k: 3
        },
        ui_state: { collapsed: false, bypassed: false },
        runtime_meta: { step_id: "analysis", node_impl_version: "1.0.0" }
      },
      {
        node_id: "node-export-results",
        node_type: "export_results",
        label: "导出结果",
        position: { x: 2040, y: 220 },
        inputs: [
          { port_id: "analysis_bundle_in", port_type: "AnalysisBundle" },
          { port_id: "audit_table_in", port_type: "AuditTable" }
        ],
        outputs: [{ port_id: "export_bundle", port_type: "ExportBundle" }],
        config: {
          export_csv: true,
          export_xlsx: true,
          export_png: true,
          export_html_report: true
        },
        ui_state: { collapsed: false, bypassed: false },
        runtime_meta: { step_id: "export", node_impl_version: "1.0.0" }
      }
    ],
    edges: [
      { edge_id: "edge-1", from_node: "node-load-project-corpus", from_port: "project_corpus", to_node: "node-filter-corpus", to_port: "project_corpus_in" },
      { edge_id: "edge-2", from_node: "node-filter-corpus", from_port: "scoped_corpus", to_node: "node-clean-text", to_port: "corpus_in" },
      { edge_id: "edge-3", from_node: "node-clean-text", from_port: "clean_corpus", to_node: "node-normalize-text", to_port: "corpus_in" },
      { edge_id: "edge-4", from_node: "node-normalize-text", from_port: "normalized_corpus", to_node: "node-tokenize", to_port: "corpus_in" },
      { edge_id: "edge-5", from_node: "node-tokenize", from_port: "token_corpus", to_node: "node-apply-dictionary-rules", to_port: "token_corpus_in" },
      { edge_id: "edge-6", from_node: "node-project-dictionary-set", from_port: "dictionary_set", to_node: "node-runtime-dictionary-overlay", to_port: "dictionary_set_in" },
      { edge_id: "edge-6-overlay", from_node: "node-runtime-dictionary-overlay", from_port: "dictionary_set", to_node: "node-apply-dictionary-rules", to_port: "dictionary_set_in" },
      { edge_id: "edge-7", from_node: "node-apply-dictionary-rules", from_port: "token_corpus", to_node: "node-filter-terms", to_port: "token_corpus_in" },
      { edge_id: "edge-8", from_node: "node-filter-terms", from_port: "filtered_token_corpus", to_node: "node-analyze-corpus", to_port: "token_corpus_in" },
      { edge_id: "edge-9", from_node: "node-analyze-corpus", from_port: "analysis_bundle", to_node: "node-export-results", to_port: "analysis_bundle_in" },
      { edge_id: "edge-10", from_node: "node-analyze-corpus", from_port: "audit_table", to_node: "node-export-results", to_port: "audit_table_in" }
    ],
    groups: [],
    viewport: { x: 0, y: 0, zoom: 0.8 },
    created_at: now,
    updated_at: now
  }
];

const manifest: ProjectManifest = {
  id: "project-demo",
  schema_version: "2.0.0",
  name: "新能源与生成式语料示例项目",
  description: "用于展示导入、预处理、关键词筛选、机构主题分析和报告输出的 V1 样例。",
  created_at: "2026-04-16T17:30:00+08:00",
  updated_at: now,
  version: "0.2.0",
  source_files: [
    { id: "source-1", name: "literature_sample.xlsx", source_type: "xlsx", relative_path: "corpus/imported/literature_sample.xlsx", imported_at: now, row_count: 2 },
    { id: "source-2", name: "patent_sample.json", source_type: "json", relative_path: "corpus/imported/patent_sample.json", imported_at: now, row_count: 1 }
  ],
  corpus_resources: [
    {
      id: "resource-demo-mixed-corpus",
      name: "Demo mixed corpus import",
      source_files: ["source-1", "source-2"],
      fingerprint: "sha256:demo-mixed-corpus"
    }
  ],
  corpus_views: [
    {
      id: "view-cn-institutions-2024",
      name: "CN institutions 2024+",
      resource_ids: ["resource-demo-mixed-corpus"],
      filter_spec: { country_or_region: ["CN"], year: { operator: "gte", values: [2024] } },
      doc_ids: ["DOC-001", "DOC-003"]
    }
  ],
  ingestion_specs: [
    {
      id: "ingest-demo-literature",
      name: "Demo literature + patent fields",
      source_profile: "literature",
      field_mappings: [
        { source_field: "title", target_field: "title", required: true },
        { source_field: "abstract", target_field: "raw_text", required: true },
        { source_field: "year", target_field: "year" },
        { source_field: "institution", target_field: "institution" }
      ],
      text_build: { mode: "concat_fields", fields: ["title", "abstract"], delimiter: "\n\n", skip_empty: true },
      dedupe_rules: { keys: ["title", "year", "institution"] }
    }
  ],
  artifact_records: [
    {
      artifact_id: "artifact-demo-frequency",
      run_id: "run-20260416-1810",
      node_id: "node-analyze-corpus",
      kind: "table",
      path: "runs/run-20260416-1810/artifacts/artifact-demo-frequency.json",
      preview_path: "runs/run-20260416-1810/artifacts/artifact-demo-frequency.preview.json",
      row_count: frequencyRows.length
    },
    {
      artifact_id: "artifact-demo-report",
      run_id: "run-20260416-1810",
      node_id: "node-export-results",
      kind: "object",
      path: "runs/run-20260416-1810/artifacts/artifact-demo-report.json",
      preview_path: "runs/run-20260416-1810/artifacts/artifact-demo-report.preview.json",
      row_count: 1
    }
  ],
  review_tasks: [
    {
      review_id: "review-demo-llm-merge",
      project_id: "project-demo",
      review_type: "dictionary_overlay",
      status: "open",
      target_ref: { term: "large language model", dictionary_kind: "standard_terms" },
      title: "确认 LLM 标准词合并",
      description: "示例复核任务：确认运行时叠加规则是否应写回项目词表。",
      created_at: now,
      updated_at: now
    } as ProjectManifest["review_tasks"][number] & { title: string; description: string; created_at: string; updated_at: string }
  ],
  experiment_specs: [
    {
      experiment_id: "exp-demo-keyword-depth",
      name: "Keyword depth variants",
      workflow_id: "wf-default",
      variant_matrix: [
        { label: "baseline", node_overrides: { "node-analyze-corpus": { top_k_project: 100 } } },
        { label: "expanded-keywords", node_overrides: { "node-analyze-corpus": { top_k_project: 160 } } }
      ]
    }
  ],
  shared_resource_refs: [],
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
  workflow_definitions: workflowDefinitions,
  active_workflow_id: "wf-default",
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
    topic_summary_table: [
      { topic_id: 0, topic_label: "生成式写作 / 学术规范", representative_terms: ["生成式", "学术规范"], document_count: 1 },
      { topic_id: 1, topic_label: "专利供应链 / 回收", representative_terms: ["patent", "recycling"], document_count: 1 }
    ],
    topic_term_table: [
      { topic_id: 0, term: "生成式", weight: 0.42 },
      { topic_id: 1, term: "patent", weight: 0.38 }
    ],
    document_topic_table: [
      { doc_id: "DOC-001", topic_id: 0, score: 0.74 },
      { doc_id: "DOC-002", topic_id: 1, score: 0.69 }
    ],
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
    graph_node_table: [
      { node: "patent", weight: 3 },
      { node: "recycling", weight: 2 }
    ],
    graph_edge_table: [
      { source: "patent", target: "recycling", weight: 2 }
    ],
    graph_metric_table: [
      { node: "patent", degree: 2, pagerank: 0.31 },
      { node: "recycling", degree: 1, pagerank: 0.22 }
    ],
    community_table: [
      { node: "patent", community_id: 0 }
    ],
    main_path_table: [
      { source: "patent", target: "recycling", weight: 2, rank: 1 }
    ],
    link_prediction_table: [
      { source: "battery", target: "recycling", score: 0.48 }
    ],
    technology_indicator_table: [
      { term: "recycling", novelty_score: 0.7, growth_ratio: 1.6, disruption_score: 0.4, maturity_score: 0.3 }
    ],
    technology_classification_table: [
      { term: "recycling", technology_label: "emerging", confidence: 0.72 }
    ],
    metadata_audit_table: [
      { doc_id: "DOC-001", field: "institution", original_value: "Fudan Univ.", normalized_value: "复旦大学", rule: "alias" }
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
