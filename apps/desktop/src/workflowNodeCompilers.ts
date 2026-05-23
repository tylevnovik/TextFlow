import type {
  ExportParameters,
  WorkflowRuntimeProfile,
  WorkflowStepId,
  RunScopeDefinition,
  WorkflowNodeInstance
} from "@textflow/shared-types";

export interface WorkflowCompileContext {
  compiled: WorkflowRuntimeProfile;
  enabledSteps: Set<WorkflowStepId>;
  exportConfig: ExportParameters;
  activeNodeTypes: Set<string>;
}

export type WorkflowNodeCompiler = (context: WorkflowCompileContext, node: WorkflowNodeInstance) => void;

const analysisOutputFlagMap = {
  frequency_statistics: "include_frequency_statistics",
  term_document_analysis: "include_term_document_relations",
  term_year_analysis: "include_term_year_relations",
  cooccurrence_analysis: "include_cooccurrence_analysis",
  similarity_analysis: "include_similarity_analysis",
  feature_term_selection: "include_feature_term_selection",
  keyword_extraction: "include_keyword_extraction",
  keyword_clustering: "include_keyword_clustering",
  institution_keyword_analysis: "include_institution_keyword_analysis",
  institution_topic_analysis: "include_institution_topic_analysis",
  document_clustering: "include_document_clustering"
} as const;

const analysisOutputFlags = Object.values(analysisOutputFlagMap);

const executionOrder: WorkflowStepId[] = [
  "ingestion",
  "cleaning",
  "normalization",
  "tokenization",
  "dictionary_application",
  "filtering",
  "analysis",
  "export"
];

function defaultRunScope(runtimeProfile: WorkflowRuntimeProfile): RunScopeDefinition {
  return {
    ...runtimeProfile.run_scope,
    mode: runtimeProfile.run_scope?.mode ?? "all_documents",
    source_values: [...(runtimeProfile.run_scope?.source_values ?? [])],
    institution_values: [...(runtimeProfile.run_scope?.institution_values ?? [])],
    category_values: [...(runtimeProfile.run_scope?.category_values ?? [])],
    year_from: runtimeProfile.run_scope?.year_from ?? null,
    year_to: runtimeProfile.run_scope?.year_to ?? null,
    selected_doc_ids: [...(runtimeProfile.run_scope?.selected_doc_ids ?? [])]
  };
}

function defaultExport(runtimeProfile: WorkflowRuntimeProfile): ExportParameters {
  return {
    ...runtimeProfile.export,
    export_csv: runtimeProfile.export?.export_csv ?? true,
    export_xlsx: runtimeProfile.export?.export_xlsx ?? true,
    export_png: runtimeProfile.export?.export_png ?? true,
    export_html_report: runtimeProfile.export?.export_html_report ?? true,
    include_audit: runtimeProfile.export?.include_audit ?? true,
    chart_dpi: runtimeProfile.export?.chart_dpi ?? 320,
    watermark_enabled: runtimeProfile.export?.watermark_enabled ?? false,
    watermark_text: runtimeProfile.export?.watermark_text ?? "TextFlow Studio"
  };
}

function cloneRuntimeProfile(runtimeProfile: WorkflowRuntimeProfile): WorkflowRuntimeProfile {
  return {
    ...runtimeProfile,
    enabled_steps: [...runtimeProfile.enabled_steps],
    execution_order: [...runtimeProfile.execution_order],
    cleaning: { ...runtimeProfile.cleaning },
    normalization: { ...runtimeProfile.normalization },
    tokenization: { ...runtimeProfile.tokenization },
    dictionary: { ...runtimeProfile.dictionary },
    filtering: { ...runtimeProfile.filtering },
    analysis: { ...runtimeProfile.analysis },
    export: { ...defaultExport(runtimeProfile) },
    run_scope: defaultRunScope(runtimeProfile),
    nodes: [...runtimeProfile.nodes],
    edges: [...runtimeProfile.edges],
    node_configs: { ...runtimeProfile.node_configs }
  };
}

function resetExportFlags(exportConfig: ExportParameters): ExportParameters {
  return {
    ...exportConfig,
    export_csv: false,
    export_xlsx: false,
    export_png: false,
    export_html_report: false
  };
}

function classifyOutputBundle(exportConfig: ExportParameters): WorkflowRuntimeProfile["output_bundle_id"] {
  if (exportConfig.export_csv && exportConfig.export_xlsx && exportConfig.export_png && exportConfig.export_html_report && exportConfig.include_audit) {
    return "full_report";
  }
  if (exportConfig.export_csv && exportConfig.export_xlsx && !exportConfig.export_png && !exportConfig.export_html_report && exportConfig.include_audit) {
    return "tables_only";
  }
  if (!exportConfig.export_csv && !exportConfig.export_xlsx && exportConfig.export_png && exportConfig.export_html_report && !exportConfig.include_audit) {
    return "charts_and_report";
  }
  if (exportConfig.export_csv && !exportConfig.export_xlsx && !exportConfig.export_png && exportConfig.export_html_report && exportConfig.include_audit) {
    return "audit_archive";
  }
  return "custom";
}

function mergeRuntimeSection<T extends keyof WorkflowRuntimeProfile>(sectionId: T, stepId: WorkflowStepId): WorkflowNodeCompiler {
  return (context, node) => {
    const patch = node.config as Partial<WorkflowRuntimeProfile[T]>;
    context.compiled[sectionId] = {
      ...(context.compiled[sectionId] as Record<string, unknown>),
      ...patch
    } as WorkflowRuntimeProfile[T];
    context.enabledSteps.add(stepId);
  };
}

function enableAnalysisOutput(
  context: WorkflowCompileContext,
  nodeType: keyof typeof analysisOutputFlagMap,
  patch: Partial<WorkflowRuntimeProfile["analysis"]> = {}
) {
  context.compiled.analysis = {
    ...context.compiled.analysis,
    [analysisOutputFlagMap[nodeType]]: true,
    ...patch
  };
  context.enabledSteps.add("analysis");
}

const workflowNodeCompilers: Record<string, WorkflowNodeCompiler> = {
  corpus_input: (context, node) => {
    context.compiled.run_scope = {
      ...context.compiled.run_scope,
      ...(node.config as Partial<RunScopeDefinition>),
      source_values: [...((node.config.source_values as string[] | undefined) ?? context.compiled.run_scope.source_values)],
      institution_values: [...((node.config.institution_values as string[] | undefined) ?? context.compiled.run_scope.institution_values)],
      category_values: [...((node.config.category_values as string[] | undefined) ?? context.compiled.run_scope.category_values)],
      selected_doc_ids: [...((node.config.selected_doc_ids as string[] | undefined) ?? context.compiled.run_scope.selected_doc_ids)]
    };
  },
  filter_corpus: (context, node) => {
    context.compiled.run_scope = {
      ...context.compiled.run_scope,
      ...(node.config as Partial<RunScopeDefinition>),
      source_values: [...((node.config.source_values as string[] | undefined) ?? context.compiled.run_scope.source_values)],
      institution_values: [...((node.config.institution_values as string[] | undefined) ?? context.compiled.run_scope.institution_values)],
      category_values: [...((node.config.category_values as string[] | undefined) ?? context.compiled.run_scope.category_values)],
      selected_doc_ids: [...((node.config.selected_doc_ids as string[] | undefined) ?? context.compiled.run_scope.selected_doc_ids)]
    };
  },
  filter_by_metadata: () => {},
  deduplicate_documents: () => {},
  sample_corpus: () => {},
  select_dictionary_tables: () => {},
  overlay_dictionary_rules: () => {},
  split_corpus: (context) => {
    context.enabledSteps.add("analysis");
  },
  bucket_by_time: (context) => {
    context.enabledSteps.add("analysis");
  },
  dictionary_input: (context, node) => {
    context.compiled.tokenization = {
      ...context.compiled.tokenization,
      use_custom_lexicon: Boolean(node.config.use_custom_lexicon ?? context.compiled.tokenization.use_custom_lexicon),
      use_phrase_lexicon: Boolean(node.config.use_phrase_lexicon ?? context.compiled.tokenization.use_phrase_lexicon)
    };
    context.compiled.normalization = {
      ...context.compiled.normalization,
      apply_regex_rules: Boolean(node.config.apply_regex_rules ?? context.compiled.normalization.apply_regex_rules)
    };
    context.compiled.dictionary = {
      ...context.compiled.dictionary,
      apply_standard_terms: Boolean(node.config.apply_standard_terms ?? context.compiled.dictionary.apply_standard_terms),
      apply_synonym_map: Boolean(node.config.apply_synonym_map ?? context.compiled.dictionary.apply_synonym_map),
      apply_near_synonym_map: Boolean(node.config.apply_near_synonym_map ?? context.compiled.dictionary.apply_near_synonym_map),
      apply_stopwords: Boolean(node.config.apply_stopwords ?? context.compiled.dictionary.apply_stopwords),
      apply_exclusion_terms: Boolean(node.config.apply_exclusion_terms ?? context.compiled.dictionary.apply_exclusion_terms)
    };
  },
  clean_text: mergeRuntimeSection("cleaning", "cleaning"),
  normalize_text: mergeRuntimeSection("normalization", "normalization"),
  tokenize: mergeRuntimeSection("tokenization", "tokenization"),
  apply_dictionary_rules: mergeRuntimeSection("dictionary", "dictionary_application"),
  filter_terms: mergeRuntimeSection("filtering", "filtering"),
  focus_terms: (context) => {
    context.enabledSteps.add("filtering");
  },
  analyze_corpus: (context, node) => {
    context.compiled.analysis = {
      ...context.compiled.analysis,
      ...Object.fromEntries(analysisOutputFlags.map((flag) => [flag, true])),
      ...(node.config as Partial<WorkflowRuntimeProfile["analysis"]>)
    };
    context.enabledSteps.add("analysis");
  },
  frequency_statistics: (context, node) => {
    enableAnalysisOutput(context, "frequency_statistics", {
      top_n: Number(node.config.top_n ?? context.compiled.analysis.top_n)
    });
  },
  term_document_analysis: (context) => {
    enableAnalysisOutput(context, "term_document_analysis");
  },
  term_year_analysis: (context) => {
    enableAnalysisOutput(context, "term_year_analysis");
  },
  cooccurrence_analysis: (context, node) => {
    enableAnalysisOutput(context, "cooccurrence_analysis", {
      cooccurrence_window: Number(node.config.cooccurrence_window ?? context.compiled.analysis.cooccurrence_window),
      min_cooccurrence: Number(node.config.min_cooccurrence ?? context.compiled.analysis.min_cooccurrence)
    });
  },
  similarity_analysis: (context, node) => {
    enableAnalysisOutput(context, "similarity_analysis", {
      similarity_method: "cosine",
      min_similarity: Number(node.config.min_similarity ?? context.compiled.analysis.min_similarity),
      similarity_top_k: Number(node.config.similarity_top_k ?? context.compiled.analysis.similarity_top_k)
    });
  },
  group_compare: (context) => {
    context.enabledSteps.add("analysis");
  },
  keyness_analysis: (context) => {
    context.enabledSteps.add("analysis");
  },
  topic_modeling: (context, node) => {
    context.compiled.analysis = {
      ...context.compiled.analysis,
      topic_algorithm: String(node.config.topic_algorithm ?? context.compiled.analysis.topic_algorithm) === "lda" ? "lda" : "nmf",
      topic_model_k: Number(node.config.topic_model_k ?? context.compiled.analysis.topic_model_k)
    };
    context.enabledSteps.add("analysis");
  },
  cluster_evaluation: (context) => {
    context.enabledSteps.add("analysis");
  },
  join_results: (context) => {
    context.enabledSteps.add("analysis");
  },
  feature_term_selection: (context, node) => {
    const rawValue = node.config.feature_term_count;
    enableAnalysisOutput(context, "feature_term_selection", {
      feature_term_count: String(rawValue ?? "") === "all"
        ? "all"
        : Number(rawValue ?? context.compiled.analysis.feature_term_count)
    });
  },
  keyword_extraction: (context, node) => {
    enableAnalysisOutput(context, "keyword_extraction", {
      top_k_per_doc: Number(node.config.top_k_per_doc ?? context.compiled.analysis.top_k_per_doc),
      top_k_project: Number(node.config.top_k_project ?? context.compiled.analysis.top_k_project)
    });
  },
  keyword_clustering: (context, node) => {
    enableAnalysisOutput(context, "keyword_clustering", {
      include_feature_term_selection: true,
      keyword_cluster_k: Number(node.config.keyword_cluster_k ?? context.compiled.analysis.keyword_cluster_k),
      topic_model_k: Number(node.config.topic_model_k ?? context.compiled.analysis.topic_model_k)
    });
  },
  institution_keyword_analysis: (context) => {
    enableAnalysisOutput(context, "institution_keyword_analysis", {
      include_keyword_extraction: true
    });
  },
  institution_topic_analysis: (context, node) => {
    enableAnalysisOutput(context, "institution_topic_analysis", {
      include_feature_term_selection: true,
      include_keyword_clustering: true,
      topic_model_k: Number(node.config.topic_model_k ?? context.compiled.analysis.topic_model_k)
    });
  },
  document_clustering: (context, node) => {
    enableAnalysisOutput(context, "document_clustering", {
      document_cluster_k: Number(node.config.document_cluster_k ?? context.compiled.analysis.document_cluster_k)
    });
  },
  save_csv: (context) => {
    context.exportConfig.export_csv = true;
    context.enabledSteps.add("export");
  },
  save_xlsx: (context) => {
    context.exportConfig.export_xlsx = true;
    context.enabledSteps.add("export");
  },
  save_png: (context, node) => {
    context.exportConfig.export_png = true;
    context.exportConfig.chart_dpi = Number(node.config.chart_dpi ?? context.exportConfig.chart_dpi);
    context.enabledSteps.add("export");
  },
  save_html_report: (context, node) => {
    context.exportConfig.export_html_report = true;
    context.exportConfig.include_audit = Boolean(node.config.include_audit ?? context.exportConfig.include_audit);
    context.enabledSteps.add("export");
  },
  export_results: (context, node) => {
    context.exportConfig = {
      ...context.exportConfig,
      ...(node.config as Partial<ExportParameters>)
    };
    context.enabledSteps.add("export");
  }
};

export function compileActiveWorkflowNodesIntoRuntimeProfile(
  activeNodes: WorkflowNodeInstance[],
  runtimeProfile: WorkflowRuntimeProfile
): WorkflowRuntimeProfile {
  const compiled = cloneRuntimeProfile(runtimeProfile);
  const activeNodeTypes = new Set(activeNodes.map((node) => node.node_type));
  const context: WorkflowCompileContext = {
    compiled,
    enabledSteps: new Set<WorkflowStepId>(["ingestion"]),
    exportConfig: resetExportFlags(defaultExport(compiled)),
    activeNodeTypes
  };

  context.compiled.analysis = {
    ...context.compiled.analysis,
    ...Object.fromEntries(analysisOutputFlags.map((flag) => [flag, false]))
  };

  for (const node of activeNodes) {
    if (node.ui_state?.bypassed) {
      continue;
    }
    workflowNodeCompilers[node.node_type]?.(context, node);
  }

  context.compiled.export = {
    ...context.compiled.export,
    ...context.exportConfig
  };
  context.compiled.execution_order = [...executionOrder];
  context.compiled.enabled_steps = executionOrder.filter((stepId) => context.enabledSteps.has(stepId));
  context.compiled.output_bundle_id = classifyOutputBundle(context.compiled.export);
  return context.compiled;
}
