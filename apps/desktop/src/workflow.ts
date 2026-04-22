import type {
  ExportParameters,
  PipelineDefinition,
  PipelineStepId,
  ProjectManifest,
  RegisteredWorkflowNodeDefinition,
  WorkflowDefinition,
  WorkflowEdge,
  WorkflowNodeInstance,
  WorkflowNodeType,
  WorkflowPort,
  WorkflowPortType
} from "@textflow/shared-types";
import { compileActiveWorkflowNodesIntoPipeline } from "./workflowNodeCompilers";
import {
  analysisResultTypes,
  builtinWorkflowNodeDefinition,
  builtinWorkflowNodeDescription,
  builtinWorkflowNodeFrameForType,
  builtinWorkflowOptionalToolboxNodes,
  corpusPortOrder,
  defaultExport,
  defaultNodePositions,
  defaultRunScope,
  executionOrder,
  legacyNodeTypes,
  renderableSourceTypes,
  sinkNodeTypes,
  tableSourceTypes,
  type WorkflowNodeDefinition
} from "./workflowNodeCatalog";

type WorkflowPortDirection = "inputs" | "outputs";

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
  return builtinWorkflowNodeFrameForType(nodeType);
}

function fallbackWorkflowNodeDefinition(nodeType: WorkflowNodeType): WorkflowNodeDefinition {
  return {
    label: String(nodeType),
    description: "插件节点或尚未在前端内置目录中声明的节点。",
    category: "process",
    inputs: [],
    outputs: [],
    stepId: "utility",
    size: { w: 320, h: 220 },
    defaultConfig: () => ({})
  };
}

function defaultConfigFromRegisteredDefinition(definition: RegisteredWorkflowNodeDefinition): Record<string, unknown> {
  return definition.params.reduce<Record<string, unknown>>((config, param) => {
    if (param.default_value !== undefined) {
      config[param.param_id] = param.default_value;
    }
    return config;
  }, {});
}

function definitionForNode(
  nodeType: WorkflowNodeType,
  registeredDefinition?: RegisteredWorkflowNodeDefinition
): WorkflowNodeDefinition {
  const builtinDefinition = builtinWorkflowNodeDefinition(nodeType);
  if (builtinDefinition) {
    return builtinDefinition;
  }
  if (registeredDefinition) {
    return {
      label: registeredDefinition.title,
      description: registeredDefinition.description ?? "",
      category: registeredDefinition.category,
      hidden_from_toolbox: registeredDefinition.hidden_from_toolbox,
      singleton: registeredDefinition.singleton,
      inputs: registeredDefinition.inputs.map((port) => ({ ...port })),
      outputs: registeredDefinition.outputs.map((port) => ({ ...port })),
      stepId: registeredDefinition.runtime.step_id,
      size: { w: 320, h: 220 },
      defaultConfig: () => defaultConfigFromRegisteredDefinition(registeredDefinition)
    };
  }
  return fallbackWorkflowNodeDefinition(nodeType);
}

function createWorkflowNode(
  nodeType: WorkflowNodeType,
  pipeline: PipelineDefinition,
  registeredDefinition?: RegisteredWorkflowNodeDefinition
): WorkflowNodeInstance {
  const definition = definitionForNode(nodeType, registeredDefinition);
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
  return builtinWorkflowNodeDescription(nodeType) || definitionForNode(nodeType).description;
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
  const builtinDefinition = builtinWorkflowNodeDefinition(nodeType);
  const base = builtinDefinition ? builtinDefinition.defaultConfig(pipeline) : {};
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
    "term_document_analysis",
    "term_year_analysis",
    "cooccurrence_analysis",
    "feature_term_selection",
    "keyword_extraction",
    "keyword_clustering",
    "institution_keyword_analysis",
    "institution_topic_analysis",
    "document_clustering"
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
      const featureTermNode = nodeByType(nodes, "feature_term_selection");
      if (featureTermNode) {
        edges.push(makeEdge(featureTermNode, "feature_term_table", analysisNode, "feature_term_table_in"));
      }
      continue;
    }
    if (analysisType === "institution_keyword_analysis") {
      if (keywordNode) {
        edges.push(makeEdge(keywordNode, "keyword_table", analysisNode, "keyword_table_in"));
      }
      continue;
    }
    if (analysisType === "institution_topic_analysis") {
      const clusterNode = nodeByType(nodes, "keyword_clustering");
      if (clusterNode) {
        edges.push(makeEdge(clusterNode, "keyword_cluster_table", analysisNode, "keyword_cluster_table_in"));
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
    ["save_csv", ["frequency_statistics", "term_document_analysis", "term_year_analysis", "cooccurrence_analysis", "feature_term_selection", "keyword_extraction", "keyword_clustering", "institution_keyword_analysis", "institution_topic_analysis", "document_clustering"]],
    ["save_xlsx", ["frequency_statistics", "term_document_analysis", "term_year_analysis", "cooccurrence_analysis", "feature_term_selection", "keyword_extraction", "keyword_clustering", "institution_keyword_analysis", "institution_topic_analysis", "document_clustering"]],
    ["save_png", ["frequency_statistics", "keyword_extraction", "keyword_clustering", "institution_topic_analysis", "document_clustering"]],
    ["save_html_report", ["frequency_statistics", "term_document_analysis", "term_year_analysis", "cooccurrence_analysis", "feature_term_selection", "keyword_extraction", "keyword_clustering", "institution_keyword_analysis", "institution_topic_analysis", "document_clustering"]]
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
  const hasActiveMerge = nodes.some((node) => active.has(node.node_id) && node.node_type === "merge_corpora");
  if (!activeCorpusInputs.length) {
    issues.push("缺少语料输入节点，当前工作流没有可处理的语料来源。");
  }
  if (activeCorpusInputs.length > 1 && !hasActiveMerge) {
    issues.push("多个语料输入需要先汇入“合并语料”节点，当前还有多条语料支路直接参与执行。");
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
  return builtinWorkflowOptionalToolboxNodes();
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
  pipeline: PipelineDefinition,
  registeredDefinition?: RegisteredWorkflowNodeDefinition
): WorkflowDefinition {
  const normalized = normalizeWorkflowGraph(workflow, pipeline);
  const definition = definitionForNode(nodeType, registeredDefinition);
  if (definition.singleton && normalized.nodes.some((node) => node.node_type === nodeType)) {
    return normalized;
  }
  const createdNode = createWorkflowNode(nodeType, pipeline, registeredDefinition);
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
    ["frequency_statistics", "term_document_analysis", "term_year_analysis", "cooccurrence_analysis", "feature_term_selection"],
    ["keyword_extraction", "keyword_clustering", "institution_keyword_analysis", "institution_topic_analysis", "document_clustering"],
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

export function compilePipelineFromWorkflow(workflow: WorkflowDefinition, pipeline: PipelineDefinition): PipelineDefinition {
  const normalized = normalizeWorkflowGraph(workflow, pipeline);
  const validation = validateWorkflowGraph(normalized);
  const activeNodeIds = new Set(validation.active_node_ids);
  const activeNodes = normalized.nodes.filter((node) => activeNodeIds.has(node.node_id));
  const compiled = compileActiveWorkflowNodesIntoPipeline(activeNodes, pipeline);
  return {
    ...compiled,
    recipe_id: normalized.meta?.template_id || compiled.recipe_id,
    output_bundle_id: normalized.meta?.output_bundle_id || compiled.output_bundle_id
  };
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
