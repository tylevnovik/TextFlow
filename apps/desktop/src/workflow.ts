import type {
  AnalysisParameters,
  ExportParameters,
  PipelineDefinition,
  PipelineStepId,
  ProjectManifest,
  RunScopeDefinition,
  WorkflowDefinition,
  WorkflowEdge,
  WorkflowNodeInstance,
  WorkflowNodeType,
  WorkflowPort,
  WorkflowPortType
} from "@textflow/shared-types";

type WorkflowPortDirection = "inputs" | "outputs";

type WorkflowStepRole = PipelineStepId | "scope" | "resource" | "merge" | "sink" | "utility";

interface WorkflowNodeDefinition {
  label: string;
  description: string;
  category: "input" | "process" | "analysis" | "output" | "utility" | "legacy";
  singleton?: boolean;
  hidden_from_toolbox?: boolean;
  inputs: WorkflowPort[];
  outputs: WorkflowPort[];
  stepId: WorkflowStepRole;
  size?: { w: number; h: number };
  defaultConfig: (pipeline: PipelineDefinition) => Record<string, unknown>;
}

export interface WorkflowValidation {
  valid: boolean;
  issues: string[];
  reachable_node_ids: string[];
  active_node_ids: string[];
  sink_node_ids: string[];
  missing_inputs_by_node_id: Record<string, string[]>;
  normalized_edges: WorkflowEdge[];
}

export interface WorkflowTargetPortCandidate {
  node_id: string;
  node_type: WorkflowNodeType;
  port_id: string;
  port_type: WorkflowPortType;
}

const legacyNodeTypes = new Set<WorkflowNodeType>([
  "load_project_corpus",
  "filter_corpus",
  "project_dictionary_set",
  "analyze_corpus",
  "export_results"
]);

const sinkNodeTypes = new Set<WorkflowNodeType>([
  "save_csv",
  "save_xlsx",
  "save_png",
  "save_html_report",
  "export_results"
]);

const renderableSourceTypes = new Set<WorkflowPortType>([
  "FrequencyTable",
  "TermYearTable",
  "CooccurrenceTable",
  "KeywordClusterTable",
  "InstitutionTopicTable",
  "AnalysisBundle"
]);

const tableSourceTypes = new Set<WorkflowPortType>([
  "FrequencyTable",
  "TermDocumentTable",
  "TermYearTable",
  "CooccurrenceTable",
  "KeywordTable",
  "KeywordClusterTable",
  "InstitutionTopicTable",
  "AuditTable"
]);

const analysisResultTypes = new Set<WorkflowPortType>([
  ...tableSourceTypes,
  "AnalysisBundle"
]);

const corpusPortOrder: WorkflowPortType[] = [
  "CorpusTable",
  "ProjectCorpus",
  "ScopedCorpus",
  "CleanCorpus",
  "NormalizedCorpus",
  "TokenCorpus",
  "FilteredTokenCorpus"
];

const defaultNodePositions: Partial<Record<WorkflowNodeType, { x: number; y: number }>> = {
  dictionary_input: { x: 120, y: 80 },
  corpus_input: { x: 120, y: 330 },
  merge_corpora: { x: 520, y: 330 },
  clean_text: { x: 900, y: 330 },
  normalize_text: { x: 1280, y: 330 },
  tokenize: { x: 1680, y: 330 },
  apply_dictionary_rules: { x: 2060, y: 330 },
  filter_terms: { x: 2460, y: 330 },
  frequency_statistics: { x: 2860, y: 80 },
  term_year_analysis: { x: 2860, y: 340 },
  cooccurrence_analysis: { x: 2860, y: 600 },
  keyword_extraction: { x: 2860, y: 860 },
  keyword_clustering: { x: 3240, y: 860 },
  institution_topic_analysis: { x: 3240, y: 600 },
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

const executionOrder: PipelineStepId[] = [
  "ingestion",
  "cleaning",
  "normalization",
  "tokenization",
  "dictionary_application",
  "filtering",
  "analysis",
  "export"
];

const defaultRunScope = (pipeline: PipelineDefinition): RunScopeDefinition => ({
  ...pipeline.run_scope,
  mode: pipeline.run_scope?.mode ?? "all_documents",
  source_values: [...(pipeline.run_scope?.source_values ?? [])],
  institution_values: [...(pipeline.run_scope?.institution_values ?? [])],
  category_values: [...(pipeline.run_scope?.category_values ?? [])],
  year_from: pipeline.run_scope?.year_from ?? null,
  year_to: pipeline.run_scope?.year_to ?? null,
  selected_doc_ids: [...(pipeline.run_scope?.selected_doc_ids ?? [])]
});

const defaultExport = (pipeline: PipelineDefinition): ExportParameters => ({
  ...pipeline.export,
  export_csv: pipeline.export?.export_csv ?? true,
  export_xlsx: pipeline.export?.export_xlsx ?? true,
  export_png: pipeline.export?.export_png ?? true,
  export_html_report: pipeline.export?.export_html_report ?? true,
  include_audit: pipeline.export?.include_audit ?? true,
  chart_dpi: pipeline.export?.chart_dpi ?? 320,
  watermark_enabled: pipeline.export?.watermark_enabled ?? false,
  watermark_text: pipeline.export?.watermark_text ?? "TextFlow Studio"
});

const workflowNodeDefinitions: Record<WorkflowNodeType, WorkflowNodeDefinition> = {
  corpus_input: {
    label: "语料输入",
    description: "选择一个语料资源，并在节点内定义本次处理对象。",
    category: "input",
    inputs: [],
    outputs: [{ port_id: "corpus", port_type: "CorpusTable", label: "语料" }],
    stepId: "scope",
    size: { w: 420, h: 340 },
    defaultConfig: (pipeline) => ({
      resource_mode: "project_corpus",
      resource_id: "project:corpus",
      ...(defaultRunScope(pipeline) as unknown as Record<string, unknown>)
    })
  },
  dictionary_input: {
    label: "词表输入",
    description: "引用当前项目中的词表资源。",
    category: "input",
    inputs: [],
    outputs: [{ port_id: "dictionary_set", port_type: "DictionarySet", label: "词表" }],
    stepId: "resource",
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
    label: "合并语料",
    description: "把多路语料汇合成一路，供下游统一处理。",
    category: "process",
    inputs: [{ port_id: "corpus_in", port_type: "CorpusTable", label: "输入语料", allow_multiple: true }],
    outputs: [{ port_id: "corpus", port_type: "CorpusTable", label: "合并后语料" }],
    stepId: "merge",
    size: { w: 300, h: 210 },
    defaultConfig: () => ({ strategy: "append" })
  },
  clean_text: {
    label: "基础清洗",
    description: "去噪、清理空白、处理 HTML 与 URL。",
    category: "process",
    inputs: [{ port_id: "corpus_in", port_type: "CorpusTable", label: "语料输入" }],
    outputs: [{ port_id: "clean_corpus", port_type: "CleanCorpus", label: "清洗后语料" }],
    stepId: "cleaning",
    size: { w: 320, h: 230 },
    defaultConfig: (pipeline) => ({ ...pipeline.cleaning })
  },
  normalize_text: {
    label: "统一写法",
    description: "统一时间、数字和正则替换后的文本表达。",
    category: "process",
    inputs: [{ port_id: "corpus_in", port_type: "CleanCorpus", label: "清洗后语料" }],
    outputs: [{ port_id: "normalized_corpus", port_type: "NormalizedCorpus", label: "标准化语料" }],
    stepId: "normalization",
    size: { w: 330, h: 240 },
    defaultConfig: (pipeline) => ({ ...pipeline.normalization })
  },
  tokenize: {
    label: "切词",
    description: "执行中英文切词，并尽量保留短语。",
    category: "process",
    inputs: [{ port_id: "corpus_in", port_type: "NormalizedCorpus", label: "标准化语料" }],
    outputs: [{ port_id: "token_corpus", port_type: "TokenCorpus", label: "Token 语料" }],
    stepId: "tokenization",
    size: { w: 320, h: 230 },
    defaultConfig: (pipeline) => ({ ...pipeline.tokenization })
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
      { port_id: "audit_table", port_type: "AuditTable", label: "审计表" }
    ],
    stepId: "dictionary_application",
    size: { w: 340, h: 240 },
    defaultConfig: (pipeline) => ({ ...pipeline.dictionary })
  },
  filter_terms: {
    label: "过滤词项",
    description: "去掉过短、过少或不适合分析的词项。",
    category: "process",
    inputs: [{ port_id: "token_corpus_in", port_type: "TokenCorpus", label: "Token 输入" }],
    outputs: [{ port_id: "filtered_token_corpus", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    stepId: "filtering",
    size: { w: 320, h: 230 },
    defaultConfig: (pipeline) => ({ ...pipeline.filtering })
  },
  frequency_statistics: {
    label: "词频统计",
    description: "生成高频词、文档频次和占比统计。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [{ port_id: "frequency_table", port_type: "FrequencyTable", label: "词频表" }],
    stepId: "analysis",
    size: { w: 280, h: 210 },
    defaultConfig: (pipeline) => ({ top_n: pipeline.analysis.top_n })
  },
  term_year_analysis: {
    label: "词项年份分析",
    description: "分析词项按年份的变化趋势。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [{ port_id: "term_year_table", port_type: "TermYearTable", label: "词项年份表" }],
    stepId: "analysis",
    size: { w: 280, h: 210 },
    defaultConfig: () => ({})
  },
  cooccurrence_analysis: {
    label: "共现分析",
    description: "统计词项在窗口内的共现关系。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [{ port_id: "cooccurrence_table", port_type: "CooccurrenceTable", label: "共现表" }],
    stepId: "analysis",
    size: { w: 320, h: 230 },
    defaultConfig: (pipeline) => ({
      cooccurrence_window: pipeline.analysis.cooccurrence_window,
      min_cooccurrence: pipeline.analysis.min_cooccurrence
    })
  },
  keyword_extraction: {
    label: "关键词提取",
    description: "从语料中抽取项目级和文档级关键词。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [{ port_id: "keyword_table", port_type: "KeywordTable", label: "关键词表" }],
    stepId: "analysis",
    size: { w: 320, h: 220 },
    defaultConfig: (pipeline) => ({
      top_k_per_doc: pipeline.analysis.top_k_per_doc,
      top_k_project: pipeline.analysis.top_k_project
    })
  },
  keyword_clustering: {
    label: "关键词聚类",
    description: "把关键词聚成主题簇，生成标签和代表词。",
    category: "analysis",
    inputs: [{ port_id: "keyword_table_in", port_type: "KeywordTable", label: "关键词输入" }],
    outputs: [{ port_id: "keyword_cluster_table", port_type: "KeywordClusterTable", label: "关键词聚类表" }],
    stepId: "analysis",
    size: { w: 320, h: 220 },
    defaultConfig: (pipeline) => ({
      keyword_cluster_k: pipeline.analysis.keyword_cluster_k,
      topic_model_k: pipeline.analysis.topic_model_k
    })
  },
  institution_topic_analysis: {
    label: "机构主题分析",
    description: "分析机构与主题的关系分布。",
    category: "analysis",
    inputs: [{ port_id: "token_corpus_in", port_type: "FilteredTokenCorpus", label: "分析词项" }],
    outputs: [{ port_id: "institution_topic_table", port_type: "InstitutionTopicTable", label: "机构主题表" }],
    stepId: "analysis",
    size: { w: 300, h: 210 },
    defaultConfig: (pipeline) => ({ topic_model_k: pipeline.analysis.topic_model_k })
  },
  save_csv: {
    label: "保存 CSV",
    description: "把上游表格结果写成 CSV 文件。",
    category: "output",
    inputs: [{ port_id: "table_in", port_type: "AnyTable", label: "表格输入", allow_multiple: true }],
    outputs: [{ port_id: "artifact", port_type: "ExportArtifact", label: "导出产物" }],
    stepId: "export",
    size: { w: 280, h: 210 },
    defaultConfig: () => ({ file_prefix: "tables", export_csv: true })
  },
  save_xlsx: {
    label: "保存 XLSX",
    description: "把上游表格结果整理成 Excel 文件。",
    category: "output",
    inputs: [{ port_id: "table_in", port_type: "AnyTable", label: "表格输入", allow_multiple: true }],
    outputs: [{ port_id: "artifact", port_type: "ExportArtifact", label: "导出产物" }],
    stepId: "export",
    size: { w: 280, h: 210 },
    defaultConfig: () => ({ file_prefix: "tables", export_xlsx: true })
  },
  save_png: {
    label: "保存 PNG",
    description: "把上游分析结果按默认图表规则渲染为 PNG。",
    category: "output",
    inputs: [{ port_id: "render_in", port_type: "AnyRenderable", label: "图像输入", allow_multiple: true }],
    outputs: [{ port_id: "artifact", port_type: "ExportArtifact", label: "导出产物" }],
    stepId: "export",
    size: { w: 300, h: 220 },
    defaultConfig: (pipeline) => ({
      file_prefix: "charts",
      chart_dpi: defaultExport(pipeline).chart_dpi
    })
  },
  save_html_report: {
    label: "保存 HTML 报告",
    description: "根据上游分析结果生成 HTML 报告。",
    category: "output",
    inputs: [{ port_id: "report_in", port_type: "AnyAnalysisResult", label: "报告输入", allow_multiple: true }],
    outputs: [{ port_id: "artifact", port_type: "ExportArtifact", label: "导出产物" }],
    stepId: "export",
    size: { w: 320, h: 230 },
    defaultConfig: (pipeline) => ({
      file_prefix: "report",
      include_audit: defaultExport(pipeline).include_audit
    })
  },
  note: {
    label: "注释",
    description: "给画布上的某段流程添加说明。",
    category: "utility",
    inputs: [],
    outputs: [],
    stepId: "utility",
    defaultConfig: () => ({ text: "备注" }),
    size: { w: 260, h: 160 }
  },
  group: {
    label: "分组",
    description: "用于整理节点区域和视觉分组。",
    category: "utility",
    inputs: [],
    outputs: [],
    stepId: "utility",
    defaultConfig: () => ({ title: "分组" }),
    size: { w: 280, h: 180 }
  },
  load_project_corpus: {
    label: "读取项目语料",
    description: "旧版兼容节点：已由语料输入替代。",
    category: "legacy",
    hidden_from_toolbox: true,
    inputs: [],
    outputs: [{ port_id: "project_corpus", port_type: "ProjectCorpus", label: "项目语料" }],
    stepId: "resource",
    defaultConfig: () => ({})
  },
  filter_corpus: {
    label: "筛选处理对象",
    description: "旧版兼容节点：已并入语料输入节点。",
    category: "legacy",
    hidden_from_toolbox: true,
    inputs: [{ port_id: "project_corpus_in", port_type: "ProjectCorpus", label: "项目语料" }],
    outputs: [{ port_id: "scoped_corpus", port_type: "ScopedCorpus", label: "筛选后语料" }],
    stepId: "scope",
    defaultConfig: (pipeline) => ({ ...(defaultRunScope(pipeline) as unknown as Record<string, unknown>) })
  },
  project_dictionary_set: {
    label: "项目词表",
    description: "旧版兼容节点：已由词表输入替代。",
    category: "legacy",
    hidden_from_toolbox: true,
    inputs: [],
    outputs: [{ port_id: "dictionary_set", port_type: "DictionarySet", label: "词表" }],
    stepId: "resource",
    defaultConfig: () => ({})
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
    stepId: "analysis",
    defaultConfig: (pipeline) => ({ ...pipeline.analysis })
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
    stepId: "export",
    defaultConfig: (pipeline) => ({ ...defaultExport(pipeline) })
  }
};

function clonePipeline(pipeline: PipelineDefinition): PipelineDefinition {
  return {
    ...pipeline,
    enabled_steps: [...pipeline.enabled_steps],
    execution_order: [...pipeline.execution_order],
    cleaning: { ...pipeline.cleaning },
    normalization: { ...pipeline.normalization },
    tokenization: { ...pipeline.tokenization },
    dictionary: { ...pipeline.dictionary },
    filtering: { ...pipeline.filtering },
    analysis: { ...pipeline.analysis },
    export: { ...defaultExport(pipeline) },
    run_scope: defaultRunScope(pipeline),
    nodes: [...pipeline.nodes],
    edges: [...pipeline.edges],
    node_configs: { ...pipeline.node_configs }
  };
}

function cloneNode(node: WorkflowNodeInstance): WorkflowNodeInstance {
  return {
    ...node,
    position: { ...node.position },
    size: node.size ? { ...node.size } : undefined,
    inputs: node.inputs.map((port) => ({ ...port })),
    outputs: node.outputs.map((port) => ({ ...port })),
    config: { ...node.config },
    ui_state: { ...node.ui_state },
    runtime_meta: { ...node.runtime_meta }
  };
}

function cloneEdge(edge: WorkflowEdge): WorkflowEdge {
  return { ...edge };
}

function workflowNodeId(nodeType: WorkflowNodeType): string {
  return `node-${nodeType}-${Math.random().toString(36).slice(2, 8)}`;
}

function workflowEdgeId(): string {
  return `edge-${Math.random().toString(36).slice(2, 10)}`;
}

function workflowNodeFrameForType(nodeType: WorkflowNodeType) {
  return definitionForNode(nodeType).size ?? { w: 280, h: 210 };
}

function definitionForNode(nodeType: WorkflowNodeType): WorkflowNodeDefinition {
  const definition = workflowNodeDefinitions[nodeType];
  if (!definition) {
    throw new Error(`Unsupported workflow node type: ${nodeType}`);
  }
  return definition;
}

function createWorkflowNode(nodeType: WorkflowNodeType, pipeline: PipelineDefinition): WorkflowNodeInstance {
  const definition = definitionForNode(nodeType);
  return {
    node_id: workflowNodeId(nodeType),
    node_type: nodeType,
    label: definition.label,
    position: { ...(defaultNodePositions[nodeType] ?? { x: 120, y: 220 }) },
    size: definition.size ? { ...definition.size } : { w: 230, h: 190 },
    inputs: definition.inputs.map((port) => ({ ...port })),
    outputs: definition.outputs.map((port) => ({ ...port })),
    config: definition.defaultConfig(pipeline),
    ui_state: {
      collapsed: false,
      bypassed: false
    },
    runtime_meta: {
      step_id: definition.stepId,
      node_impl_version: "2.0.0"
    }
  };
}

function nodeLookupById(nodes: WorkflowNodeInstance[]): Map<string, WorkflowNodeInstance> {
  return new Map(nodes.map((node) => [node.node_id, cloneNode(node)]));
}

function findPort(
  node: WorkflowNodeInstance | undefined,
  portId: string,
  direction: WorkflowPortDirection
): WorkflowPort | null {
  if (!node) {
    return null;
  }
  return node[direction].find((port) => port.port_id === portId) ?? null;
}

function portAcceptsMultiple(node: WorkflowNodeInstance | undefined, portId: string): boolean {
  return Boolean(findPort(node, portId, "inputs")?.allow_multiple);
}

function outputPortForSingleInputNode(node: WorkflowNodeInstance | undefined): string | null {
  if (!node) {
    return null;
  }
  return node.outputs[0]?.port_id ?? null;
}

function nodeDescription(nodeType: WorkflowNodeType): string {
  return definitionForNode(nodeType).description;
}

function isSourceNode(node: WorkflowNodeInstance): boolean {
  return node.inputs.length === 0 && !sinkNodeTypes.has(node.node_type);
}

function isSinkNode(node: WorkflowNodeInstance): boolean {
  return sinkNodeTypes.has(node.node_type);
}

function isLegacyGraph(workflow: WorkflowDefinition): boolean {
  return workflow.nodes.some((node) => legacyNodeTypes.has(node.node_type));
}

function normalizeConfigNode(
  nodeType: WorkflowNodeType,
  config: Record<string, unknown>,
  pipeline: PipelineDefinition
): Record<string, unknown> {
  const base = definitionForNode(nodeType).defaultConfig(pipeline);
  return {
    ...base,
    ...config
  };
}

function filteredNodeTypeSequence(pipeline: PipelineDefinition): WorkflowNodeType[] {
  const enabledSteps = new Set(pipeline.enabled_steps);
  const sequence: WorkflowNodeType[] = ["corpus_input"];
  if (enabledSteps.has("cleaning")) {
    sequence.push("clean_text");
  }
  if (enabledSteps.has("normalization")) {
    sequence.push("normalize_text");
  }
  sequence.push("tokenize");
  if (enabledSteps.has("dictionary_application")) {
    sequence.push("apply_dictionary_rules");
  }
  if (enabledSteps.has("filtering")) {
    sequence.push("filter_terms");
  }
  return sequence;
}

function analysisStarterNodes(): WorkflowNodeType[] {
  return [
    "frequency_statistics",
    "term_year_analysis",
    "cooccurrence_analysis",
    "keyword_extraction",
    "keyword_clustering",
    "institution_topic_analysis"
  ];
}

function outputStarterNodes(exportConfig: ExportParameters): WorkflowNodeType[] {
  const nodes: WorkflowNodeType[] = [];
  if (exportConfig.export_csv) {
    nodes.push("save_csv");
  }
  if (exportConfig.export_xlsx) {
    nodes.push("save_xlsx");
  }
  if (exportConfig.export_png) {
    nodes.push("save_png");
  }
  if (exportConfig.export_html_report) {
    nodes.push("save_html_report");
  }
  return nodes;
}

function makeEdge(fromNode: WorkflowNodeInstance, fromPort: string, toNode: WorkflowNodeInstance, toPort: string): WorkflowEdge {
  return {
    edge_id: workflowEdgeId(),
    from_node: fromNode.node_id,
    from_port: fromPort,
    to_node: toNode.node_id,
    to_port: toPort
  };
}

function createStarterWorkflowNodes(pipeline: PipelineDefinition): WorkflowNodeInstance[] {
  const nodes: WorkflowNodeInstance[] = [];
  const sequence = filteredNodeTypeSequence(pipeline);
  const exportConfig = defaultExport(pipeline);
  const starterTypes: WorkflowNodeType[] = [
    ...sequence,
    "dictionary_input",
    ...analysisStarterNodes(),
    ...outputStarterNodes(exportConfig)
  ];
  for (const nodeType of starterTypes) {
    nodes.push(createWorkflowNode(nodeType, pipeline));
  }
  return nodes;
}

function nodeByType(nodes: WorkflowNodeInstance[], nodeType: WorkflowNodeType): WorkflowNodeInstance | undefined {
  return nodes.find((node) => node.node_type === nodeType);
}

function buildStarterWorkflowEdges(nodes: WorkflowNodeInstance[], pipeline: PipelineDefinition): WorkflowEdge[] {
  const edges: WorkflowEdge[] = [];
  const filteredSequence = filteredNodeTypeSequence(pipeline);
  for (let index = 0; index < filteredSequence.length - 1; index += 1) {
    const fromNode = nodeByType(nodes, filteredSequence[index]);
    const toNode = nodeByType(nodes, filteredSequence[index + 1]);
    if (!fromNode || !toNode) {
      continue;
    }
    const fromPort = outputPortForSingleInputNode(fromNode);
    const toPort = toNode.inputs[0]?.port_id;
    if (fromPort && toPort) {
      edges.push(makeEdge(fromNode, fromPort, toNode, toPort));
    }
  }

  const dictionaryNode = nodeByType(nodes, "dictionary_input");
  const dictionaryApplyNode = nodeByType(nodes, "apply_dictionary_rules");
  if (dictionaryNode && dictionaryApplyNode) {
    edges.push(makeEdge(dictionaryNode, "dictionary_set", dictionaryApplyNode, "dictionary_set_in"));
  }

  const lastProcessNode =
    nodeByType(nodes, "filter_terms")
    ?? nodeByType(nodes, "apply_dictionary_rules")
    ?? nodeByType(nodes, "tokenize")
    ?? nodeByType(nodes, "normalize_text")
    ?? nodeByType(nodes, "clean_text")
    ?? nodeByType(nodes, "corpus_input");

  const keywordNode = nodeByType(nodes, "keyword_extraction");
  const clusterNode = nodeByType(nodes, "keyword_clustering");

  for (const analysisType of analysisStarterNodes()) {
    const analysisNode = nodeByType(nodes, analysisType);
    if (!analysisNode) {
      continue;
    }
    if (analysisType === "keyword_clustering") {
      if (keywordNode) {
        edges.push(makeEdge(keywordNode, "keyword_table", analysisNode, "keyword_table_in"));
      }
      continue;
    }
    if (lastProcessNode) {
      const fromPort = outputPortForSingleInputNode(lastProcessNode);
      const toPort = analysisNode.inputs[0]?.port_id;
      if (fromPort && toPort) {
        edges.push(makeEdge(lastProcessNode, fromPort, analysisNode, toPort));
      }
    }
  }

  const sinkMappings: Array<[WorkflowNodeType, WorkflowNodeType[]]> = [
    ["save_csv", ["frequency_statistics", "term_year_analysis", "cooccurrence_analysis", "keyword_extraction", "keyword_clustering", "institution_topic_analysis"]],
    ["save_xlsx", ["frequency_statistics", "term_year_analysis", "cooccurrence_analysis", "keyword_extraction", "keyword_clustering", "institution_topic_analysis"]],
    ["save_png", ["frequency_statistics", "term_year_analysis", "cooccurrence_analysis", "keyword_clustering", "institution_topic_analysis"]],
    ["save_html_report", ["frequency_statistics", "term_year_analysis", "cooccurrence_analysis", "keyword_extraction", "keyword_clustering", "institution_topic_analysis"]]
  ];

  for (const [sinkType, sourceTypes] of sinkMappings) {
    const sinkNode = nodeByType(nodes, sinkType);
    if (!sinkNode) {
      continue;
    }
    for (const sourceType of sourceTypes) {
      const sourceNode = nodeByType(nodes, sourceType);
      const fromPort = outputPortForSingleInputNode(sourceNode);
      const toPort = sinkNode.inputs[0]?.port_id;
      if (sourceNode && fromPort && toPort) {
        edges.push(makeEdge(sourceNode, fromPort, sinkNode, toPort));
      }
    }
    if (sinkType === "save_html_report" && dictionaryApplyNode) {
      edges.push(makeEdge(dictionaryApplyNode, "audit_table", sinkNode, "report_in"));
    }
  }

  return edges;
}

function buildStarterWorkflow(
  workflow: WorkflowDefinition,
  pipeline: PipelineDefinition
): WorkflowDefinition {
  const timestamp = new Date().toISOString();
  const nodes = createStarterWorkflowNodes(pipeline);
  return {
    ...workflow,
    graph_mode: "dag",
    source: workflow.source ?? "template",
    updated_at: timestamp,
    nodes,
    edges: buildStarterWorkflowEdges(nodes, pipeline),
    groups: [],
    viewport: {
      x: 0,
      y: 0,
      zoom: 0.82
    }
  };
}

export function workflowPortCompatible(sourceType: WorkflowPortType, targetType: WorkflowPortType): boolean {
  if (sourceType === targetType) {
    return true;
  }
  if (targetType === "AnyTable" && tableSourceTypes.has(sourceType)) {
    return true;
  }
  if (targetType === "AnyRenderable" && renderableSourceTypes.has(sourceType)) {
    return true;
  }
  if (targetType === "AnyAnalysisResult" && analysisResultTypes.has(sourceType)) {
    return true;
  }
  const sourceIndex = corpusPortOrder.indexOf(sourceType);
  const targetIndex = corpusPortOrder.indexOf(targetType);
  if (sourceIndex >= 0 && targetIndex >= 0) {
    return sourceIndex <= targetIndex;
  }
  if ((sourceType === "ProjectCorpus" || sourceType === "ScopedCorpus") && targetType === "CorpusTable") {
    return true;
  }
  if (sourceType === "CorpusTable" && (targetType === "ProjectCorpus" || targetType === "ScopedCorpus")) {
    return true;
  }
  return false;
}

function canConnectPortPair(
  nodes: Map<string, WorkflowNodeInstance>,
  fromNodeId: string,
  fromPortId: string,
  toNodeId: string,
  toPortId: string
): boolean {
  if (fromNodeId === toNodeId) {
    return false;
  }
  const fromNode = nodes.get(fromNodeId);
  const toNode = nodes.get(toNodeId);
  const fromPort = findPort(fromNode, fromPortId, "outputs");
  const toPort = findPort(toNode, toPortId, "inputs");
  if (!fromPort || !toPort) {
    return false;
  }
  return workflowPortCompatible(fromPort.port_type, toPort.port_type);
}

function edgeCreatesCycle(
  nodes: WorkflowNodeInstance[],
  edges: WorkflowEdge[],
  fromNodeId: string,
  toNodeId: string
): boolean {
  const adjacency = new Map<string, Set<string>>();
  for (const node of nodes) {
    adjacency.set(node.node_id, new Set<string>());
  }
  for (const edge of edges) {
    adjacency.get(edge.from_node)?.add(edge.to_node);
  }
  adjacency.get(fromNodeId)?.add(toNodeId);
  const stack = [toNodeId];
  const visited = new Set<string>();
  while (stack.length) {
    const current = stack.pop()!;
    if (current === fromNodeId) {
      return true;
    }
    if (visited.has(current)) {
      continue;
    }
    visited.add(current);
    for (const next of adjacency.get(current) ?? []) {
      stack.push(next);
    }
  }
  return false;
}

function normalizeEdgesWithNodes(workflow: WorkflowDefinition, nodes: WorkflowNodeInstance[]): WorkflowEdge[] {
  const nodeMap = nodeLookupById(nodes);
  const candidateEdges = Array.isArray(workflow.edges) ? workflow.edges : [];
  const normalizedEdges: WorkflowEdge[] = [];

  for (const rawEdge of candidateEdges) {
    if (!rawEdge) {
      continue;
    }
    const edge = cloneEdge(rawEdge);
    if (!canConnectPortPair(nodeMap, edge.from_node, edge.from_port, edge.to_node, edge.to_port)) {
      continue;
    }

    const toNode = nodeMap.get(edge.to_node);
    const targetAllowsMultiple = portAcceptsMultiple(toNode, edge.to_port);
    const sameTargetIndex = normalizedEdges.findIndex((item) => item.to_node === edge.to_node && item.to_port === edge.to_port);
    if (!targetAllowsMultiple && sameTargetIndex >= 0) {
      normalizedEdges.splice(sameTargetIndex, 1);
    }

    if (edgeCreatesCycle(nodes, normalizedEdges, edge.from_node, edge.to_node)) {
      continue;
    }
    normalizedEdges.push(edge);
  }

  return normalizedEdges;
}

function graphIncomingEdges(edges: WorkflowEdge[]): Map<string, WorkflowEdge[]> {
  const incoming = new Map<string, WorkflowEdge[]>();
  for (const edge of edges) {
    const key = `${edge.to_node}:${edge.to_port}`;
    const group = incoming.get(key) ?? [];
    group.push(edge);
    incoming.set(key, group);
  }
  return incoming;
}

function graphOutgoingEdges(edges: WorkflowEdge[]): Map<string, WorkflowEdge[]> {
  const outgoing = new Map<string, WorkflowEdge[]>();
  for (const edge of edges) {
    const key = `${edge.from_node}:${edge.from_port}`;
    const group = outgoing.get(key) ?? [];
    group.push(edge);
    outgoing.set(key, group);
  }
  return outgoing;
}

function inputPortSatisfied(
  nodeId: string,
  port: WorkflowPort,
  incoming: Map<string, WorkflowEdge[]>,
  reachable: Set<string>
): boolean {
  const matches = incoming.get(`${nodeId}:${port.port_id}`) ?? [];
  return matches.some((edge) => reachable.has(edge.from_node));
}

function forwardReachableNodeIds(nodes: WorkflowNodeInstance[], edges: WorkflowEdge[]): Set<string> {
  const incoming = graphIncomingEdges(edges);
  const reachable = new Set<string>();

  for (const node of nodes) {
    if (isSourceNode(node)) {
      reachable.add(node.node_id);
    }
  }

  let changed = true;
  while (changed) {
    changed = false;
    for (const node of nodes) {
      if (reachable.has(node.node_id) || node.inputs.length === 0) {
        continue;
      }
      const ready = node.inputs.every((port) => inputPortSatisfied(node.node_id, port, incoming, reachable));
      if (ready) {
        reachable.add(node.node_id);
        changed = true;
      }
    }
  }

  return reachable;
}

function activeNodeIdsFromSinks(nodes: WorkflowNodeInstance[], edges: WorkflowEdge[], reachable: Set<string>): { active: Set<string>; sinks: Set<string> } {
  const incoming = graphIncomingEdges(edges);
  const sinks = new Set<string>();
  for (const node of nodes) {
    if (!isSinkNode(node) || !reachable.has(node.node_id)) {
      continue;
    }
    const satisfied = node.inputs.every((port) => inputPortSatisfied(node.node_id, port, incoming, reachable));
    if (satisfied) {
      sinks.add(node.node_id);
    }
  }

  const active = new Set<string>(sinks);
  const stack = [...sinks];
  while (stack.length) {
    const current = stack.pop()!;
    for (const port of nodes.find((node) => node.node_id === current)?.inputs ?? []) {
      for (const edge of incoming.get(`${current}:${port.port_id}`) ?? []) {
        if (!active.has(edge.from_node)) {
          active.add(edge.from_node);
          stack.push(edge.from_node);
        }
      }
    }
  }
  return { active, sinks };
}

function upgradeLegacyWorkflow(workflow: WorkflowDefinition, pipeline: PipelineDefinition): WorkflowDefinition {
  if (!isLegacyGraph(workflow)) {
    return workflow;
  }
  return buildStarterWorkflow(
    {
      ...workflow,
      source: workflow.source === "manual" ? "manual" : "migrated_from_pipeline"
    },
    pipeline
  );
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

function classifyOutputBundle(exportConfig: ExportParameters): PipelineDefinition["output_bundle_id"] {
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

function activeCorpusInputIds(nodes: WorkflowNodeInstance[], activeNodeIds: Set<string>): string[] {
  return nodes
    .filter((node) => activeNodeIds.has(node.node_id) && node.node_type === "corpus_input")
    .map((node) => node.node_id);
}

export function validateWorkflowGraph(workflow: WorkflowDefinition): WorkflowValidation {
  const nodes = workflow.nodes.map(cloneNode);
  const normalizedEdges = normalizeEdgesWithNodes(workflow, nodes);
  const reachable = forwardReachableNodeIds(nodes, normalizedEdges);
  const { active, sinks } = activeNodeIdsFromSinks(nodes, normalizedEdges, reachable);
  const incoming = graphIncomingEdges(normalizedEdges);
  const issues: string[] = [];
  const missingInputsByNodeId: Record<string, string[]> = {};

  for (const node of nodes) {
    if (!node.inputs.length) {
      continue;
    }
    const missingPorts = node.inputs
      .filter((port) => !inputPortSatisfied(node.node_id, port, incoming, reachable))
      .map((port) => port.port_id);

    if (missingPorts.length) {
      missingInputsByNodeId[node.node_id] = missingPorts;
      issues.push(`${node.label} 缺少输入：${missingPorts.join("、")}`);
    }
  }

  if (!sinks.size) {
    issues.push("至少需要接入一个输出节点，当前工作流才可运行。");
  }

  const activeCorpusInputs = activeCorpusInputIds(nodes, active);
  if (!activeCorpusInputs.length) {
    issues.push("缺少语料输入节点，当前工作流没有可处理的语料来源。");
  }
  if (activeCorpusInputs.length > 1) {
    issues.push("当前运行时暂不支持多个语料输入同时进入执行链，请先保留一条语料支路。");
  }
  if (nodes.some((node) => active.has(node.node_id) && node.node_type === "merge_corpora")) {
    issues.push("当前运行时暂不支持合并语料节点执行，这类节点已允许建图，但还不能直接运行。");
  }

  return {
    valid: issues.length === 0,
    issues,
    reachable_node_ids: [...reachable],
    active_node_ids: [...active],
    sink_node_ids: [...sinks],
    missing_inputs_by_node_id: missingInputsByNodeId,
    normalized_edges: normalizedEdges
  };
}

function updateWorkflowEdges(workflow: WorkflowDefinition, edges: WorkflowEdge[]): WorkflowDefinition {
  return {
    ...workflow,
    source: "manual",
    updated_at: new Date().toISOString(),
    edges
  };
}

export function resolveActiveWorkflow(project: ProjectManifest | null | undefined): WorkflowDefinition | null {
  if (!project?.workflow_definitions?.length) {
    return null;
  }
  return (
    project.workflow_definitions.find((workflow) => workflow.workflow_id === project.active_workflow_id)
    ?? project.workflow_definitions[0]
    ?? null
  );
}

export function workflowOptionalToolboxNodes(): WorkflowNodeType[] {
  return (Object.entries(workflowNodeDefinitions) as Array<[WorkflowNodeType, WorkflowNodeDefinition]>)
    .filter(([, definition]) => !definition.hidden_from_toolbox)
    .sort((left, right) => left[1].category.localeCompare(right[1].category) || left[1].label.localeCompare(right[1].label, "zh-CN"))
    .map(([nodeType]) => nodeType);
}

export function workflowNodeCanRemove(): boolean {
  return true;
}

export function normalizeWorkflowGraph(workflow: WorkflowDefinition, pipeline: PipelineDefinition): WorkflowDefinition {
  const upgraded = upgradeLegacyWorkflow(workflow, pipeline);
  const nodes = upgraded.nodes.map((node) => {
    const definition = definitionForNode(node.node_type);
    return {
      ...cloneNode(node),
      label: node.label || definition.label,
      inputs: node.inputs?.length ? node.inputs.map((port) => ({ ...port })) : definition.inputs.map((port) => ({ ...port })),
      outputs: node.outputs?.length ? node.outputs.map((port) => ({ ...port })) : definition.outputs.map((port) => ({ ...port })),
      config: normalizeConfigNode(node.node_type, node.config ?? {}, pipeline),
      runtime_meta: {
        ...node.runtime_meta,
        step_id: definition.stepId,
        node_impl_version: node.runtime_meta?.node_impl_version ?? "2.0.0"
      }
    };
  });

  return {
    ...upgraded,
    graph_mode: "dag",
    source: upgraded.source ?? "manual",
    updated_at: new Date().toISOString(),
    nodes,
    edges: normalizeEdgesWithNodes({ ...upgraded, nodes }, nodes),
    viewport: {
      x: upgraded.viewport?.x ?? 0,
      y: upgraded.viewport?.y ?? 0,
      zoom: upgraded.viewport?.zoom ?? 0.82
    }
  };
}

export function addWorkflowNodeByType(
  workflow: WorkflowDefinition,
  nodeType: WorkflowNodeType,
  pipeline: PipelineDefinition
): WorkflowDefinition {
  const normalized = normalizeWorkflowGraph(workflow, pipeline);
  const definition = definitionForNode(nodeType);
  if (definition.singleton && normalized.nodes.some((node) => node.node_type === nodeType)) {
    return normalized;
  }
  const createdNode = createWorkflowNode(nodeType, pipeline);
  const siblingCount = normalized.nodes.filter((node) => node.node_type === nodeType).length;
  const basePosition = defaultPositionForWorkflowNode(createdNode);
  let candidatePosition = {
    x: basePosition.x + siblingCount * 42,
    y: basePosition.y + siblingCount * 56
  };

  while (normalized.nodes.some((node) =>
    Math.abs(node.position.x - candidatePosition.x) < 48
    && Math.abs(node.position.y - candidatePosition.y) < 48
  )) {
    candidatePosition = {
      x: candidatePosition.x + 36,
      y: candidatePosition.y + 48
    };
  }

  createdNode.position = candidatePosition;
  const nodes = [...normalized.nodes.map(cloneNode), createdNode];
  return {
    ...normalized,
    source: "manual",
    updated_at: new Date().toISOString(),
    nodes
  };
}

export function removeWorkflowNodeById(
  workflow: WorkflowDefinition,
  nodeId: string
): WorkflowDefinition {
  const nodes = workflow.nodes.filter((node) => node.node_id !== nodeId).map(cloneNode);
  const edges = workflow.edges
    .filter((edge) => edge.from_node !== nodeId && edge.to_node !== nodeId)
    .map(cloneEdge);
  return {
    ...workflow,
    source: "manual",
    updated_at: new Date().toISOString(),
    nodes,
    edges
  };
}

export function removeWorkflowNodeByType(
  workflow: WorkflowDefinition,
  nodeType: WorkflowNodeType,
  pipeline: PipelineDefinition
): WorkflowDefinition {
  const normalized = normalizeWorkflowGraph(workflow, pipeline);
  const target = normalized.nodes.find((node) => node.node_type === nodeType);
  return target ? removeWorkflowNodeById(normalized, target.node_id) : normalized;
}

export function restoreWorkflowDefaultEdges(workflow: WorkflowDefinition, pipeline: PipelineDefinition): WorkflowDefinition {
  const normalized = normalizeWorkflowGraph(workflow, pipeline);
  const starter = buildStarterWorkflow(normalized, pipeline);
  const nodes = normalized.nodes.map(cloneNode);
  const nodeByTypeMap = new Map(nodes.map((node) => [node.node_type, node]));
  const translatedEdges: WorkflowEdge[] = [];

  for (const edge of starter.edges) {
    const starterFrom = starter.nodes.find((node) => node.node_id === edge.from_node);
    const starterTo = starter.nodes.find((node) => node.node_id === edge.to_node);
    if (!starterFrom || !starterTo) {
      continue;
    }
    const fromNode = nodeByTypeMap.get(starterFrom.node_type);
    const toNode = nodeByTypeMap.get(starterTo.node_type);
    if (!fromNode || !toNode) {
      continue;
    }
    translatedEdges.push({
      edge_id: workflowEdgeId(),
      from_node: fromNode.node_id,
      from_port: edge.from_port,
      to_node: toNode.node_id,
      to_port: edge.to_port
    });
  }

  return updateWorkflowEdges(normalized, normalizeEdgesWithNodes({ ...normalized, edges: translatedEdges }, nodes));
}

export function workflowNodeStepId(node: WorkflowNodeInstance): PipelineStepId | null {
  const stepId = definitionForNode(node.node_type).stepId;
  return typeof stepId === "string" && executionOrder.includes(stepId as PipelineStepId)
    ? (stepId as PipelineStepId)
    : null;
}

export function defaultPositionForWorkflowNode(node: WorkflowNodeInstance): { x: number; y: number } {
  return { ...(defaultNodePositions[node.node_type] ?? { x: 120, y: 220 }) };
}

export function updateWorkflowNodePosition(
  workflow: WorkflowDefinition,
  nodeId: string,
  position: { x: number; y: number }
): WorkflowDefinition {
  return updateWorkflowNode(workflow, nodeId, (node) => ({
    ...node,
    position: {
      x: Math.round(position.x),
      y: Math.round(position.y)
    }
  }));
}

export function autoLayoutWorkflow(workflow: WorkflowDefinition): WorkflowDefinition {
  const grouped = workflowOptionalToolboxNodes().reduce<Record<string, WorkflowNodeInstance[]>>((accumulator, nodeType) => {
    accumulator[nodeType] = workflow.nodes.filter((node) => node.node_type === nodeType).map(cloneNode);
    return accumulator;
  }, {});

  const categoryColumns: Array<Array<WorkflowNodeType>> = [
    ["corpus_input", "dictionary_input"],
    ["merge_corpora", "clean_text", "normalize_text", "tokenize", "apply_dictionary_rules", "filter_terms"],
    ["frequency_statistics", "term_year_analysis", "cooccurrence_analysis", "keyword_extraction", "keyword_clustering", "institution_topic_analysis"],
    ["save_csv", "save_xlsx", "save_png", "save_html_report"],
    ["note", "group"]
  ];
  const placed: WorkflowNodeInstance[] = [];
  let currentX = 120;
  categoryColumns.forEach((column, columnIndex) => {
    const columnWidth = Math.max(...column.map((nodeType) => workflowNodeFrameForType(nodeType).w), 280);
    let currentY = 80;
    for (const nodeType of column) {
      const nodes = [...(grouped[nodeType] ?? [])].sort(
        (left, right) => left.position.y - right.position.y || left.position.x - right.position.x
      );
      for (const node of nodes) {
        const nodeFrame = workflowNodeFrameForType(node.node_type);
        placed.push({
          ...node,
          position: {
            x: currentX,
            y: currentY
          }
        });
        currentY += nodeFrame.h + 56;
      }
    }
    currentX += columnWidth + (columnIndex === 0 ? 180 : 140);
  });

  return {
    ...workflow,
    source: "manual",
    updated_at: new Date().toISOString(),
    viewport: {
      ...workflow.viewport,
      x: 0,
      y: 0,
      zoom: 0.82
    },
    nodes: placed.length ? placed : workflow.nodes.map((node) => ({
      ...cloneNode(node),
      position: defaultPositionForWorkflowNode(node)
    }))
  };
}

export function updateWorkflowViewport(
  workflow: WorkflowDefinition,
  patch: Partial<WorkflowDefinition["viewport"]>
): WorkflowDefinition {
  return {
    ...workflow,
    source: "manual",
    updated_at: new Date().toISOString(),
    viewport: {
      ...workflow.viewport,
      ...patch
    }
  };
}

export function workflowConnectionTargets(
  workflow: WorkflowDefinition,
  fromNodeId: string,
  fromPortId: string
): WorkflowTargetPortCandidate[] {
  const nodes = nodeLookupById(workflow.nodes);
  return workflow.nodes
    .flatMap((node) => node.inputs.map((port) => ({ node, port })))
    .filter(({ node, port }) => canConnectPortPair(nodes, fromNodeId, fromPortId, node.node_id, port.port_id))
    .map(({ node, port }) => ({
      node_id: node.node_id,
      node_type: node.node_type,
      port_id: port.port_id,
      port_type: port.port_type
    }));
}

export function createWorkflowEdge(
  workflow: WorkflowDefinition,
  fromNodeId: string,
  fromPortId: string,
  toNodeId: string,
  toPortId: string
): WorkflowDefinition {
  const nodes = workflow.nodes.map(cloneNode);
  const nodeMap = nodeLookupById(nodes);
  if (!canConnectPortPair(nodeMap, fromNodeId, fromPortId, toNodeId, toPortId)) {
    return workflow;
  }
  const targetAllowsMultiple = portAcceptsMultiple(nodeMap.get(toNodeId), toPortId);
  const candidateEdges = workflow.edges
    .filter((edge) => targetAllowsMultiple ? true : !(edge.to_node === toNodeId && edge.to_port === toPortId))
    .map(cloneEdge);
  if (edgeCreatesCycle(nodes, candidateEdges, fromNodeId, toNodeId)) {
    return workflow;
  }
  const nextEdge: WorkflowEdge = {
    edge_id: workflowEdgeId(),
    from_node: fromNodeId,
    from_port: fromPortId,
    to_node: toNodeId,
    to_port: toPortId
  };
  return updateWorkflowEdges(workflow, normalizeEdgesWithNodes({ ...workflow, edges: [...candidateEdges, nextEdge] }, nodes));
}

export function removeWorkflowEdge(workflow: WorkflowDefinition, edgeId: string): WorkflowDefinition {
  return updateWorkflowEdges(
    workflow,
    workflow.edges.filter((edge) => edge.edge_id !== edgeId).map(cloneEdge)
  );
}

function applyAnalysisNodeConfig(
  compiled: PipelineDefinition,
  node: WorkflowNodeInstance
): PipelineDefinition {
  const next = clonePipeline(compiled);
  const config = node.config ?? {};
  if (node.node_type === "frequency_statistics") {
    next.analysis.top_n = Number(config.top_n ?? next.analysis.top_n);
  } else if (node.node_type === "cooccurrence_analysis") {
    next.analysis.cooccurrence_window = Number(config.cooccurrence_window ?? next.analysis.cooccurrence_window);
    next.analysis.min_cooccurrence = Number(config.min_cooccurrence ?? next.analysis.min_cooccurrence);
  } else if (node.node_type === "keyword_extraction") {
    next.analysis.top_k_per_doc = Number(config.top_k_per_doc ?? next.analysis.top_k_per_doc);
    next.analysis.top_k_project = Number(config.top_k_project ?? next.analysis.top_k_project);
  } else if (node.node_type === "keyword_clustering") {
    next.analysis.keyword_cluster_k = Number(config.keyword_cluster_k ?? next.analysis.keyword_cluster_k);
    next.analysis.topic_model_k = Number(config.topic_model_k ?? next.analysis.topic_model_k);
  } else if (node.node_type === "institution_topic_analysis") {
    next.analysis.topic_model_k = Number(config.topic_model_k ?? next.analysis.topic_model_k);
  } else if (node.node_type === "analyze_corpus") {
    next.analysis = {
      ...next.analysis,
      ...(config as Partial<AnalysisParameters>)
    };
  }
  return next;
}

export function compilePipelineFromWorkflow(workflow: WorkflowDefinition, pipeline: PipelineDefinition): PipelineDefinition {
  const compiled = clonePipeline(pipeline);
  const normalized = normalizeWorkflowGraph(workflow, pipeline);
  const validation = validateWorkflowGraph(normalized);
  const activeNodeIds = new Set(validation.active_node_ids);
  const activeNodes = normalized.nodes.filter((node) => activeNodeIds.has(node.node_id));

  const corpusInput = activeNodes.find((node) => node.node_type === "corpus_input");
  if (corpusInput) {
    compiled.run_scope = {
      ...compiled.run_scope,
      ...(corpusInput.config as Partial<RunScopeDefinition>),
      source_values: [...((corpusInput.config.source_values as string[] | undefined) ?? compiled.run_scope.source_values)],
      institution_values: [...((corpusInput.config.institution_values as string[] | undefined) ?? compiled.run_scope.institution_values)],
      category_values: [...((corpusInput.config.category_values as string[] | undefined) ?? compiled.run_scope.category_values)],
      selected_doc_ids: [...((corpusInput.config.selected_doc_ids as string[] | undefined) ?? compiled.run_scope.selected_doc_ids)]
    };
  } else {
    const legacyScope = activeNodes.find((node) => node.node_type === "filter_corpus");
    if (legacyScope) {
      compiled.run_scope = {
        ...compiled.run_scope,
        ...(legacyScope.config as Partial<RunScopeDefinition>),
        source_values: [...((legacyScope.config.source_values as string[] | undefined) ?? compiled.run_scope.source_values)],
        institution_values: [...((legacyScope.config.institution_values as string[] | undefined) ?? compiled.run_scope.institution_values)],
        category_values: [...((legacyScope.config.category_values as string[] | undefined) ?? compiled.run_scope.category_values)],
        selected_doc_ids: [...((legacyScope.config.selected_doc_ids as string[] | undefined) ?? compiled.run_scope.selected_doc_ids)]
      };
    }
  }

  const dictionaryInput = activeNodes.find((node) => node.node_type === "dictionary_input");
  if (dictionaryInput) {
    compiled.tokenization = {
      ...compiled.tokenization,
      use_custom_lexicon: Boolean(dictionaryInput.config.use_custom_lexicon ?? compiled.tokenization.use_custom_lexicon),
      use_phrase_lexicon: Boolean(dictionaryInput.config.use_phrase_lexicon ?? compiled.tokenization.use_phrase_lexicon)
    };
    compiled.normalization = {
      ...compiled.normalization,
      apply_regex_rules: Boolean(dictionaryInput.config.apply_regex_rules ?? compiled.normalization.apply_regex_rules)
    };
    compiled.dictionary = {
      ...compiled.dictionary,
      apply_standard_terms: Boolean(dictionaryInput.config.apply_standard_terms ?? compiled.dictionary.apply_standard_terms),
      apply_synonym_map: Boolean(dictionaryInput.config.apply_synonym_map ?? compiled.dictionary.apply_synonym_map),
      apply_near_synonym_map: Boolean(dictionaryInput.config.apply_near_synonym_map ?? compiled.dictionary.apply_near_synonym_map),
      apply_stopwords: Boolean(dictionaryInput.config.apply_stopwords ?? compiled.dictionary.apply_stopwords),
      apply_exclusion_terms: Boolean(dictionaryInput.config.apply_exclusion_terms ?? compiled.dictionary.apply_exclusion_terms)
    };
  }

  for (const node of activeNodes) {
    if (node.ui_state?.bypassed) {
      continue;
    }
    if (node.node_type === "clean_text") {
      compiled.cleaning = { ...compiled.cleaning, ...(node.config as Partial<PipelineDefinition["cleaning"]>) };
    } else if (node.node_type === "normalize_text") {
      compiled.normalization = { ...compiled.normalization, ...(node.config as Partial<PipelineDefinition["normalization"]>) };
    } else if (node.node_type === "tokenize") {
      compiled.tokenization = { ...compiled.tokenization, ...(node.config as Partial<PipelineDefinition["tokenization"]>) };
    } else if (node.node_type === "apply_dictionary_rules") {
      compiled.dictionary = { ...compiled.dictionary, ...(node.config as Partial<PipelineDefinition["dictionary"]>) };
    } else if (node.node_type === "filter_terms") {
      compiled.filtering = { ...compiled.filtering, ...(node.config as Partial<PipelineDefinition["filtering"]>) };
    } else if (
      node.node_type === "frequency_statistics"
      || node.node_type === "term_year_analysis"
      || node.node_type === "cooccurrence_analysis"
      || node.node_type === "keyword_extraction"
      || node.node_type === "keyword_clustering"
      || node.node_type === "institution_topic_analysis"
      || node.node_type === "analyze_corpus"
    ) {
      Object.assign(compiled, applyAnalysisNodeConfig(compiled, node));
    } else if (node.node_type === "save_png") {
      compiled.export.chart_dpi = Number(node.config.chart_dpi ?? compiled.export.chart_dpi);
    } else if (node.node_type === "save_html_report") {
      compiled.export.include_audit = Boolean(node.config.include_audit ?? compiled.export.include_audit);
    } else if (node.node_type === "export_results") {
      compiled.export = { ...compiled.export, ...(node.config as Partial<ExportParameters>) };
    }
  }

  let exportConfig = resetExportFlags(defaultExport(compiled));
  const activeNodeTypes = new Set(activeNodes.filter((node) => !node.ui_state?.bypassed).map((node) => node.node_type));

  if (activeNodeTypes.has("save_csv")) {
    exportConfig.export_csv = true;
  }
  if (activeNodeTypes.has("save_xlsx")) {
    exportConfig.export_xlsx = true;
  }
  if (activeNodeTypes.has("save_png")) {
    exportConfig.export_png = true;
  }
  if (activeNodeTypes.has("save_html_report")) {
    exportConfig.export_html_report = true;
  }
  if (activeNodeTypes.has("export_results")) {
    exportConfig = {
      ...exportConfig,
      ...(activeNodes.find((node) => node.node_type === "export_results")?.config as Partial<ExportParameters> | undefined)
    };
  }
  compiled.export = {
    ...compiled.export,
    ...exportConfig
  };

  const enabledSteps = new Set<PipelineStepId>(["ingestion"]);
  for (const node of activeNodes) {
    if (node.ui_state?.bypassed) {
      continue;
    }
    const stepId = workflowNodeStepId(node);
    if (stepId) {
      enabledSteps.add(stepId);
    }
  }

  compiled.execution_order = [...executionOrder];
  compiled.enabled_steps = executionOrder.filter((stepId) => enabledSteps.has(stepId));
  compiled.output_bundle_id = classifyOutputBundle(compiled.export);
  compiled.recipe_id = activeNodeTypes.has("analyze_corpus") || activeNodeTypes.has("export_results")
    ? compiled.recipe_id
    : "custom";
  return compiled;
}

export function syncWorkflowFromPipeline(
  workflow: WorkflowDefinition,
  pipeline: PipelineDefinition,
  source: WorkflowDefinition["source"] = workflow.source
): WorkflowDefinition {
  const normalized = workflow.nodes.length
    ? normalizeWorkflowGraph(workflow, pipeline)
    : buildStarterWorkflow(
      {
        ...workflow,
        source
      },
      pipeline
    );

  const nodes = normalized.nodes.map((node) => ({
    ...cloneNode(node),
    config: normalizeConfigNode(node.node_type, node.config ?? {}, pipeline)
  }));

  return {
    ...normalized,
    source,
    meta: {
      ...normalized.meta,
      template_id: pipeline.recipe_id,
      output_bundle_id: pipeline.output_bundle_id
    },
    nodes,
    updated_at: new Date().toISOString()
  };
}

export function updateWorkflowNode(
  workflow: WorkflowDefinition,
  nodeId: string,
  updater: (node: WorkflowNodeInstance) => WorkflowNodeInstance
): WorkflowDefinition {
  return {
    ...workflow,
    source: "manual",
    updated_at: new Date().toISOString(),
    nodes: workflow.nodes.map((node) => (node.node_id === nodeId ? updater(cloneNode(node)) : cloneNode(node)))
  };
}

export function updateWorkflowMeta(
  workflow: WorkflowDefinition,
  patch: Partial<WorkflowDefinition["meta"]>
): WorkflowDefinition {
  return {
    ...workflow,
    source: "manual",
    updated_at: new Date().toISOString(),
    meta: {
      ...workflow.meta,
      ...patch
    }
  };
}

export function buildBlankWorkflowFromPipeline(
  workflowId: string,
  name: string,
  pipeline: PipelineDefinition
): WorkflowDefinition {
  const timestamp = new Date().toISOString();
  return {
    workflow_id: workflowId,
    name,
    version: "2.0.0",
    graph_mode: "dag",
    source: "manual",
    meta: {
      template_id: pipeline.recipe_id ?? "custom",
      output_bundle_id: pipeline.output_bundle_id ?? "custom"
    },
    nodes: [],
    edges: [],
    groups: [],
    viewport: {
      x: 0,
      y: 0,
      zoom: 0.82
    },
    created_at: timestamp,
    updated_at: timestamp
  };
}

export function workflowNodeDefinition(
  nodeType: WorkflowNodeType
): WorkflowNodeDefinition {
  return definitionForNode(nodeType);
}

export function workflowNodeDescriptionForType(nodeType: WorkflowNodeType): string {
  return nodeDescription(nodeType);
}
