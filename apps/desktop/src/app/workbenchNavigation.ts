import type {
  PageId,
  RegisteredWorkflowNodeDefinition,
  WorkspaceSnapshot
} from "@textflow/shared-types";
import { buildCorpusExplorerNodes, type CorpusExplorerNode } from "../features/corpus/CorpusExplorer";
import {
  buildLexiconExplorerNodes,
  lexiconKindLabels,
  lexiconKindOrder,
  type LexiconExplorerNode
} from "../features/lexicon/LexiconExplorer";
import type { WorkflowWorkbenchCanvasAction } from "../features/workflow/workflowWorkbenchActions";
import { workflowToolboxDefinitions } from "../workflowNodeCatalog";
import type { WorkbenchSelection } from "./workbenchSelection";

export interface WorkbenchNavigationItem {
  id: string;
  label: string;
  detail: string;
  badge?: string;
  page: PageId;
  selection: WorkbenchSelection;
  children?: WorkbenchNavigationItem[];
}

export interface WorkbenchNavigationGroup {
  id: string;
  label: string;
  summary: string;
  items: WorkbenchNavigationItem[];
}

export interface WorkflowQuickAction {
  id: WorkflowWorkbenchCanvasAction;
  label: string;
  detail: string;
  tone?: "danger";
}

export const dictionaryKindLabels = lexiconKindLabels;

const workflowNodeCategoryLabels: Record<RegisteredWorkflowNodeDefinition["category"], string> = {
  input: "输入",
  process: "处理",
  analysis: "分析",
  output: "输出",
  utility: "辅助"
};

function enabledEntryCount(snapshot: WorkspaceSnapshot, kind: keyof typeof dictionaryKindLabels): number {
  const collection = snapshot.current_project?.dictionary_set.collections?.[kind];
  if (!collection) {
    return 0;
  }

  return collection.tables.reduce((total, table) => {
    if (!table.enabled) {
      return total;
    }
    return total + table.entries.filter((entry) => entry.enabled).length;
  }, 0);
}

export function buildWorkbenchNavigation(snapshot: WorkspaceSnapshot): WorkbenchNavigationGroup[] {
  const project = snapshot.current_project;
  const projectId = project?.id ?? "no-project";
  const corpusNodes = buildCorpusExplorerNodes(snapshot);
  const lexiconNodes = buildLexiconExplorerNodes(snapshot);
  const activeWorkflow = project?.workflow_definitions.find((workflow) => workflow.workflow_id === project.active_workflow_id)
    ?? project?.workflow_definitions[0];
  const latestRun = project?.run_history[0];
  const workflowId = activeWorkflow?.workflow_id ?? "active-workflow";
  const workflowToolboxItems = workflowLibraryNavigationItems(snapshotWorkflowToolboxDefinitions(snapshot), projectId, workflowId);

  return [
    {
      id: "project",
      label: "项目",
      summary: project ? project.name : "尚未打开项目",
      items: project
        ? [
            {
              id: "project-overview",
              label: "三核心概览",
              detail: `${snapshot.corpus.length} 篇文档 · ${project.workflow_definitions.length} 张图`,
              badge: "核心",
              page: "project",
              selection: { kind: "project", projectId }
            },
            {
              id: "project-management",
              label: "项目管理",
              detail: "打开、创建或导入其它项目",
              page: "home",
              selection: { kind: "project", projectId }
            }
          ]
        : [
            {
              id: "project-overview",
              label: "打开或新建项目",
              detail: "先创建本地项目工作区",
              page: "home",
              selection: { kind: "project", projectId }
            }
          ]
    },
    {
      id: "corpus",
      label: "语料",
      summary: `${snapshot.corpus.length} 篇文档`,
      items: corpusNodes.filter((node) => node.kind !== "source_file").slice(0, 6).map((node) => corpusNodeToNavigationItem(node, projectId))
    },
    {
      id: "lexicon",
      label: "词库",
      summary: project ? `${lexiconKindOrder.length} 类词库` : "等待项目加载",
      items: lexiconNodes.filter((node) => node.kind === "kind").map((node) => lexiconNodeToNavigationItem(node, projectId, snapshot))
    },
    {
      id: "workflow",
      label: "节点图",
      summary: activeWorkflow ? activeWorkflow.name : "等待创建图",
      items: [
        {
          id: "workflow-active",
          label: activeWorkflow?.name ?? "默认节点图",
          detail: activeWorkflow ? "当前节点图" : "创建或打开节点图",
          badge: "默认",
          page: "workflow",
          selection: { kind: "workflow", projectId, workflowId }
        },
        {
          id: "workflow-toolbox",
          label: "节点工具箱",
          detail: workflowToolboxItems.length ? `${workflowToolboxItems.length} 个可拖拽节点` : "等待节点定义",
          badge: "抽屉",
          page: "workflow",
          selection: { kind: "workflow_toolbox", projectId, workflowId },
          children: workflowToolboxItems
        }
      ]
    },
    {
      id: "runs",
      label: "运行",
      summary: latestRun ? latestRun.status : "暂无运行",
      items: [
        {
          id: "workflow-runs",
          label: "最近运行",
          detail: latestRun ? `${latestRun.status} · ${latestRun.started_at}` : "暂无运行记录",
          page: "results",
          selection: { kind: "run", projectId, runId: latestRun?.run_id ?? "latest-run" }
        },
        {
          id: "workflow-artifacts",
          label: "产物列表",
          detail: project ? `${project.artifact_records.length} 个节点产物` : "暂无产物",
          page: "results",
          selection: { kind: "artifact", projectId, artifactId: project?.artifact_records[0]?.artifact_id ?? "latest-artifact" }
        }
      ]
    },
    {
      id: "system",
      label: "系统",
      summary: "本机配置",
      items: [
        {
          id: "settings",
          label: "设置",
          detail: "缩放、主题、路径偏好",
          page: "settings",
          selection: { kind: "project", projectId }
        }
      ]
    }
  ];
}

function snapshotWorkflowToolboxDefinitions(snapshot: WorkspaceSnapshot): RegisteredWorkflowNodeDefinition[] {
  return (snapshot.node_definitions?.length ? snapshot.node_definitions : workflowToolboxDefinitions())
    .filter((definition) => !definition.hidden_from_toolbox);
}

function workflowLibraryNavigationItems(
  nodeDefinitions: RegisteredWorkflowNodeDefinition[],
  projectId: string,
  workflowId: string
): WorkbenchNavigationItem[] {
  return [...nodeDefinitions]
    .sort((left, right) =>
      left.category.localeCompare(right.category)
      || left.title.localeCompare(right.title, "zh-CN")
    )
    .map((definition) => ({
      id: `workflow-library-${definition.type}`,
      label: definition.title,
      detail: `${workflowNodeCategoryLabels[definition.category]} · ${definition.description || "拖入画布创建节点"}`,
      page: "workflow" as const,
      selection: {
        kind: "workflow_library" as const,
        projectId,
        workflowId,
        nodeType: definition.type
      }
    }));
}

export function workflowQuickActions(): WorkflowQuickAction[] {
  return [
    { id: "insert_recommended_starter", label: "生成骨架", detail: "按当前项目重建默认处理链" },
    { id: "restore_recommended_edges", label: "恢复连线", detail: "补回系统推荐连接" },
    { id: "auto_layout", label: "整理布局", detail: "重新排列画布节点" },
    { id: "fit_view", label: "适配视图", detail: "居中当前节点图" },
    { id: "validate_graph", label: "校验", detail: "检查连线与运行问题" },
    { id: "clear_canvas", label: "清空", detail: "仅清空当前画布", tone: "danger" }
  ];
}

function corpusNodeToNavigationItem(node: CorpusExplorerNode, projectId: string): WorkbenchNavigationItem {
  return {
    id: `corpus-${node.kind}-${node.id}`,
    label: node.label,
    detail: node.detail,
    badge: node.badge,
    page: "data",
    selection: corpusNodeSelection(node, projectId)
  };
}

function corpusNodeSelection(node: CorpusExplorerNode, projectId: string): WorkbenchSelection {
  switch (node.kind) {
    case "ingestion_spec":
      return { kind: "ingestion_spec", projectId, specId: node.id };
    case "source_file":
      return { kind: "corpus_collection", projectId, collectionId: `source:${node.id}` };
    case "corpus_view":
      return { kind: "corpus_collection", projectId, collectionId: node.id };
    default:
      return { kind: "corpus_collection", projectId, collectionId: "all-corpus" };
  }
}

function lexiconNodeToNavigationItem(
  node: LexiconExplorerNode,
  projectId: string,
  snapshot: WorkspaceSnapshot
): WorkbenchNavigationItem {
  return {
    id: `lexicon-${node.kind}-${node.dictionaryKind}-${node.id}`,
    label: node.label,
    detail: node.detail,
    badge: node.badge ?? (node.kind === "kind" ? String(enabledEntryCount(snapshot, node.dictionaryKind)) : undefined),
    page: "dictionaries",
    selection: lexiconNodeSelection(node, projectId)
  };
}

function lexiconNodeSelection(node: LexiconExplorerNode, projectId: string): WorkbenchSelection {
  if (node.kind === "table") {
    return {
      kind: "lexicon_table",
      projectId,
      dictionaryKind: node.dictionaryKind,
      tableId: node.id
    };
  }

  return {
    kind: "lexicon_kind",
    projectId,
    dictionaryKind: node.dictionaryKind
  };
}
