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
  dictionary_input: { x: 120, y: 80 },
  corpus_input: { x: 120, y: 330 },
  merge_corpora: { x: 520, y: 330 },
  filter_by_metadata: { x: 760, y: 120 },
  deduplicate_documents: { x: 760, y: 330 },
  sample_corpus: { x: 760, y: 540 },
  split_corpus: { x: 900, y: 860 },
  bucket_by_time: { x: 1260, y: 860 },
  clean_text: { x: 900, y: 330 },
  normalize_text: { x: 1280, y: 330 },
  tokenize: { x: 1680, y: 330 },
  apply_dictionary_rules: { x: 2060, y: 330 },
  filter_terms: { x: 2460, y: 330 },
  frequency_statistics: { x: 2860, y: 80 },
  term_document_analysis: { x: 2860, y: 340 },
  term_year_analysis: { x: 2860, y: 600 },
  cooccurrence_analysis: { x: 2860, y: 860 },
  feature_term_selection: { x: 2860, y: 1120 },
  keyword_extraction: { x: 3240, y: 80 },
  keyword_clustering: { x: 3240, y: 340 },
  institution_keyword_analysis: { x: 3240, y: 600 },
  institution_topic_analysis: { x: 3240, y: 860 },
  document_clustering: { x: 3240, y: 1120 },
  save_csv: { x: 3620, y: 80 },
  save_xlsx: { x: 3620, y: 340 },
  save_png: { x: 3620, y: 600 },
  save_html_report: { x: 3620, y: 860 },
  note: { x: 4000, y: 120 },
  group: { x: 4000, y: 360 },
  load_project_corpus: { x: 120, y: 330 },
  filter_corpus: { x: 520, y: 330 },
  project_dictionary_set: { x: 120, y: 80 },
  analyze_corpus: { x: 2860, y: 330 },
  export_results: { x: 3620, y: 360 }
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

const builtinWorkflowNodeUiDefinitions: Record<WorkflowNodeType, WorkflowNodeUiDefinition> = {
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
  clean_text: {
    size: { w: 320, h: 230 },
    defaultConfig: (runtimeProfile) => ({ ...runtimeProfile.cleaning })
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
    (Object.entries(builtinWorkflowNodeSchema) as Array<[WorkflowNodeType, GeneratedWorkflowNodeSchema]>).map(
      ([nodeType, schema]) => {
        const uiDefinition = builtinWorkflowNodeUiDefinitions[nodeType];
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
