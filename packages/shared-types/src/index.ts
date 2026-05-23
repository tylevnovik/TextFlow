export type SourceProfile =
  | "generic"
  | "literature"
  | "wos"
  | "scopus"
  | "patent"
  | "incopat"
  | "business_reserved";

export type WorkflowStepId =
  | "ingestion"
  | "cleaning"
  | "normalization"
  | "tokenization"
  | "dictionary_application"
  | "filtering"
  | "analysis"
  | "export";

export type DictionaryKind =
  | "stopwords"
  | "custom_lexicon"
  | "phrase_lexicon"
  | "synonym_map"
  | "near_synonym_map"
  | "standard_terms"
  | "exclusion_terms"
  | "regex_rules";

export type RunStatus = "idle" | "running" | "completed" | "failed" | "cancelled";

export type ExportFormat = "csv" | "xlsx" | "png" | "html";
export type WorkflowGraphMode = "dag";
export type WorkflowSource = "system_default" | "manual" | "template";
export type BuiltinWorkflowNodeType =
  | "corpus_input"
  | "dictionary_input"
  | "merge_corpora"
  | "select_dictionary_tables"
  | "overlay_dictionary_rules"
  | "filter_by_metadata"
  | "deduplicate_documents"
  | "sample_corpus"
  | "split_corpus"
  | "bucket_by_time"
  | "conditional_router"
  | "result_gate"
  | "manual_review_gate"
  | "load_project_corpus"
  | "filter_corpus"
  | "project_dictionary_set"
  | "clean_text"
  | "normalize_metadata"
  | "normalize_text"
  | "tokenize"
  | "apply_dictionary_rules"
  | "filter_terms"
  | "focus_terms"
  | "frequency_statistics"
  | "term_document_analysis"
  | "term_year_analysis"
  | "cooccurrence_analysis"
  | "similarity_analysis"
  | "group_compare"
  | "keyness_analysis"
  | "topic_modeling"
  | "cluster_evaluation"
  | "join_results"
  | "feature_term_selection"
  | "keyword_extraction"
  | "keyword_clustering"
  | "institution_keyword_analysis"
  | "institution_topic_analysis"
  | "document_clustering"
  | "build_network"
  | "graph_metrics"
  | "community_detection"
  | "main_path_analysis"
  | "link_prediction"
  | "technology_indicators"
  | "technology_classification"
  | "analyze_corpus"
  | "save_csv"
  | "save_xlsx"
  | "save_png"
  | "save_html_report"
  | "export_results"
  | "note"
  | "group";
export type WorkflowNodeType = BuiltinWorkflowNodeType | (string & {});
export type WorkflowPortType =
  | "CorpusResource"
  | "CorpusTable"
  | "ProjectCorpus"
  | "ScopedCorpus"
  | "DictionarySet"
  | "AnyTable"
  | "AnyAnalysisResult"
  | "AnyRenderable"
  | "CleanCorpus"
  | "NormalizedCorpus"
  | "TokenCorpus"
  | "FilteredTokenCorpus"
  | "FrequencyTable"
  | "TermDocumentTable"
  | "TermYearTable"
  | "CooccurrenceTable"
  | "FeatureTermTable"
  | "KeywordTable"
  | "KeywordClusterTable"
  | "InstitutionKeywordTable"
  | "InstitutionTopicTable"
  | "DocumentClusterTable"
  | "GraphNodeTable"
  | "GraphEdgeTable"
  | "GraphMetricTable"
  | "CommunityTable"
  | "MainPathTable"
  | "LinkPredictionTable"
  | "TechnologyIndicatorTable"
  | "TechnologyClassificationTable"
  | "MetadataAuditTable"
  | "AnalysisBundle"
  | "AuditTable"
  | "ExportBundle"
  | "ExportArtifact";

export interface RelativePathRef {
  relative_path: string;
}

export interface ProjectSettings {
  default_language: "auto" | "zh" | "en" | "mixed";
  preferred_theme: "paper" | "ink";
  enable_auto_save: boolean;
  enable_update_check: boolean;
  default_export_formats: ExportFormat[];
}

export interface ProjectPaths {
  root: string;
  corpus_dir: string;
  dictionaries_dir: string;
  runs_dir: string;
  cache_dir: string;
  exports_dir: string;
}

export interface TextBuildConfig {
  mode: "single_field" | "concat_fields";
  fields: string[];
  delimiter: string;
  skip_empty: boolean;
}

export interface FieldMappingRule {
  source_field: string;
  target_field:
    | "doc_id"
    | "source_type"
    | "title"
    | "raw_text"
    | "year"
    | "source"
    | "author"
    | "institution"
    | "country_or_region"
    | "category_or_tag"
    | "keyword_field"
    | "extra_metadata";
  required?: boolean;
  aliases?: string[];
}

export interface ImportTemplate {
  id: string;
  name: string;
  source_profile: SourceProfile;
  description?: string;
  field_mappings: FieldMappingRule[];
  text_build: TextBuildConfig;
}

export interface CorpusResource {
  id: string;
  name: string;
  source_files: string[];
  fingerprint: string;
}

export interface CorpusView {
  id: string;
  name: string;
  resource_ids: string[];
  filter_spec: Record<string, unknown>;
  doc_ids?: string[];
}

export interface IngestionSpec {
  id: string;
  name: string;
  source_profile: string;
  field_mappings: unknown[];
  text_build: Record<string, unknown>;
  dedupe_rules: Record<string, unknown>;
}

export interface ArtifactRecord {
  artifact_id: string;
  run_id: string;
  node_id: string;
  kind: string;
  path: string;
  preview_path?: string;
  row_count?: number;
  preview_rows?: number;
}

export interface ReviewTask {
  review_id: string;
  project_id: string;
  review_type: string;
  status: "open" | "resolved";
  target_ref: Record<string, string>;
}

export interface ExperimentSpec {
  experiment_id: string;
  name: string;
  workflow_id: string;
  variant_matrix: Record<string, unknown>[];
}

export interface SourceFileRecord {
  id: string;
  name: string;
  source_type: "txt" | "csv" | "xlsx" | "xls" | "json";
  relative_path: string;
  imported_at: string;
  row_count: number;
  retained_in_project?: boolean;
  redistribution?: "approved" | "restricted" | "unknown";
  license_note?: string;
  source_profile?: SourceProfile;
  seed_id?: string;
}

export interface CorpusItem {
  id: string;
  doc_id: string;
  source_profile: SourceProfile;
  title: string;
  raw_text: string;
  clean_text: string;
  normalized_text: string;
  tokens: string[];
  phrase_hits: string[];
  filtered_tokens: string[];
  year?: number | null;
  source?: string;
  author?: string;
  institution?: string;
  country_or_region?: string;
  category_or_tag?: string;
  keyword_field?: string;
  extra_metadata: Record<string, string | number | boolean | null>;
  status: "ready" | "warning" | "error";
  raw_hash?: string;
}

export interface DictionaryEntry {
  id: string;
  source: string;
  target?: string;
  tags?: string[];
  enabled: boolean;
  hits: number;
  notes?: string;
}

export interface DictionarySheet {
  kind: DictionaryKind;
  name: string;
  version: string;
  entries: DictionaryEntry[];
}

export interface DictionaryTableResource {
  id: string;
  kind: DictionaryKind;
  name: string;
  version: string;
  description?: string;
  source_url?: string;
  built_in: boolean;
  editable: boolean;
  enabled: boolean;
  tags?: string[];
  entries: DictionaryEntry[];
}

export interface DictionaryCollection {
  kind: DictionaryKind;
  name: string;
  description?: string;
  tables: DictionaryTableResource[];
}

export interface DictionarySet {
  id: string;
  name: string;
  version: string;
  bound_to_project: boolean;
  collections: Record<DictionaryKind, DictionaryCollection>;
  sheets: Record<DictionaryKind, DictionarySheet>;
}

export interface CleaningParameters {
  strip_html: boolean;
  strip_urls: boolean;
  strip_email: boolean;
  strip_phone: boolean;
  normalize_whitespace: boolean;
  normalize_punctuation: boolean;
  full_half_width_normalize: boolean;
  lowercase_english: boolean;
  remove_emoji: boolean;
  remove_special_chars: boolean;
}

export interface NormalizationParameters {
  convert_traditional_to_simplified: boolean;
  normalize_numbers: boolean;
  normalize_time_expr: boolean;
  apply_regex_rules: boolean;
  regex_rule_priority: "rule_order" | "first_match";
}

export interface TokenizationParameters {
  language_mode: "auto" | "zh" | "en" | "mixed";
  tokenizer_backend: "default";
  use_custom_lexicon: boolean;
  use_phrase_lexicon: boolean;
  preserve_domain_phrases: boolean;
  split_hyphenated_terms: boolean;
  split_slash_terms: boolean;
  normalize_camel_case: boolean;
  keep_original_order: boolean;
  min_token_length_before_filter: number;
  enable_ngrams: boolean;
  ngram_min: number;
  ngram_max: number;
}

export interface DictionaryParameters {
  apply_standard_terms: boolean;
  apply_synonym_map: boolean;
  apply_near_synonym_map: boolean;
  apply_stopwords: boolean;
  apply_exclusion_terms: boolean;
  conflict_resolution: "priority" | "first_match";
}

export interface FilteringParameters {
  min_token_length: number;
  filter_numeric_tokens: boolean;
  min_term_frequency: number;
  filter_by_pos: boolean;
  keep_single_char_important_terms: boolean;
}

export interface AnalysisParameters {
  top_n: number;
  cooccurrence_window: number;
  min_cooccurrence: number;
  feature_term_count: number | "all";
  top_k_per_doc: number;
  top_k_project: number;
  similarity_method: "cosine";
  min_similarity: number;
  similarity_top_k: number;
  topic_algorithm: "nmf" | "lda";
  topic_model_k: number;
  keyword_cluster_k: number;
  document_cluster_k: number;
  include_frequency_statistics: boolean;
  include_term_document_relations: boolean;
  include_term_year_relations: boolean;
  include_cooccurrence_analysis: boolean;
  include_similarity_analysis: boolean;
  include_feature_term_selection: boolean;
  include_keyword_extraction: boolean;
  include_keyword_clustering: boolean;
  include_institution_keyword_analysis: boolean;
  include_institution_topic_analysis: boolean;
  include_document_clustering: boolean;
}

export interface ExportParameters {
  export_csv: boolean;
  export_xlsx: boolean;
  export_png: boolean;
  export_html_report: boolean;
  include_audit: boolean;
  chart_dpi: number;
  watermark_enabled: boolean;
  watermark_text: string;
}

export interface RunScopeDefinition {
  mode: "all_documents" | "filtered_subset" | "selected_documents";
  source_values: string[];
  institution_values: string[];
  category_values: string[];
  year_from?: number | null;
  year_to?: number | null;
  selected_doc_ids: string[];
}

export type WorkflowRecipeId = "standard_analysis" | "keyword_topic" | "trend_scan" | "custom";

export type OutputBundleId = "full_report" | "tables_only" | "charts_and_report" | "audit_archive" | "custom";

export interface WorkflowRuntimeProfile {
  id: string;
  name: string;
  enabled_steps: WorkflowStepId[];
  cleaning: CleaningParameters;
  normalization: NormalizationParameters;
  tokenization: TokenizationParameters;
  dictionary: DictionaryParameters;
  filtering: FilteringParameters;
  analysis: AnalysisParameters;
  export: ExportParameters;
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
  node_configs: Record<string, unknown>;
  execution_order: WorkflowStepId[];
  run_scope: RunScopeDefinition;
  recipe_id: WorkflowRecipeId;
  output_bundle_id: OutputBundleId;
}

export interface WorkflowPort {
  port_id: string;
  port_type: WorkflowPortType;
  label?: string;
  allow_multiple?: boolean;
}

export interface WorkflowNodeUiState {
  collapsed: boolean;
  bypassed: boolean;
  pinned_preview?: boolean;
}

export interface WorkflowNodeRuntimeMeta {
  step_id?: WorkflowStepId | "scope" | "resource" | "merge" | "sink" | "utility";
  node_impl_version: string;
}

export interface WorkflowNodeInstance {
  node_id: string;
  node_type: WorkflowNodeType;
  label: string;
  position: { x: number; y: number };
  size?: { w: number; h: number };
  inputs: WorkflowPort[];
  outputs: WorkflowPort[];
  config: Record<string, unknown>;
  ui_state: WorkflowNodeUiState;
  runtime_meta: WorkflowNodeRuntimeMeta;
}

export interface WorkflowEdge {
  edge_id: string;
  from_node: string;
  from_port: string;
  to_node: string;
  to_port: string;
}

export interface WorkflowGroup {
  group_id: string;
  label: string;
  node_ids: string[];
  collapsed: boolean;
}

export interface WorkflowDefinition {
  workflow_id: string;
  name: string;
  version: string;
  graph_mode: WorkflowGraphMode;
  source: WorkflowSource;
  meta: {
    template_id: WorkflowRecipeId;
    output_bundle_id: OutputBundleId;
  };
  nodes: WorkflowNodeInstance[];
  edges: WorkflowEdge[];
  groups: WorkflowGroup[];
  viewport: {
    x: number;
    y: number;
    zoom: number;
  };
  created_at: string;
  updated_at: string;
}

export type WorkflowNodeParamKind = "boolean" | "number" | "string" | "enum";

export interface WorkflowNodeParamOption {
  value: string;
  label: string;
}

export interface WorkflowNodeParamDefinition {
  param_id: string;
  label: string;
  kind: WorkflowNodeParamKind;
  description?: string;
  required?: boolean;
  default_value?: string | number | boolean | null;
  options?: WorkflowNodeParamOption[];
}

export interface RegisteredWorkflowNodeDefinition {
  type: WorkflowNodeType;
  title: string;
  category: "input" | "process" | "analysis" | "output" | "utility" | "legacy";
  description?: string;
  hidden_from_toolbox?: boolean;
  singleton?: boolean;
  inputs: WorkflowPort[];
  outputs: WorkflowPort[];
  params: WorkflowNodeParamDefinition[];
  runtime: {
    step_id: WorkflowStepId | "scope" | "resource" | "merge" | "sink" | "utility";
    executor: string;
    cacheable: boolean;
    previewable: boolean;
    output_node: boolean;
  };
}

export interface RunLogEntry {
  timestamp: string;
  level: "info" | "warning" | "error" | "fatal";
  step: WorkflowStepId | "system";
  message: string;
}

export interface StepArtifactSummary {
  step: WorkflowStepId;
  output_files: string[];
  record_count: number;
  cache_hit: boolean;
}

export type RunArtifactSummary = StepArtifactSummary | ArtifactRecord;

export interface NodeOutputPreview {
  kind: "table" | "list" | "object" | "text" | "scalar" | "empty";
  row_count?: number;
  rows?: Array<Record<string, unknown>>;
  items?: string[];
  keys?: string[];
  text?: string;
  value?: unknown;
}

export interface NodeRunSummary {
  node_id: string;
  node_type: WorkflowNodeType;
  label: string;
  status: "completed" | "cached" | "failed" | "skipped";
  started_at: string;
  ended_at?: string;
  duration_ms: number;
  cache_hit: boolean;
  cache_key?: string;
  cache_path?: string;
  output_ports: string[];
  output_summary?: string;
  sample_outputs?: string[];
  output_previews?: Record<string, NodeOutputPreview>;
  error?: string;
}

export type WorkflowNodeRuntimeStatus = NodeRunSummary["status"] | "pending" | "running";

export interface WorkflowNodeRuntimeState {
  node_id: string;
  node_type: WorkflowNodeType;
  label: string;
  status: WorkflowNodeRuntimeStatus;
  node_index: number;
  total_nodes: number;
  progress: number;
  started_at?: string;
  ended_at?: string;
  duration_ms?: number;
  cache_hit?: boolean;
  cache_key?: string;
  cache_path?: string;
  output_ports?: string[];
  output_summary?: string;
  sample_outputs?: string[];
  output_previews?: Record<string, NodeOutputPreview>;
  detail?: string;
  error?: string;
}

export type WorkflowRunStage =
  | "preparing"
  | "running"
  | "exporting"
  | "saving"
  | "completed"
  | "failed";

export interface WorkflowRunProgressDetail {
  kind: "workflow_run";
  run_id?: string;
  workflow_id?: string;
  workflow_name?: string;
  stage: WorkflowRunStage;
  total_nodes: number;
  completed_nodes: number;
  current_node_id?: string;
  current_node_label?: string;
  current_node_index?: number;
  last_completed_node_id?: string;
  elapsed_ms?: number;
  detail?: string;
  node_states: Record<string, WorkflowNodeRuntimeState>;
  node_state_delta?: Record<string, WorkflowNodeRuntimeState>;
  full_node_state_sync?: boolean;
}

export interface RunRecord {
  run_id: string;
  project_id: string;
  workflow_version: string;
  workflow_id: string;
  workflow_name: string;
  workflow_hash: string;
  dictionary_version: string;
  started_at: string;
  ended_at?: string;
  status: RunStatus;
  warnings: string[];
  errors: string[];
  logs: RunLogEntry[];
  artifacts: RunArtifactSummary[];
  node_runs?: NodeRunSummary[];
  params_snapshot_path: string;
  processed_document_count: number;
  run_scope_summary: string;
  recipe_id: WorkflowRecipeId;
  output_bundle_id: OutputBundleId;
  output_summary: string;
}

export interface FrequencyRow {
  term: string;
  tf: number;
  df: number;
  ratio: number;
  word_length: number;
  first_year?: number | null;
  last_year?: number | null;
  avg_per_doc: number;
}

export interface TermDocumentRow {
  term: string;
  doc_id: string;
  title: string;
  year?: number | null;
  term_count_in_doc: number;
  source?: string;
}

export interface TermYearRow {
  term: string;
  year: number;
  tf_in_year: number;
  df_in_year: number;
  ratio_in_year: number;
}

export interface CooccurrenceRow {
  term_a: string;
  term_b: string;
  cooccurrence_count: number;
  score: number;
}

export interface FeatureTermRow {
  term: string;
  score: number;
  selected: boolean;
  source: "auto" | "manual";
  rank: number;
}

export interface KeywordRow {
  scope: "doc" | "project";
  doc_id?: string;
  keyword: string;
  score: number;
  rank: number;
}

export interface KeywordClusterRow {
  term: string;
  cluster_id: number;
  distance_to_centroid: number;
  is_label_term: boolean;
  topic_label?: string;
}

export interface InstitutionKeywordRow {
  institution: string;
  keyword: string;
  cooccurrence_count: number;
  year?: number | null;
  score: number;
}

export interface InstitutionTopicRow {
  institution: string;
  topic_id: number;
  topic_label: string;
  cooccurrence_count: number;
  representative_terms: string[];
  year?: number | null;
}

export interface DocumentClusterRow {
  doc_id: string;
  cluster_id: number;
  x: number;
  y: number;
  title: string;
  year?: number | null;
  source?: string;
}

export type GenericResultRow = Record<string, unknown>;

export interface AuditRow {
  doc_id: string;
  position?: number;
  source_term: string;
  target_term?: string;
  rule_type: string;
  rule_source: string;
  rule_key: string;
  action: "replace" | "drop" | "keep";
}

export interface ResultBundle {
  frequency_table: FrequencyRow[];
  term_document_table: TermDocumentRow[];
  term_year_table: TermYearRow[];
  cooccurrence_table: CooccurrenceRow[];
  similarity_table?: GenericResultRow[];
  selected_feature_terms: FeatureTermRow[];
  focus_term_summary?: GenericResultRow[];
  keyword_result: KeywordRow[];
  keyword_cluster_result: KeywordClusterRow[];
  topic_term_table?: GenericResultRow[];
  document_topic_table?: GenericResultRow[];
  topic_summary_table?: GenericResultRow[];
  institution_keyword_cooccurrence: InstitutionKeywordRow[];
  institution_topic_cooccurrence: InstitutionTopicRow[];
  clustering_result: DocumentClusterRow[];
  graph_node_table?: GenericResultRow[];
  graph_edge_table?: GenericResultRow[];
  graph_metric_table?: GenericResultRow[];
  community_table?: GenericResultRow[];
  main_path_table?: GenericResultRow[];
  link_prediction_table?: GenericResultRow[];
  technology_indicator_table?: GenericResultRow[];
  technology_classification_table?: GenericResultRow[];
  metadata_audit_table?: GenericResultRow[];
  audit_table: AuditRow[];
  report_files: string[];
}

export interface ProjectTemplate {
  id: string;
  name: string;
  description: string;
  source_profile: SourceProfile;
  workflow_definitions: WorkflowDefinition[];
  active_workflow_id: string;
  dictionary_set: DictionarySet;
  import_template: ImportTemplate;
}

export interface ProjectManifest {
  id: string;
  schema_version: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  version: string;
  source_files: SourceFileRecord[];
  corpus_resources: CorpusResource[];
  corpus_views: CorpusView[];
  ingestion_specs: IngestionSpec[];
  artifact_records: ArtifactRecord[];
  review_tasks: ReviewTask[];
  experiment_specs: ExperimentSpec[];
  shared_resource_refs: RelativePathRef[];
  settings: ProjectSettings;
  paths: ProjectPaths;
  import_template: ImportTemplate;
  dictionary_set: DictionarySet;
  workflow_definitions: WorkflowDefinition[];
  active_workflow_id: string;
  run_history: RunRecord[];
  results: ResultBundle;
}

export interface ProjectSummary {
  id: string;
  name: string;
  description: string;
  path: string;
  updated_at: string;
  document_count: number;
  run_count: number;
}

export interface WorkspaceSnapshot {
  recent_projects: ProjectSummary[];
  current_project?: ProjectManifest;
  corpus: CorpusItem[];
  selected_run?: RunRecord;
  node_definitions?: RegisteredWorkflowNodeDefinition[];
}

export const sourceProfiles: Record<SourceProfile, string> = {
  generic: "通用结构化数据",
  literature: "文献数据",
  wos: "Web of Science",
  scopus: "Scopus",
  patent: "专利数据",
  incopat: "IncoPat",
  business_reserved: "商业数据（预留）"
};

export const sourceProfileImportTemplates: Record<
  SourceProfile,
  Pick<ImportTemplate, "name" | "description" | "field_mappings" | "text_build">
> = {
  generic: {
    name: "通用导入模板",
    description: "适合 txt/csv/xlsx/json 的通用结构化文本导入。",
    field_mappings: [
      { source_field: "doc_id", target_field: "doc_id", required: false, aliases: ["id", "document_id"] },
      { source_field: "title", target_field: "title", required: false, aliases: ["name", "subject"] },
      { source_field: "abstract", target_field: "raw_text", required: false, aliases: ["raw_text", "content", "text", "summary"] },
      { source_field: "year", target_field: "year", required: false, aliases: ["published", "publication_year"] },
      { source_field: "source", target_field: "source", required: false, aliases: ["journal", "origin"] },
      { source_field: "author", target_field: "author", required: false, aliases: ["authors", "creator"] },
      { source_field: "institution", target_field: "institution", required: false, aliases: ["org", "organization", "affiliation"] },
      { source_field: "country_or_region", target_field: "country_or_region", required: false, aliases: ["country", "region"] },
      { source_field: "category_or_tag", target_field: "category_or_tag", required: false, aliases: ["category", "tag"] },
      { source_field: "keyword_field", target_field: "keyword_field", required: false, aliases: ["keywords", "keyword"] }
    ],
    text_build: { mode: "concat_fields", fields: ["title", "abstract"], delimiter: "\n\n", skip_empty: true }
  },
  literature: {
    name: "文献导入模板",
    description: "面向论文、报告和综述等文献数据。",
    field_mappings: [
      { source_field: "title", target_field: "title", required: true, aliases: ["Title", "article_title"] },
      { source_field: "abstract", target_field: "raw_text", required: true, aliases: ["Abstract", "summary"] },
      { source_field: "year", target_field: "year", required: false, aliases: ["PY", "published", "publication_year"] },
      { source_field: "source", target_field: "source", required: false, aliases: ["journal", "SO"] },
      { source_field: "author", target_field: "author", required: false, aliases: ["authors", "AU"] },
      { source_field: "institution", target_field: "institution", required: false, aliases: ["org", "affiliation", "C1"] },
      { source_field: "keyword_field", target_field: "keyword_field", required: false, aliases: ["keywords", "DE"] },
      { source_field: "category_or_tag", target_field: "category_or_tag", required: false, aliases: ["category", "WC"] }
    ],
    text_build: { mode: "concat_fields", fields: ["title", "abstract"], delimiter: "\n\n", skip_empty: true }
  },
  wos: {
    name: "Web of Science 模板",
    description: "预置 WoS 常见字段别名和主文本拼接策略。",
    field_mappings: [
      { source_field: "UT", target_field: "doc_id", required: true, aliases: ["Accession Number"] },
      { source_field: "TI", target_field: "title", required: true, aliases: ["Article Title"] },
      { source_field: "AB", target_field: "raw_text", required: true, aliases: ["Abstract"] },
      { source_field: "PY", target_field: "year", required: false, aliases: ["Published Year"] },
      { source_field: "SO", target_field: "source", required: false, aliases: ["Publication Name"] },
      { source_field: "AU", target_field: "author", required: false, aliases: ["Authors"] },
      { source_field: "C1", target_field: "institution", required: false, aliases: ["Addresses"] },
      { source_field: "DE", target_field: "keyword_field", required: false, aliases: ["Author Keywords"] },
      { source_field: "WC", target_field: "category_or_tag", required: false, aliases: ["Web of Science Categories"] }
    ],
    text_build: { mode: "concat_fields", fields: ["TI", "AB", "DE"], delimiter: "\n\n", skip_empty: true }
  },
  scopus: {
    name: "Scopus 模板",
    description: "预置 Scopus CSV 常见字段别名与主文本拼接策略。",
    field_mappings: [
      { source_field: "EID", target_field: "doc_id", required: true, aliases: ["eid"] },
      { source_field: "Title", target_field: "title", required: true, aliases: ["title"] },
      { source_field: "Abstract", target_field: "raw_text", required: true, aliases: ["abstract"] },
      { source_field: "Year", target_field: "year", required: false, aliases: ["year"] },
      { source_field: "Source title", target_field: "source", required: false, aliases: ["source"] },
      { source_field: "Authors", target_field: "author", required: false, aliases: ["author"] },
      { source_field: "Affiliations", target_field: "institution", required: false, aliases: ["affiliation"] },
      { source_field: "Author Keywords", target_field: "keyword_field", required: false, aliases: ["keywords"] },
      { source_field: "Index Keywords", target_field: "keyword_field", required: false, aliases: ["index_keywords"] }
    ],
    text_build: { mode: "concat_fields", fields: ["Title", "Abstract", "Author Keywords"], delimiter: "\n\n", skip_empty: true }
  },
  patent: {
    name: "专利导入模板",
    description: "适合公开文本、摘要、申请人和 IPC/主题字段。",
    field_mappings: [
      { source_field: "publication_number", target_field: "doc_id", required: true, aliases: ["pn", "patent_no", "公开（公告）号"] },
      { source_field: "title", target_field: "title", required: true, aliases: ["invention_title", "标题", "专利名称"] },
      { source_field: "abstract", target_field: "raw_text", required: true, aliases: ["摘要", "abstract_text"] },
      { source_field: "publication_year", target_field: "year", required: false, aliases: ["year", "公开（公告）日"] },
      { source_field: "applicant", target_field: "institution", required: false, aliases: ["assignee", "申请人"] },
      { source_field: "inventor", target_field: "author", required: false, aliases: ["发明人"] },
      { source_field: "ipc", target_field: "category_or_tag", required: false, aliases: ["IPC", "IPC分类号"] },
      { source_field: "keywords", target_field: "keyword_field", required: false, aliases: ["主题词"] }
    ],
    text_build: { mode: "concat_fields", fields: ["title", "abstract", "keywords"], delimiter: "\n\n", skip_empty: true }
  },
  incopat: {
    name: "IncoPat 模板",
    description: "预置 IncoPat 常见中文字段名与别名。",
    field_mappings: [
      { source_field: "公开（公告）号", target_field: "doc_id", required: true, aliases: ["公开(公告)号", "申请号", "专利号", "公开号", "授权公告号", "首次公开号"] },
      { source_field: "标题 (中文)", target_field: "title", required: true, aliases: ["标题（中文）", "标题(中文)", "标题", "专利名称", "标题 (英文)", "标题（英文）", "标题(英文)", "标题（小语种原文）"] },
      { source_field: "摘要 (中文)", target_field: "raw_text", required: true, aliases: ["摘要（中文）", "摘要(中文)", "摘要", "摘要 (英文)", "摘要（英文）", "摘要(英文)", "摘要（小语种原文）", "首权翻译", "首项权利要求", "独立权利要求", "简介"] },
      { source_field: "公开（公告）日", target_field: "year", required: false, aliases: ["公开(公告)日", "申请日", "优先权日", "最早优先权日", "年份", "首次公开日", "授权公告日"] },
      { source_field: "申请人", target_field: "institution", required: false, aliases: ["标准化申请人", "当前权利人", "标准化当前权利人", "第一申请人", "专利权人", "申请人(翻译)", "申请人（翻译）"] },
      { source_field: "发明人", target_field: "author", required: false, aliases: ["第一发明(设计)人", "第一发明（设计）人", "发明(设计)人(其他)", "发明（设计）人（其他）", "Inventor"] },
      { source_field: "公开国别", target_field: "country_or_region", required: false, aliases: ["申请人国家/地区", "优先权国别", "同族国家/地区"] },
      { source_field: "IPC", target_field: "category_or_tag", required: false, aliases: ["IPC分类号", "IPC主分类-小组", "CPC"] },
      { source_field: "技术功效短语", target_field: "keyword_field", required: false, aliases: ["技术功效句", "用途", "关键词", "主题词"] }
    ],
    text_build: { mode: "concat_fields", fields: ["标题 (中文)", "摘要 (中文)"], delimiter: "\n\n", skip_empty: true }
  },
  business_reserved: {
    name: "商业数据模板",
    description: "预留给后续商业数据/行业报告导入。",
    field_mappings: [
      { source_field: "record_id", target_field: "doc_id", required: false, aliases: ["id"] },
      { source_field: "title", target_field: "title", required: true, aliases: ["subject"] },
      { source_field: "content", target_field: "raw_text", required: true, aliases: ["raw_text", "text"] },
      { source_field: "year", target_field: "year", required: false, aliases: ["published_year"] },
      { source_field: "company", target_field: "institution", required: false, aliases: ["institution", "organization"] },
      { source_field: "topic", target_field: "category_or_tag", required: false, aliases: ["category"] },
      { source_field: "keywords", target_field: "keyword_field", required: false, aliases: ["tags"] }
    ],
    text_build: { mode: "concat_fields", fields: ["title", "content"], delimiter: "\n\n", skip_empty: true }
  }
};

export const pageIds = [
  "home",
  "project",
  "data",
  "workflow",
  "dictionaries",
  "results",
  "report",
  "settings"
] as const;

export type PageId = (typeof pageIds)[number];
