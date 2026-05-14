import type {
  ExportParameters,
  WorkflowRuntimeProfile,
  WorkflowStepId,
  RunScopeDefinition,
  WorkflowNodeType,
  WorkflowPort,
  WorkflowPortType
} from "@textflow/shared-types";
import { builtinWorkflowNodeSchema, type GeneratedWorkflowNodeSchema } from "./generatedBuiltinWorkflowNodeSchema";

export type WorkflowStepRole = WorkflowStepId | "scope" | "resource" | "merge" | "sink" | "utility";

const controlFlowWorkflowNodeSchema = {
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
      {
        port_id: "route_summary",
        port_type: "AnyTable",
        label: "路由摘要",
        result_bundle_key: "conditional_route_summary"
      }
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
      {
        port_id: "review_gate_summary",
        port_type: "AnyTable",
        label: "复核门禁摘要",
        result_bundle_key: "review_gate_summary"
      }
    ],
    stepId: "resource"
  }
} satisfies Partial<Record<WorkflowNodeType, GeneratedWorkflowNodeSchema>>;

const workflowNodeSchema = {
  ...builtinWorkflowNodeSchema,
  ...controlFlowWorkflowNodeSchema
} as Record<WorkflowNodeType, GeneratedWorkflowNodeSchema>;

export interface WorkflowCatalogPort extends WorkflowPort {
  result_bundle_key?: string;
  png_chart_ids?: string[];
  include_in_html_audit?: boolean;
}

export interface WorkflowNodeDefinition {
  label: string;
  description: string;
  category: "input" | "process" | "analysis" | "output" | "utility" | "legacy";
  singleton?: boolean;
  hidden_from_toolbox?: boolean;
  inputs: WorkflowCatalogPort[];
  outputs: WorkflowCatalogPort[];
  stepId: WorkflowStepRole;
  size?: { w: number; h: number };
  defaultConfig: (runtimeProfile: WorkflowRuntimeProfile) => Record<string, unknown>;
}

interface WorkflowNodeUiDefinition {
  size?: { w: number; h: number };
  defaultConfig: (runtimeProfile: WorkflowRuntimeProfile) => Record<string, unknown>;
}

export const corpusPortOrder: WorkflowPortType[] = [
  "CorpusTable",
  "ProjectCorpus",
  "ScopedCorpus",
  "CleanCorpus",
  "NormalizedCorpus",
  "TokenCorpus",
  "FilteredTokenCorpus"
];

export const defaultNodePositions: Partial<Record<WorkflowNodeType, { x: number; y: number }>> = {
  dictionary_input: { x: 120, y: 40 },
  select_dictionary_tables: { x: 640, y: 40 },
  overlay_dictionary_rules: { x: 1080, y: 40 },
  corpus_input: { x: 120, y: 480 },
  merge_corpora: { x: 640, y: 480 },
  filter_by_metadata: { x: 1080, y: 40 },
  deduplicate_documents: { x: 1080, y: 480 },
  sample_corpus: { x: 1080, y: 820 },
  split_corpus: { x: 1500, y: 1320 },
  bucket_by_time: { x: 1920, y: 1320 },
  conditional_router: { x: 2340, y: 1320 },
  result_gate: { x: 4920, y: 1320 },
  manual_review_gate: { x: 5340, y: 680 },
  clean_text: { x: 1500, y: 480 },
  normalize_metadata: { x: 640, y: 480 },
  normalize_text: { x: 1920, y: 480 },
  tokenize: { x: 2340, y: 480 },
  apply_dictionary_rules: { x: 2760, y: 480 },
  filter_terms: { x: 3180, y: 480 },
  frequency_statistics: { x: 3660, y: 40 },
  term_document_analysis: { x: 3660, y: 360 },
  term_year_analysis: { x: 3660, y: 680 },
  cooccurrence_analysis: { x: 3660, y: 1000 },
  feature_term_selection: { x: 3660, y: 1320 },
  group_compare: { x: 3660, y: 1640 },
  similarity_analysis: { x: 4080, y: 40 },
  keyword_extraction: { x: 4080, y: 360 },
  keyword_clustering: { x: 4080, y: 680 },
  topic_modeling: { x: 4080, y: 1000 },
  institution_keyword_analysis: { x: 4080, y: 1320 },
  keyness_analysis: { x: 4080, y: 1640 },
  institution_topic_analysis: { x: 4500, y: 40 },
  document_clustering: { x: 4500, y: 360 },
  build_network: { x: 4500, y: 680 },
  graph_metrics: { x: 4500, y: 1000 },
  community_detection: { x: 4500, y: 1320 },
  cluster_evaluation: { x: 4500, y: 1640 },
  main_path_analysis: { x: 4920, y: 40 },
  link_prediction: { x: 4920, y: 360 },
  technology_indicators: { x: 4920, y: 680 },
  technology_classification: { x: 4920, y: 1000 },
  join_results: { x: 4920, y: 1320 },
  save_csv: { x: 5340, y: 40 },
  save_xlsx: { x: 5340, y: 360 },
  save_png: { x: 5340, y: 680 },
  save_html_report: { x: 5340, y: 1000 },
  note: { x: 5760, y: 40 },
  group: { x: 5760, y: 360 },
  load_project_corpus: { x: 120, y: 480 },
  filter_corpus: { x: 640, y: 480 },
  project_dictionary_set: { x: 120, y: 40 },
  analyze_corpus: { x: 1080, y: 480 },
  export_results: { x: 1500, y: 480 }
};

export const executionOrder: WorkflowStepId[] = [
  "ingestion",
  "cleaning",
  "normalization",
  "tokenization",
  "dictionary_application",
  "filtering",
  "analysis",
  "export"
];

export const defaultRunScope = (runtimeProfile: WorkflowRuntimeProfile): RunScopeDefinition => ({
  ...runtimeProfile.run_scope,
  mode: runtimeProfile.run_scope?.mode ?? "all_documents",
  source_values: [...(runtimeProfile.run_scope?.source_values ?? [])],
  institution_values: [...(runtimeProfile.run_scope?.institution_values ?? [])],
  category_values: [...(runtimeProfile.run_scope?.category_values ?? [])],
  year_from: runtimeProfile.run_scope?.year_from ?? null,
  year_to: runtimeProfile.run_scope?.year_to ?? null,
  selected_doc_ids: [...(runtimeProfile.run_scope?.selected_doc_ids ?? [])]
});

export const defaultExport = (runtimeProfile: WorkflowRuntimeProfile): ExportParameters => ({
  ...runtimeProfile.export,
  export_csv: runtimeProfile.export?.export_csv ?? true,
  export_xlsx: runtimeProfile.export?.export_xlsx ?? true,
  export_png: runtimeProfile.export?.export_png ?? true,
  export_html_report: runtimeProfile.export?.export_html_report ?? true,
  include_audit: runtimeProfile.export?.include_audit ?? true,
  chart_dpi: runtimeProfile.export?.chart_dpi ?? 320,
  watermark_enabled: runtimeProfile.export?.watermark_enabled ?? false,
  watermark_text: runtimeProfile.export?.watermark_text ?? "TextFlow Studio"
});

const fallbackWorkflowNodeUiDefinition: WorkflowNodeUiDefinition = {
  size: { w: 320, h: 220 },
  defaultConfig: () => ({})
};

const builtinWorkflowNodeUiDefinitions: Partial<Record<WorkflowNodeType, WorkflowNodeUiDefinition>> = {
  corpus_input: {
    size: { w: 420, h: 340 },
    defaultConfig: (runtimeProfile) => ({
      resource_mode: "project_corpus",
      resource_id: "project:corpus",
      ...(defaultRunScope(runtimeProfile) as unknown as Record<string, unknown>)
    })
  },
  dictionary_input: {
    size: { w: 360, h: 360 },
    defaultConfig: () => ({
      resource_mode: "project_dictionary",
      resource_id: "project:dictionary_set",
      use_custom_lexicon: true,
      use_phrase_lexicon: true,
      apply_regex_rules: true,
      apply_standard_terms: true,
      apply_synonym_map: true,
      apply_near_synonym_map: true,
      apply_stopwords: true,
      apply_exclusion_terms: true
    })
  },
  select_dictionary_tables: {
    size: { w: 360, h: 320 },
    defaultConfig: () => ({
      selected_table_ids: [],
      selected_table_ids_text: ""
    })
  },
  overlay_dictionary_rules: {
    size: { w: 380, h: 320 },
    defaultConfig: () => ({
      overlay_rows: [
        {
          kind: "standard_terms",
          source: "llm",
          target: "large language model",
          enabled: true
        }
      ],
      overlay_rows_text: "standard_terms|llm|large language model|true"
    })
  },
  merge_corpora: {
    size: { w: 300, h: 210 },
    defaultConfig: () => ({ strategy: "append" })
  },
  filter_by_metadata: {
    size: { w: 340, h: 240 },
    defaultConfig: () => ({
      conditions: [{ field: "institution", operator: "in", values: ["OpenAI"] }]
    })
  },
  deduplicate_documents: {
    size: { w: 320, h: 220 },
    defaultConfig: () => ({
      dedupe_keys: ["title", "year"],
      strategy: "keep_first"
    })
  },
  sample_corpus: {
    size: { w: 320, h: 240 },
    defaultConfig: () => ({
      sample_mode: "random",
      sample_size: 200,
      sample_ratio: null,
      seed: 42
    })
  },
  split_corpus: {
    size: { w: 320, h: 240 },
    defaultConfig: () => ({
      split_strategy: "ratio",
      splits: [
        { name: "train", ratio: 0.7 },
        { name: "test", ratio: 0.3 }
      ],
      seed: 42
    })
  },
  bucket_by_time: {
    size: { w: 320, h: 220 },
    defaultConfig: () => ({
      field: "year",
      granularity: "year"
    })
  },
  conditional_router: {
    size: { w: 360, h: 280 },
    defaultConfig: () => ({
      source_kind: "corpus_metadata",
      field: "institution",
      operator: "in",
      values: ["OpenAI"],
      values_text: "OpenAI"
    })
  },
  result_gate: {
    size: { w: 360, h: 280 },
    defaultConfig: () => ({
      metric_artifact: "cluster_evaluation_table",
      metric_name: "silhouette_score",
      metric_name_field: "metric",
      metric_field: "value",
      operator: "gte",
      threshold: 0.5
    })
  },
  manual_review_gate: {
    size: { w: 360, h: 260 },
    defaultConfig: () => ({
      review_id: "",
      required_status: "resolved",
      on_missing: "block"
    })
  },
  clean_text: {
    size: { w: 320, h: 230 },
    defaultConfig: (runtimeProfile) => ({ ...runtimeProfile.cleaning })
  },
  normalize_metadata: {
    size: { w: 380, h: 320 },
    defaultConfig: () => ({
      institution_aliases_text: "",
      country_aliases_text: "CN|China\nUS|United States\nUSA|United States",
      category_aliases_text: "",
      split_delimiters: ";；|",
      keep_first_institution: true,
      year_source_field: "year"
    })
  },
  normalize_text: {
    size: { w: 330, h: 240 },
    defaultConfig: (runtimeProfile) => ({ ...runtimeProfile.normalization })
  },
  tokenize: {
    size: { w: 320, h: 230 },
    defaultConfig: (runtimeProfile) => ({ ...runtimeProfile.tokenization })
  },
  apply_dictionary_rules: {
    size: { w: 340, h: 240 },
    defaultConfig: (runtimeProfile) => ({ ...runtimeProfile.dictionary })
  },
  filter_terms: {
    size: { w: 320, h: 230 },
    defaultConfig: (runtimeProfile) => ({ ...runtimeProfile.filtering })
  },
  frequency_statistics: {
    size: { w: 280, h: 210 },
    defaultConfig: (runtimeProfile) => ({ top_n: runtimeProfile.analysis.top_n })
  },
  term_document_analysis: {
    size: { w: 300, h: 210 },
    defaultConfig: () => ({})
  },
  term_year_analysis: {
    size: { w: 280, h: 210 },
    defaultConfig: () => ({})
  },
  cooccurrence_analysis: {
    size: { w: 320, h: 230 },
    defaultConfig: (runtimeProfile) => ({
      cooccurrence_window: runtimeProfile.analysis.cooccurrence_window,
      min_cooccurrence: runtimeProfile.analysis.min_cooccurrence
    })
  },
  similarity_analysis: {
    size: { w: 340, h: 230 },
    defaultConfig: (runtimeProfile) => ({
      similarity_method: runtimeProfile.analysis.similarity_method,
      min_similarity: runtimeProfile.analysis.min_similarity,
      similarity_top_k: runtimeProfile.analysis.similarity_top_k,
      feature_term_count: runtimeProfile.analysis.feature_term_count
    })
  },
  group_compare: {
    size: { w: 360, h: 280 },
    defaultConfig: () => ({
      group_field: "institution",
      baseline_group: "OpenAI",
      comparison_groups: ["Anthropic", "Google"],
      comparison_groups_text: "Anthropic,Google",
      min_frequency: 1
    })
  },
  keyness_analysis: {
    size: { w: 360, h: 260 },
    defaultConfig: () => ({
      group_field: "institution",
      baseline_group: "OpenAI",
      comparison_group: "Anthropic",
      min_frequency: 2
    })
  },
  topic_modeling: {
    size: { w: 360, h: 260 },
    defaultConfig: (runtimeProfile) => ({
      topic_algorithm: runtimeProfile.analysis.topic_algorithm,
      topic_model_k: runtimeProfile.analysis.topic_model_k,
      top_terms_per_topic: 5
    })
  },
  cluster_evaluation: {
    size: { w: 320, h: 210 },
    defaultConfig: () => ({})
  },
  join_results: {
    size: { w: 360, h: 260 },
    defaultConfig: () => ({
      left_artifact: "frequency_table",
      right_artifact: "keyness_table",
      join_keys: ["term"],
      join_keys_text: "term",
      join_type: "inner"
    })
  },
  feature_term_selection: {
    size: { w: 320, h: 220 },
    defaultConfig: (runtimeProfile) => ({
      feature_term_count: runtimeProfile.analysis.feature_term_count
    })
  },
  keyword_extraction: {
    size: { w: 320, h: 220 },
    defaultConfig: (runtimeProfile) => ({
      top_k_per_doc: runtimeProfile.analysis.top_k_per_doc,
      top_k_project: runtimeProfile.analysis.top_k_project
    })
  },
  keyword_clustering: {
    size: { w: 320, h: 220 },
    defaultConfig: (runtimeProfile) => ({
      keyword_cluster_k: runtimeProfile.analysis.keyword_cluster_k,
      topic_model_k: runtimeProfile.analysis.topic_model_k
    })
  },
  institution_keyword_analysis: {
    size: { w: 320, h: 210 },
    defaultConfig: () => ({})
  },
  institution_topic_analysis: {
    size: { w: 300, h: 210 },
    defaultConfig: (runtimeProfile) => ({ topic_model_k: runtimeProfile.analysis.topic_model_k })
  },
  document_clustering: {
    size: { w: 300, h: 210 },
    defaultConfig: (runtimeProfile) => ({ document_cluster_k: runtimeProfile.analysis.document_cluster_k })
  },
  build_network: {
    size: { w: 340, h: 230 },
    defaultConfig: () => ({
      min_edge_weight: 1,
      max_edges: 5000
    })
  },
  graph_metrics: {
    size: { w: 320, h: 210 },
    defaultConfig: () => ({})
  },
  community_detection: {
    size: { w: 340, h: 230 },
    defaultConfig: () => ({
      community_method: "greedy_modularity"
    })
  },
  main_path_analysis: {
    size: { w: 360, h: 230 },
    defaultConfig: () => ({
      main_path_mode: "directed_citation_or_weighted_backbone"
    })
  },
  link_prediction: {
    size: { w: 340, h: 230 },
    defaultConfig: () => ({
      link_prediction_top_n: 200
    })
  },
  technology_indicators: {
    size: { w: 360, h: 230 },
    defaultConfig: () => ({
      indicator_current_year: null
    })
  },
  technology_classification: {
    size: { w: 380, h: 280 },
    defaultConfig: () => ({
      threshold_emerging_novelty: 0.65,
      threshold_emerging_growth: 1.5,
      threshold_disruptive: 0.65,
      threshold_core: 0.65,
      threshold_declining_growth: 0.75,
      threshold_declining_maturity: 0.4
    })
  },
  save_csv: {
    size: { w: 280, h: 210 },
    defaultConfig: () => ({ file_prefix: "tables", export_csv: true })
  },
  save_xlsx: {
    size: { w: 280, h: 210 },
    defaultConfig: () => ({ file_prefix: "tables", export_xlsx: true })
  },
  save_png: {
    size: { w: 300, h: 220 },
    defaultConfig: (runtimeProfile) => ({
      file_prefix: "charts",
      chart_dpi: defaultExport(runtimeProfile).chart_dpi
    })
  },
  save_html_report: {
    size: { w: 320, h: 230 },
    defaultConfig: (runtimeProfile) => ({
      file_prefix: "report",
      include_audit: defaultExport(runtimeProfile).include_audit
    })
  },
  note: {
    size: { w: 260, h: 160 },
    defaultConfig: () => ({ text: "备注" })
  },
  group: {
    size: { w: 280, h: 180 },
    defaultConfig: () => ({ title: "分组" })
  },
  load_project_corpus: {
    defaultConfig: () => ({})
  },
  filter_corpus: {
    defaultConfig: (runtimeProfile) => ({ ...(defaultRunScope(runtimeProfile) as unknown as Record<string, unknown>) })
  },
  project_dictionary_set: {
    defaultConfig: () => ({})
  },
  analyze_corpus: {
    defaultConfig: (runtimeProfile) => ({ ...runtimeProfile.analysis })
  },
  export_results: {
    defaultConfig: (runtimeProfile) => ({ ...defaultExport(runtimeProfile) })
  }
};

function buildBuiltinWorkflowNodeDefinitions(): Record<WorkflowNodeType, WorkflowNodeDefinition> {
  return Object.fromEntries(
    (Object.entries(workflowNodeSchema) as Array<[WorkflowNodeType, GeneratedWorkflowNodeSchema]>).map(
      ([nodeType, schema]) => {
        const uiDefinition = builtinWorkflowNodeUiDefinitions[nodeType] ?? fallbackWorkflowNodeUiDefinition;
        return [
          nodeType,
          {
            ...schema,
            size: uiDefinition.size,
            defaultConfig: uiDefinition.defaultConfig
          }
        ];
      }
    )
  ) as Record<WorkflowNodeType, WorkflowNodeDefinition>;
}

export function missingBuiltinWorkflowNodeUiDefinitionsForTest(): WorkflowNodeType[] {
  return (Object.keys(workflowNodeSchema) as WorkflowNodeType[]).filter(
    (nodeType) => !builtinWorkflowNodeUiDefinitions[nodeType]
  );
}

export const builtinWorkflowNodeDefinitions: Record<WorkflowNodeType, WorkflowNodeDefinition> =
  buildBuiltinWorkflowNodeDefinitions();

function workflowNodeEntries(): Array<[WorkflowNodeType, WorkflowNodeDefinition]> {
  return Object.entries(builtinWorkflowNodeDefinitions) as Array<[WorkflowNodeType, WorkflowNodeDefinition]>;
}

function collectOutputPortTypes(
  predicate: (port: WorkflowCatalogPort, nodeType: WorkflowNodeType, definition: WorkflowNodeDefinition) => boolean
): WorkflowPortType[] {
  const types = new Set<WorkflowPortType>();
  for (const [nodeType, definition] of workflowNodeEntries()) {
    for (const port of definition.outputs) {
      if (predicate(port, nodeType, definition)) {
        types.add(port.port_type);
      }
    }
  }
  return [...types];
}

export const legacyNodeTypes = new Set<WorkflowNodeType>(
  workflowNodeEntries()
    .filter(([, definition]) => definition.category === "legacy")
    .map(([nodeType]) => nodeType)
);

export const sinkNodeTypes = new Set<WorkflowNodeType>(
  workflowNodeEntries()
    .filter(([nodeType, definition]) => definition.category === "output" || nodeType === "export_results")
    .map(([nodeType]) => nodeType)
);

export const renderableSourceTypes = new Set<WorkflowPortType>([
  ...collectOutputPortTypes((port) => Boolean(port.png_chart_ids?.length)),
  "AnalysisBundle"
]);

export const tableSourceTypes = new Set<WorkflowPortType>(
  collectOutputPortTypes((port) => Boolean(port.result_bundle_key))
);

export const analysisResultTypes = new Set<WorkflowPortType>([
  ...tableSourceTypes,
  "AnalysisBundle"
]);

export function builtinWorkflowNodeDefinition(nodeType: WorkflowNodeType): WorkflowNodeDefinition | null {
  return builtinWorkflowNodeDefinitions[nodeType] ?? null;
}

export function builtinWorkflowNodeFrameForType(nodeType: WorkflowNodeType) {
  return builtinWorkflowNodeDefinition(nodeType)?.size ?? { w: 280, h: 210 };
}

export function builtinWorkflowNodeDescription(nodeType: WorkflowNodeType): string {
  return builtinWorkflowNodeDefinition(nodeType)?.description ?? "";
}

export function builtinWorkflowOptionalToolboxNodes(): WorkflowNodeType[] {
  return (Object.entries(builtinWorkflowNodeDefinitions) as Array<[WorkflowNodeType, WorkflowNodeDefinition]>)
    .filter(([, definition]) => !definition.hidden_from_toolbox)
    .sort((left, right) => left[1].category.localeCompare(right[1].category) || left[1].label.localeCompare(right[1].label, "zh-CN"))
    .map(([nodeType]) => nodeType);
}
