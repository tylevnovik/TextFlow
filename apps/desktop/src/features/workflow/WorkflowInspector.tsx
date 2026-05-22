import type { ReactNode } from "react";
import { Button, Divider } from "@fluentui/react-components";
import type {
  ArtifactRecord,
  ProjectManifest,
  WorkflowDefinition,
  WorkflowEdge,
  WorkflowNodeInstance,
  WorkflowNodeRuntimeState
} from "@textflow/shared-types";
import type { WorkbenchSelection } from "../../app/workbenchSelection";
import { buildRunCommands } from "../runs/runCommands";
import { workflowNodeDefinition } from "../../workflow";

type WorkflowInspectorSelection = Extract<
  WorkbenchSelection,
  { kind: "workflow" | "workflow_toolbox" | "workflow_node" | "workflow_edge" }
>;

export function WorkflowInspector({
  selection,
  project,
  workflow,
  runtimeStates
}: {
  selection: WorkflowInspectorSelection;
  project: ProjectManifest;
  workflow: WorkflowDefinition | null | undefined;
  runtimeStates?: Record<string, WorkflowNodeRuntimeState>;
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
        node={node}
        project={project}
        runtime={node ? runtimeStates?.[node.node_id] : undefined}
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
  runtime
}: {
  node: WorkflowNodeInstance | null;
  project: ProjectManifest;
  runtime?: WorkflowNodeRuntimeState;
}) {
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
      <div className="workflow-inspector-token-strip" aria-label="节点配置键">
        {(configKeys.length ? configKeys : ["default"]).slice(0, 12).map((key) => (
          <span key={key}>{key}</span>
        ))}
      </div>
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
