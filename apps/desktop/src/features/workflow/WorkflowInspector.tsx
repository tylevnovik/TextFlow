import { useMemo, useState, type ReactNode } from "react";
import { Button, Divider } from "@fluentui/react-components";
import type {
  ArtifactRecord,
  CorpusItem,
  ProjectManifest,
  RunScopeDefinition,
  WorkspaceSnapshot,
  WorkflowDefinition,
  WorkflowEdge,
  WorkflowNodeInstance,
  WorkflowNodeRuntimeState
} from "@textflow/shared-types";
import type { WorkbenchSelection } from "../../app/workbenchSelection";
import { buildRunCommands } from "../runs/runCommands";
import { resolveWorkflowRuntimeProfile, workflowNodeDefinition } from "../../workflow";
import { DynamicNodeEditor } from "./DynamicNodeEditor";
import {
  workflowNodeConfigFacts,
  type WorkflowNodeConfigFact
} from "./workflowNodeConfigFacts";
import {
  WORKFLOW_NODE_EDITOR_ACTION_EVENT,
  type WorkflowNodeEditorAction
} from "./workflowWorkbenchActions";
import type { WorkflowNodeEditorContext } from "../../workflowNodeRegistry";

type WorkflowInspectorSelection = Extract<
  WorkbenchSelection,
  { kind: "workflow" | "workflow_toolbox" | "workflow_node" | "workflow_edge" }
>;

export function WorkflowInspector({
  selection,
  project,
  workflow,
  runtimeStates,
  snapshot,
  loading = false,
  onSetActivePage
}: {
  selection: WorkflowInspectorSelection;
  project: ProjectManifest;
  workflow: WorkflowDefinition | null | undefined;
  runtimeStates?: Record<string, WorkflowNodeRuntimeState>;
  snapshot?: WorkspaceSnapshot;
  loading?: boolean;
  onSetActivePage?: (page: "dictionaries") => void;
}) {
  if (!workflow) {
    return (
      <InspectorCard
        eyebrow="节点图"
        title="节点图未找到"
        rows={[["状态", "当前项目没有可用 workflow"]]}
      />
    );
  }

  if (selection.kind === "workflow_node") {
    const node = workflow.nodes.find((item) => item.node_id === selection.nodeId) ?? null;
    return (
      <WorkflowNodeInspector
        node={selection.node ?? node}
        project={project}
        workflow={workflow}
        runtime={node ? runtimeStates?.[node.node_id] : undefined}
        snapshot={snapshot}
        loading={loading}
        onSetActivePage={onSetActivePage}
      />
    );
  }

  if (selection.kind === "workflow_edge") {
    const edge = workflow.edges.find((item) => item.edge_id === selection.edgeId) ?? null;
    return <WorkflowEdgeInspector workflow={workflow} edge={edge} />;
  }

  const latestRun = project.run_history.find((run) => run.workflow_id === workflow.workflow_id)
    ?? project.run_history[0];

  return (
    <InspectorCard
      eyebrow="节点图"
      title={workflow.name}
      rows={[
        ["版本", workflow.version],
        ["最近运行", latestRun?.status ?? "暂无"],
        ["产物", `${project.artifact_records.length} 个`]
      ]}
    />
  );
}

function WorkflowNodeInspector({
  node,
  project,
  workflow,
  runtime,
  snapshot,
  loading,
  onSetActivePage
}: {
  node: WorkflowNodeInstance | null;
  project: ProjectManifest;
  workflow: WorkflowDefinition;
  runtime?: WorkflowNodeRuntimeState;
  snapshot?: WorkspaceSnapshot;
  loading: boolean;
  onSetActivePage?: (page: "dictionaries") => void;
}) {
  const [documentPickerQuery, setDocumentPickerQuery] = useState("");
  const nodeDefinitionsByType = useMemo(
    () => new Map((snapshot?.node_definitions ?? []).map((item) => [item.type, item])),
    [snapshot?.node_definitions]
  );
  const draftRuntimeProfile = useMemo(
    () => resolveWorkflowRuntimeProfile(project, workflow),
    [project, workflow]
  );
  const corpus = snapshot?.corpus ?? [];
  const availableSources = useMemo(
    () => uniqueSorted(corpus.map((item) => item.source)),
    [corpus]
  );
  const availableInstitutions = useMemo(
    () => uniqueSorted(corpus.map((item) => item.institution)),
    [corpus]
  );
  const availableCategories = useMemo(
    () => uniqueSorted(corpus.map((item) => item.category_or_tag)),
    [corpus]
  );

  if (!node) {
    return (
      <InspectorCard
        eyebrow="节点参数"
        title="节点未找到"
        rows={[["状态", "当前选择已不在节点图中"]]}
      />
    );
  }

  const definition = workflowNodeDefinition(node.node_type);
  const artifacts = project.artifact_records.filter((artifact) => artifact.node_id === node.node_id);
  const configKeys = Object.keys(node.config ?? {});
  const exportCommands = buildRunCommands({ loading: false, artifact: artifacts[0] }).filter((command) => command.formats);

  const dispatchEditorAction = (action: WorkflowNodeEditorAction) => {
    window.dispatchEvent(new CustomEvent<WorkflowNodeEditorAction>(WORKFLOW_NODE_EDITOR_ACTION_EVENT, {
      detail: action
    }));
  };

  const runScopeForNode = (item: WorkflowNodeInstance | null | undefined): RunScopeDefinition => {
    const baseScope = normalizeRunScope(draftRuntimeProfile.run_scope);
    if (!item || item.node_type !== "corpus_input") {
      return baseScope;
    }
    return normalizeRunScope({
      ...baseScope,
      ...(item.config as Partial<RunScopeDefinition>)
    });
  };

  const editorContext: WorkflowNodeEditorContext | null = snapshot ? {
    node,
    project,
    snapshot: { corpus },
    draftRuntimeProfile,
    loading,
    nodeDefinitionsByType,
    availableSources,
    availableInstitutions,
    availableCategories,
    documentPickerQuery,
    setDocumentPickerQuery,
    setActivePage: (page) => onSetActivePage?.(page),
    bindDictionaryTableToWorkflow: (tableId) => dispatchEditorAction({
      type: "bind_dictionary_table",
      workflowId: workflow.workflow_id,
      tableId
    }),
    runScopeForNode,
    runScopeSummary,
    corpusMatchesRunScope,
    updateNodeConfig: (nodeId, patch) => dispatchEditorAction({
      type: "update_config",
      workflowId: workflow.workflow_id,
      nodeId,
      patch
    }),
    updateRunScope: (nodeId, patch) => dispatchEditorAction({
      type: "update_config",
      workflowId: workflow.workflow_id,
      nodeId,
      patch
    }),
    toggleScopeArrayValue: (nodeId, field, value) => {
      const scope = runScopeForNode(node);
      const values = scope[field];
      dispatchEditorAction({
        type: "update_config",
        workflowId: workflow.workflow_id,
        nodeId,
        patch: {
          [field]: values.includes(value)
            ? values.filter((item) => item !== value)
            : [...values, value]
        }
      });
    },
    toggleSelectedDocument: (nodeId, docId) => {
      const scope = runScopeForNode(node);
      dispatchEditorAction({
        type: "update_config",
        workflowId: workflow.workflow_id,
        nodeId,
        patch: {
          selected_doc_ids: scope.selected_doc_ids.includes(docId)
            ? scope.selected_doc_ids.filter((item) => item !== docId)
            : [...scope.selected_doc_ids, docId]
        }
      });
    },
    enabledDictionaryEntryCount
  } : null;
  const dynamicDefinition = nodeDefinitionsByType.get(node.node_type);
  const configFacts = workflowNodeConfigFacts({
    node,
    definition: dynamicDefinition,
    runtimeProfile: draftRuntimeProfile,
    project,
    corpus,
    runScope: runScopeForNode(node),
    corpusMatchesRunScope
  });

  return (
    <InspectorCard
      eyebrow="节点参数"
      title={node.label}
      rows={[
        ["类型", definition.label],
        ["输入", node.inputs.map((port) => `${port.label ?? port.port_id}:${port.port_type}`).join(" / ") || "无"],
        ["输出", node.outputs.map((port) => `${port.label ?? port.port_id}:${port.port_type}`).join(" / ") || "无"],
        ["运行状态", runtime ? runtimeStatusLabel(runtime.status) : "尚未执行"],
        ["配置", configKeys.length ? `${configKeys.length} 项` : "使用默认配置"],
        ["产物", `${artifacts.length} 个`]
      ]}
    >
      <div className="workflow-inspector-excerpt">
        <strong>说明</strong>
        <p>{definition.description || "该节点使用当前默认执行器。"}</p>
      </div>
      <WorkflowNodeFactGrid facts={configFacts} />
      {editorContext && (
        <div className="workflow-inspector-editor">
          <strong>配置</strong>
          <DynamicNodeEditor context={editorContext} definition={dynamicDefinition} />
        </div>
      )}
      <ArtifactList artifacts={artifacts} />
      {artifacts.length > 0 && (
        <div className="run-inspector-actions" aria-label="节点产物导出动作">
          {exportCommands.slice(0, 4).map((command) => (
            <Button size="small" appearance="subtle" key={command.id}>
              {command.label}
            </Button>
          ))}
        </div>
      )}
      {runtime?.output_summary && (
        <div className="workflow-inspector-excerpt">
          <strong>最近输出</strong>
          <p>{runtime.output_summary}</p>
        </div>
      )}
      {runtime?.error && (
        <div className="workflow-inspector-warning">
          <strong>错误</strong>
          <p>{runtime.error}</p>
        </div>
      )}
    </InspectorCard>
  );
}

function WorkflowNodeFactGrid({ facts }: { facts: WorkflowNodeConfigFact[] }) {
  if (!facts.length) {
    return null;
  }
  return (
    <div className="workflow-inspector-config-facts" aria-label="节点当前配置摘要">
      {facts.map((fact) => (
        <span key={`${fact.label}-${fact.value}`} className={fact.tone ? `is-${fact.tone}` : undefined}>
          <b>{fact.label}</b>
          <em>{fact.value}</em>
        </span>
      ))}
    </div>
  );
}

function WorkflowEdgeInspector({
  workflow,
  edge
}: {
  workflow: WorkflowDefinition;
  edge: WorkflowEdge | null;
}) {
  if (!edge) {
    return (
      <InspectorCard
        eyebrow="连线"
        title="连线未找到"
        rows={[["状态", "当前选择已不在节点图中"]]}
      />
    );
  }

  const source = workflow.nodes.find((node) => node.node_id === edge.from_node);
  const target = workflow.nodes.find((node) => node.node_id === edge.to_node);
  const sourcePort = source?.outputs.find((port) => port.port_id === edge.from_port);
  const targetPort = target?.inputs.find((port) => port.port_id === edge.to_port);
  const isCompatible = Boolean(sourcePort && targetPort && sourcePort.port_type === targetPort.port_type);

  return (
    <InspectorCard
      eyebrow="连线"
      title={`${source?.label ?? edge.from_node} -> ${target?.label ?? edge.to_node}`}
      rows={[
        ["来源节点", source?.label ?? edge.from_node],
        ["来源端口", `${sourcePort?.label ?? edge.from_port} · ${sourcePort?.port_type ?? "未知"}`],
        ["目标节点", target?.label ?? edge.to_node],
        ["目标端口", `${targetPort?.label ?? edge.to_port} · ${targetPort?.port_type ?? "未知"}`],
        ["兼容性", isCompatible ? "端口类型匹配" : "等待校验"]
      ]}
    />
  );
}

function ArtifactList({ artifacts }: { artifacts: ArtifactRecord[] }) {
  if (!artifacts.length) {
    return null;
  }

  return (
    <div className="workflow-inspector-artifacts" aria-label="节点产物">
      {artifacts.slice(0, 4).map((artifact) => (
        <article key={artifact.artifact_id}>
          <strong>{artifact.kind}</strong>
          <span>{artifact.artifact_id}</span>
        </article>
      ))}
    </div>
  );
}

function InspectorCard({
  eyebrow,
  title,
  rows,
  children
}: {
  eyebrow: string;
  title: string;
  rows: Array<[string, string]>;
  children?: ReactNode;
}) {
  return (
    <div className="workbench-inspector-card workflow-inspector-card">
      <p className="workbench-kicker">{eyebrow}</p>
      <h3>{title}</h3>
      <Divider />
      <dl className="workbench-inspector-list">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {children}
    </div>
  );
}

function runtimeStatusLabel(status: WorkflowNodeRuntimeState["status"]): string {
  switch (status) {
    case "running":
      return "运行中";
    case "completed":
      return "已完成";
    case "cached":
      return "缓存命中";
    case "failed":
      return "失败";
    case "skipped":
      return "已跳过";
    default:
      return "待执行";
  }
}

function normalizeRunScope(scope: Partial<RunScopeDefinition> | undefined): RunScopeDefinition {
  return {
    mode: scope?.mode ?? "all_documents",
    source_values: [...(scope?.source_values ?? [])],
    institution_values: [...(scope?.institution_values ?? [])],
    category_values: [...(scope?.category_values ?? [])],
    year_from: scope?.year_from ?? null,
    year_to: scope?.year_to ?? null,
    selected_doc_ids: [...(scope?.selected_doc_ids ?? [])]
  };
}

function runScopeSummary(scope: RunScopeDefinition, totalCount: number, matchedCount: number): string {
  if (scope.mode === "selected_documents") {
    return `已手动选择 ${scope.selected_doc_ids.length} 篇文档，当前能命中 ${matchedCount}/${totalCount} 篇。`;
  }
  if (scope.mode === "filtered_subset") {
    const parts: string[] = [];
    if (scope.source_values.length) {
      parts.push(`来源=${scope.source_values.join("、")}`);
    }
    if (scope.institution_values.length) {
      parts.push(`机构=${scope.institution_values.join("、")}`);
    }
    if (scope.category_values.length) {
      parts.push(`标签=${scope.category_values.join("、")}`);
    }
    if (scope.year_from || scope.year_to) {
      if (scope.year_from && scope.year_to) {
        parts.push(`年份=${scope.year_from}-${scope.year_to}`);
      } else if (scope.year_from) {
        parts.push(`年份>=${scope.year_from}`);
      } else if (scope.year_to) {
        parts.push(`年份<=${scope.year_to}`);
      }
    }
    return `按条件处理：${parts.join("；") || "尚未设置具体条件"}，当前能命中 ${matchedCount}/${totalCount} 篇。`;
  }
  return `处理项目里的全部资料，共 ${matchedCount}/${totalCount} 篇文档。`;
}

function corpusMatchesRunScope(item: CorpusItem, scope: RunScopeDefinition): boolean {
  if (scope.mode === "selected_documents") {
    return scope.selected_doc_ids.includes(item.doc_id);
  }
  if (scope.mode !== "filtered_subset") {
    return true;
  }
  if (scope.source_values.length && !scope.source_values.includes(item.source ?? "")) {
    return false;
  }
  if (scope.institution_values.length && !scope.institution_values.includes(item.institution ?? "")) {
    return false;
  }
  if (scope.category_values.length && !scope.category_values.includes(item.category_or_tag ?? "")) {
    return false;
  }
  if (scope.year_from && (!item.year || item.year < scope.year_from)) {
    return false;
  }
  if (scope.year_to && (!item.year || item.year > scope.year_to)) {
    return false;
  }
  return true;
}

function enabledDictionaryEntryCount(dictionarySet: ProjectManifest["dictionary_set"]): number {
  return Object.values(dictionarySet.sheets).reduce(
    (count, sheet) => count + sheet.entries.filter((entry) => entry.enabled).length,
    0
  );
}

function uniqueSorted(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value))))
    .sort((left, right) => left.localeCompare(right, "zh-CN"));
}
