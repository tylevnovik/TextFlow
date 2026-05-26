import type {
  RegisteredWorkflowNodeDefinition,
  WorkflowDefinition,
  WorkflowNodeInstance,
  WorkflowNodeType
} from "@textflow/shared-types";
import { workflowNodeDefinition } from "../../workflow";

export interface WorkflowExplorerNode {
  id: string;
  kind: "workflow" | "node" | "library";
  label: string;
  detail: string;
  badge?: string;
  nodeId?: string;
  nodeType?: WorkflowNodeType;
}

const categoryLabels: Record<RegisteredWorkflowNodeDefinition["category"], string> = {
  input: "输入",
  process: "处理",
  analysis: "分析",
  output: "输出",
  utility: "辅助"
};

export function buildWorkflowExplorerNodes(
  workflow: WorkflowDefinition | null | undefined,
  nodeDefinitions: RegisteredWorkflowNodeDefinition[] = []
): WorkflowExplorerNode[] {
  if (!workflow) {
    return [
      {
        id: "workflow-empty",
        kind: "workflow",
        label: "默认节点图",
        detail: "等待项目加载"
      }
    ];
  }

  const visibleDefinitions = nodeDefinitions.filter((definition) => !definition.hidden_from_toolbox);
  const libraryNodes = visibleDefinitions.slice(0, 12).map((definition) => ({
    id: `library-${definition.type}`,
    kind: "library" as const,
    label: definition.title,
    detail: `${categoryLabels[definition.category]} · ${definition.description || "可添加到画布"}`,
    badge: "节点库",
    nodeType: definition.type
  }));

  return [
    {
      id: workflow.workflow_id,
      kind: "workflow",
      label: workflow.name,
      detail: `${workflow.nodes.length} 个节点 · ${workflow.edges.length} 条连线`,
      badge: workflow.source === "system_default" ? "默认" : "项目"
    },
    ...workflow.nodes.map((node) => workflowNodeToExplorerNode(node)),
    ...libraryNodes
  ];
}

export function WorkflowExplorer({
  nodes,
  selectedId,
  onSelectNode
}: {
  nodes: WorkflowExplorerNode[];
  selectedId?: string;
  onSelectNode?: (node: WorkflowExplorerNode) => void;
}) {
  return (
    <nav className="workflow-explorer" aria-label="节点图对象">
      {nodes.map((node) => (
        <button
          key={`${node.kind}-${node.id}`}
          type="button"
          className={`workflow-explorer-node node-${node.kind} ${selectedId === node.id ? "is-active" : ""}`}
          onClick={() => onSelectNode?.(node)}
        >
          <span>
            <strong>{node.label}</strong>
            <small>{node.detail}</small>
          </span>
          {node.badge && <em>{node.badge}</em>}
        </button>
      ))}
    </nav>
  );
}

function workflowNodeToExplorerNode(node: WorkflowNodeInstance): WorkflowExplorerNode {
  const definition = workflowNodeDefinition(node.node_type);

  return {
    id: node.node_id,
    kind: "node",
    label: node.label,
    detail: `${categoryLabels[definition.category]} · ${node.inputs.length} 入 / ${node.outputs.length} 出`,
    badge: node.ui_state.bypassed ? "跳过" : undefined,
    nodeId: node.node_id,
    nodeType: node.node_type
  };
}
