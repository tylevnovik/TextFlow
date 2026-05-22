import { useEffect, useMemo, useReducer, useRef, type PointerEvent as ReactPointerEvent, type ReactElement } from "react";
import type { ArtifactRecord, ExportFormat, PageId, RunRecord, WorkflowDefinition, WorkspaceSnapshot } from "@textflow/shared-types";
import {
  Badge,
  Button,
  Divider,
  Toolbar,
  ToolbarButton,
  Tree,
  TreeItem,
  TreeItemLayout
} from "@fluentui/react-components";
import {
  ArrowDownloadRegular,
  ArrowUploadRegular,
  BookRegular,
  DatabaseRegular,
  DesktopFlowRegular,
  DocumentRegular,
  FolderRegular,
  HistoryRegular,
  PanelBottomRegular,
  PanelLeftRegular,
  PanelRightRegular,
  PlayRegular,
  SaveRegular,
  SettingsRegular,
  TableRegular
} from "@fluentui/react-icons";
import { PageView, pageMeta } from "../screens";
import { CorpusInspector } from "../features/corpus/CorpusInspector";
import { LexiconInspector } from "../features/lexicon/LexiconInspector";
import { RunInspector } from "../features/runs/RunInspector";
import { RunStatusPane, type RunProgressInfo } from "../features/runs/RunStatusPane";
import { WorkflowInspector } from "../features/workflow/WorkflowInspector";
import {
  WORKFLOW_NODE_TYPE_MIME,
  WORKFLOW_WORKBENCH_ACTION_EVENT,
  type WorkflowWorkbenchAction
} from "../features/workflow/workflowWorkbenchActions";
import {
  buildWorkbenchNavigation,
  workflowQuickActions,
  type WorkbenchNavigationGroup,
  type WorkbenchNavigationItem
} from "./workbenchNavigation";
import {
  selectionFromPage,
  selectionKey,
  selectionToPage,
  serializeWorkbenchSelection,
  workbenchSelectionReducer,
  WORKBENCH_SELECTION_MIME,
  type WorkbenchSelection
} from "./workbenchSelection";
import {
  initialWorkbenchLayoutState,
  workbenchLayoutReducer
} from "./workbenchLayoutState";

export type WorkbenchProgressInfo = RunProgressInfo;

interface ProjectWorkbenchProps {
  activePage: PageId;
  snapshot: WorkspaceSnapshot;
  loading: boolean;
  statusLine: string;
  progress: WorkbenchProgressInfo;
  setActivePage: (page: PageId) => void;
  onRunWorkflow: () => void | Promise<void>;
  onExportArtifacts: (formats?: ExportFormat[]) => void | Promise<void>;
}

export function ProjectWorkbench({
  activePage,
  snapshot,
  loading,
  statusLine,
  progress,
  setActivePage,
  onRunWorkflow,
  onExportArtifacts
}: ProjectWorkbenchProps) {
  const project = snapshot.current_project;
  const navigation = useMemo(() => buildWorkbenchNavigation(snapshot), [snapshot]);
  const [layoutState, dispatchLayout] = useReducer(workbenchLayoutReducer, initialWorkbenchLayoutState);
  const [selection, dispatchSelection] = useReducer(
    workbenchSelectionReducer,
    selectionFromPage(activePage, project?.id)
  );
  const pendingSelectionKeyRef = useRef<string | null>(null);
  const currentPageMeta = pageMeta[activePage];
  const canActOnWorkflow = Boolean(project) && !loading;
  const showCorpusCommand = Boolean(project) && !loading && (activePage === "home" || activePage === "project" || activePage === "data");
  const showWorkflowCommands = Boolean(project) && activePage === "workflow";
  const showExportCommand = Boolean(project) && !loading && (activePage === "results" || activePage === "report");
  const showSurfaceHeader = activePage !== "workflow";
  const canShowBottomPane = activePage === "workflow" || activePage === "results" || activePage === "report";
  const showBottomPane = canShowBottomPane && !layoutState.bottomPaneCollapsed;
  const collapseBottomPane = !canShowBottomPane || layoutState.bottomPaneCollapsed;
  const surfaceStatus = surfaceStatusLine(statusLine, project?.name);

  useEffect(() => {
    const pendingSelectionKey = pendingSelectionKeyRef.current;
    if (pendingSelectionKey === selectionKey(selection)) {
      if (selectionToPage(selection) === activePage) {
        pendingSelectionKeyRef.current = null;
      }
      return;
    }

    const defaultSelection = selectionFromPage(activePage, project?.id);
    if (
      selection.projectId !== defaultSelection.projectId
      || (selectionToPage(selection) !== activePage && selectionKey(selection) !== selectionKey(defaultSelection))
    ) {
      dispatchSelection({ type: "select", selection: defaultSelection });
    }
  }, [activePage, project?.id, selection]);

  const selectWorkbenchSelection = (nextSelection: WorkbenchSelection, page = selectionToPage(nextSelection)) => {
    pendingSelectionKeyRef.current = selectionKey(nextSelection);
    dispatchSelection({ type: "select", selection: nextSelection });
    setActivePage(page);
  };

  const selectWorkbenchItem = (item: WorkbenchNavigationItem) => {
    selectWorkbenchSelection(item.selection, item.page);
    dispatchWorkflowWorkbenchActionFromItem(item);
  };

  const selectedKey = selectionKey(selection);
  const activeWorkflow = project?.workflow_definitions.find((workflow) => workflow.workflow_id === project.active_workflow_id)
    ?? project?.workflow_definitions[0];
  const selectWorkflowEntry = () => {
    selectWorkbenchSelection({
      kind: "workflow",
      projectId: project?.id ?? "no-project",
      workflowId: activeWorkflow?.workflow_id ?? "active-workflow"
    });
  };
  const selectRun = (run: RunRecord) => {
    selectWorkbenchSelection({
      kind: "run",
      projectId: project?.id ?? run.project_id,
      runId: run.run_id
    }, "results");
  };
  const selectArtifact = (artifact: ArtifactRecord) => {
    selectWorkbenchSelection({
      kind: "artifact",
      projectId: project?.id ?? "no-project",
      artifactId: artifact.artifact_id
    }, "results");
  };
  const exportFormats = (formats: ExportFormat[]) => onExportArtifacts(formats);
  const beginResize = (pane: "object" | "inspector" | "bottom", event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    const startX = event.clientX;
    const startY = event.clientY;
    const startWidth = pane === "object" ? layoutState.objectPaneWidth : layoutState.inspectorWidth;
    const startHeight = layoutState.bottomPaneHeight;
    const target = event.currentTarget;
    target.setPointerCapture(event.pointerId);

    const handleMove = (moveEvent: PointerEvent) => {
      if (pane === "object") {
        dispatchLayout({ type: "setObjectPaneWidth", width: clamp(startWidth + moveEvent.clientX - startX, 240, 420) });
        return;
      }

      if (pane === "inspector") {
        dispatchLayout({ type: "setInspectorWidth", width: clamp(startWidth - (moveEvent.clientX - startX), 280, 460) });
        return;
      }

      dispatchLayout({ type: "setBottomPaneHeight", height: clamp(startHeight - (moveEvent.clientY - startY), 160, 420) });
    };

    const handleEnd = () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleEnd);
      window.removeEventListener("pointercancel", handleEnd);
    };

    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleEnd);
    window.addEventListener("pointercancel", handleEnd);
  };

  return (
    <div
      className={[
        "textflow-workbench-shell",
        layoutState.objectPaneCollapsed ? "is-object-pane-collapsed" : "",
        layoutState.inspectorCollapsed ? "is-inspector-collapsed" : "",
        collapseBottomPane ? "is-bottom-pane-collapsed" : ""
      ].join(" ")}
      style={{
        ["--object-pane-width" as string]: `${layoutState.objectPaneWidth}px`,
        ["--inspector-width" as string]: `${layoutState.inspectorWidth}px`,
        ["--bottom-pane-height" as string]: `${layoutState.bottomPaneHeight}px`
      }}
    >
      <header className="workbench-titlebar">
        <div className="workbench-brand">
          <div className="workbench-brand-mark" aria-hidden="true">TF</div>
          <div>
            <p className="workbench-kicker">TextFlow Studio</p>
            <h1>{project?.name ?? "本地文本项目工作台"}</h1>
          </div>
        </div>

        <Toolbar aria-label="当前对象命令栏" className="workbench-commandbar">
          <CommandButton label="项目管理" icon={<FolderRegular />} onClick={() => setActivePage("home")} />
          {showCorpusCommand && (
            <CommandButton label="导入语料" icon={<ArrowUploadRegular />} onClick={() => setActivePage("data")} disabled={loading} />
          )}
          {showWorkflowCommands && (
            <>
              <CommandButton
                label="保存图"
                icon={<SaveRegular />}
                onClick={() => window.dispatchEvent(new CustomEvent("textflow:workflow-save"))}
                disabled={!canActOnWorkflow}
              />
              <CommandButton
                label="运行节点图"
                icon={<PlayRegular />}
                onClick={() => window.dispatchEvent(new CustomEvent("textflow:workflow-run"))}
                disabled={!canActOnWorkflow}
                primary
              />
            </>
          )}
          {project && activePage !== "workflow" && (
            <CommandButton label="打开节点图" icon={<DesktopFlowRegular />} onClick={selectWorkflowEntry} disabled={loading} />
          )}
          {showExportCommand && (
            <CommandButton label="导出产物" icon={<ArrowDownloadRegular />} onClick={() => void onExportArtifacts(["csv", "xlsx", "html", "png"])} disabled={loading} />
          )}
        </Toolbar>

        <div className="workbench-window-tools">
          <Button
            appearance="subtle"
            aria-label={layoutState.objectPaneCollapsed ? "展开项目对象区" : "折叠项目对象区"}
            title={layoutState.objectPaneCollapsed ? "展开项目对象区" : "折叠项目对象区"}
            icon={<PanelLeftRegular />}
            onClick={() => dispatchLayout({ type: "toggleObjectPane" })}
          />
          <Button
            appearance="subtle"
            aria-label={layoutState.inspectorCollapsed ? "展开属性检查器" : "折叠属性检查器"}
            title={layoutState.inspectorCollapsed ? "展开属性检查器" : "折叠属性检查器"}
            icon={<PanelRightRegular />}
            onClick={() => dispatchLayout({ type: "toggleInspector" })}
          />
          {canShowBottomPane && (
            <Button
              appearance="subtle"
              aria-label={layoutState.bottomPaneCollapsed ? "展开底部面板" : "折叠底部面板"}
              title={layoutState.bottomPaneCollapsed ? "展开底部面板" : "折叠底部面板"}
              icon={<PanelBottomRegular />}
              onClick={() => dispatchLayout({ type: "toggleBottomPane" })}
            />
          )}
        </div>
      </header>

      {!layoutState.objectPaneCollapsed && (
        <aside className="workbench-object-pane">
          <div
            className="workbench-pane-resize-handle is-right"
            role="separator"
            aria-label="调整项目对象区宽度"
            aria-orientation="vertical"
            onPointerDown={(event) => beginResize("object", event)}
          />
          <div className="workbench-pane-header">
            <div>
              <p className="workbench-kicker">项目对象</p>
              <strong>语料 · 词库 · 节点图</strong>
            </div>
            <Button
              appearance="subtle"
              size="small"
              aria-label="折叠项目对象区"
              title="折叠项目对象区"
              icon={<PanelLeftRegular />}
              onClick={() => dispatchLayout({ type: "toggleObjectPane" })}
            />
          </div>
          <ObjectSwitcher
            groups={navigation}
            activePage={activePage}
            onSelectItem={selectWorkbenchItem}
          />
          <ObjectTree
            groups={navigation}
            selectedKey={selectedKey}
            onSelectItem={selectWorkbenchItem}
            activePage={activePage}
          />
          {activePage === "workflow" && activeWorkflow && (
            <WorkflowActionStrip
              projectId={project?.id ?? "no-project"}
              workflowId={activeWorkflow.workflow_id}
              onAction={(item) => {
                dispatchWorkflowWorkbenchActionFromItem(item);
                dispatchSelection({ type: "select", selection: item.selection });
              }}
            />
          )}
        </aside>
      )}

      <main className="workbench-main">
        {showSurfaceHeader && (
          <section className="workbench-surface-header">
            <div>
              <p className="workbench-kicker">{currentPageMeta.surfaceLabel}</p>
              <h2>{currentPageMeta.headline}</h2>
              {surfaceStatus && <p>{surfaceStatus}</p>}
            </div>
          </section>
        )}

        <section className={`workbench-surface-content content-grid page-${activePage} ${activePage === "workflow" ? "is-workflow-page" : ""}`}>
          <PageView
            page={activePage}
            workbenchSelection={selection}
            onWorkbenchSelect={selectWorkbenchSelection}
          />
        </section>
      </main>

      {!layoutState.inspectorCollapsed && (
        <aside className="workbench-inspector" aria-label="属性检查器">
          <div
            className="workbench-pane-resize-handle is-left"
            role="separator"
            aria-label="调整属性检查器宽度"
            aria-orientation="vertical"
            onPointerDown={(event) => beginResize("inspector", event)}
          />
          <div className="workbench-pane-header workbench-inspector-header">
            <div>
              <p className="workbench-kicker">属性检查器</p>
              <strong>当前对象</strong>
            </div>
            <Button
              appearance="subtle"
              size="small"
              aria-label="折叠属性检查器"
              title="折叠属性检查器"
              icon={<PanelRightRegular />}
              onClick={() => dispatchLayout({ type: "toggleInspector" })}
            />
          </div>
          <InspectorHost
            selection={selection}
            snapshot={snapshot}
            loading={loading}
            onSendToWorkflow={selectWorkflowEntry}
            onOpenRun={selectRun}
            onOpenArtifact={selectArtifact}
            onExportFormats={exportFormats}
          />
        </aside>
      )}

      {showBottomPane && (
        <section className="workbench-bottom-pane-host">
          <div
            className="workbench-pane-resize-handle is-top"
            role="separator"
            aria-label="调整底部面板高度"
            aria-orientation="horizontal"
            onPointerDown={(event) => beginResize("bottom", event)}
          />
          <RunStatusPane
            activeTab={layoutState.bottomTab}
            onTabChange={(tab) => dispatchLayout({ type: "setBottomTab", tab })}
            snapshot={snapshot}
            progress={progress}
            onOpenRun={selectRun}
            onOpenArtifact={selectArtifact}
            onCollapse={() => dispatchLayout({ type: "toggleBottomPane" })}
          />
        </section>
      )}
    </div>
  );
}

function dispatchWorkflowWorkbenchActionFromItem(item: WorkbenchNavigationItem) {
  const selection = item.selection;
  let action: WorkflowWorkbenchAction | null = null;

  if (selection.kind === "workflow_action") {
    action = { type: "canvas", action: selection.action };
  }

  if (selection.kind === "workflow_library") {
    action = { type: "add_node", nodeType: selection.nodeType };
  }

  if (!action) {
    return;
  }

  window.requestAnimationFrame(() => {
    window.dispatchEvent(new CustomEvent<WorkflowWorkbenchAction>(WORKFLOW_WORKBENCH_ACTION_EVENT, { detail: action }));
  });
}

function CommandButton({
  label,
  icon,
  disabled,
  primary,
  onClick
}: {
  label: string;
  icon: ReactElement;
  disabled?: boolean;
  primary?: boolean;
  onClick?: () => void;
}) {
  return (
    <ToolbarButton
      icon={icon}
      appearance={primary ? "primary" : "subtle"}
      disabled={disabled}
      title={label}
      onClick={onClick}
    >
      {label}
    </ToolbarButton>
  );
}

function ObjectTree({
  groups,
  selectedKey,
  onSelectItem,
  activePage
}: {
  groups: WorkbenchNavigationGroup[];
  selectedKey: string;
  onSelectItem: (item: WorkbenchNavigationItem) => void;
  activePage: PageId;
}) {
  const openItems = useMemo(() => {
    const pageGroupId = groupIdForPage(activePage);
    const nextOpenItems = groups.filter((group) => group.id === "project" || group.id === pageGroupId).map((group) => group.id);
    if (pageGroupId === "workflow") {
      nextOpenItems.push("workflow-toolbox");
    }
    return nextOpenItems;
  }, [activePage, groups]);

  return (
    <Tree
      aria-label="项目对象树"
      className="workbench-tree"
      defaultOpenItems={openItems}
      key={openItems.join(":")}
      onOpenChange={(_, data) => {
        const group = groups.find((item) => item.id === String(data.value));
        const groupEntry = group?.items[0];
        if (groupEntry) {
          onSelectItem(groupEntry);
        }
      }}
    >
      {groups.map((group) => {
        const isGroupActive = group.id === groupIdForPage(activePage);

        return (
        <TreeItem
          itemType="branch"
          value={group.id}
          key={group.id}
          className={isGroupActive ? "is-active" : undefined}
        >
          <TreeItemLayout
            iconBefore={groupIcon(group.id)}
            aside={<span className="workbench-tree-summary">{group.summary}</span>}
          >
            {group.label}
          </TreeItemLayout>
          <Tree className="workbench-tree-children" defaultOpenItems={openItems}>
            <ObjectTreeItems
              items={group.items}
              selectedKey={selectedKey}
              onSelectItem={onSelectItem}
              openItems={openItems}
            />
          </Tree>
        </TreeItem>
        );
      })}
    </Tree>
  );
}

function ObjectTreeItems({
  items,
  selectedKey,
  onSelectItem,
  openItems
}: {
  items: WorkbenchNavigationItem[];
  selectedKey: string;
  onSelectItem: (item: WorkbenchNavigationItem) => void;
  openItems: string[];
}) {
  return (
    <>
      {items.map((item) => {
        const hasChildren = Boolean(item.children?.length);
        const isActive = selectionKey(item.selection) === selectedKey;
        const draggable = isDraggableWorkbenchItem(item);

        return (
          <TreeItem
            itemType={hasChildren ? "branch" : "leaf"}
            value={item.id}
            key={item.id}
            className={`${isActive ? "is-active" : ""} ${hasChildren ? "is-drawer" : ""}`.trim() || undefined}
            onClick={hasChildren ? undefined : (event) => {
              event.stopPropagation();
              onSelectItem(item);
            }}
            draggable={draggable}
            onDragStart={(event) => {
              if (!draggable) {
                return;
              }
              event.dataTransfer.effectAllowed = "copy";
              if (item.selection.kind === "workflow_library") {
                event.dataTransfer.setData(WORKFLOW_NODE_TYPE_MIME, item.selection.nodeType);
              } else {
                event.dataTransfer.setData(WORKBENCH_SELECTION_MIME, serializeWorkbenchSelection(item.selection));
              }
              event.dataTransfer.setData("text/plain", item.label);
            }}
          >
            <TreeItemLayout
              iconBefore={itemIcon(item)}
              aside={item.badge ? <Badge size="small">{item.badge}</Badge> : undefined}
            >
              <span className="workbench-tree-main">
                <strong>{item.label}</strong>
                <small>{item.detail}</small>
              </span>
            </TreeItemLayout>
            {hasChildren && (
              <Tree className="workbench-tree-children workbench-tree-drawer-items" defaultOpenItems={openItems}>
                <ObjectTreeItems
                  items={item.children ?? []}
                  selectedKey={selectedKey}
                  onSelectItem={onSelectItem}
                  openItems={openItems}
                />
              </Tree>
            )}
          </TreeItem>
        );
      })}
    </>
  );
}

function ObjectSwitcher({
  groups,
  activePage,
  onSelectItem
}: {
  groups: WorkbenchNavigationGroup[];
  activePage: PageId;
  onSelectItem: (item: WorkbenchNavigationItem) => void;
}) {
  const activeGroupId = groupIdForPage(activePage);
  const selectGroup = (groupId: string) => {
    const entry = groups.find((group) => group.id === groupId)?.items[0];
    if (entry) {
      onSelectItem(entry);
    }
  };

  return (
    <nav
      className="workbench-object-switcher"
      aria-label="主对象导航"
      onPointerDownCapture={(event) => {
        const target = event.target as HTMLElement;
        const trigger = target.closest<HTMLElement>("[data-workbench-group]");
        if (!trigger) {
          return;
        }
        selectGroup(trigger.dataset.workbenchGroup ?? "");
      }}
    >
      {groups.map((group) => {
        const entry = group.items[0];
        const isActive = group.id === activeGroupId;
        return (
          <Button
            key={group.id}
            data-workbench-group={group.id}
            appearance={isActive ? "primary" : "subtle"}
            size="small"
            icon={groupIcon(group.id)}
            disabled={!entry}
            onClick={() => selectGroup(group.id)}
          >
            {group.label}
          </Button>
        );
      })}
    </nav>
  );
}

function WorkflowActionStrip({
  projectId,
  workflowId,
  onAction
}: {
  projectId: string;
  workflowId: string;
  onAction: (item: WorkbenchNavigationItem) => void;
}) {
  return (
    <section className="workbench-workflow-actions" aria-label="节点图动作">
      <div className="workbench-workflow-actions-head">
        <p className="workbench-kicker">节点图动作</p>
        <span>画布</span>
      </div>
      <div className="workbench-workflow-action-grid">
        {workflowQuickActions().map((action) => {
          const item: WorkbenchNavigationItem = {
            id: `workflow-action-${action.id}`,
            label: action.label,
            detail: action.detail,
            page: "workflow",
            selection: { kind: "workflow_action", projectId, workflowId, action: action.id }
          };

          return (
            <Button
              key={action.id}
              appearance={action.tone === "danger" ? "subtle" : "secondary"}
              size="small"
              className={action.tone === "danger" ? "is-danger" : undefined}
              title={action.detail}
              onClick={() => onAction(item)}
            >
              {action.label}
            </Button>
          );
        })}
      </div>
    </section>
  );
}

function groupIdForPage(page: PageId): string {
  switch (page) {
    case "data":
      return "corpus";
    case "dictionaries":
      return "lexicon";
    case "workflow":
      return "workflow";
    case "results":
    case "report":
      return "runs";
    case "settings":
      return "system";
    default:
      return "project";
  }
}

function surfaceStatusLine(statusLine: string, projectName?: string): string | null {
  if (!statusLine.trim()) {
    return null;
  }

  if (projectName && statusLine.includes(`当前项目：${projectName}`)) {
    return null;
  }

  return statusLine;
}

function isDraggableWorkbenchItem(item: WorkbenchNavigationItem) {
  return item.selection.kind === "corpus_collection"
    || item.selection.kind === "lexicon_table"
    || item.selection.kind === "workflow_library";
}

function groupIcon(groupId: string) {
  switch (groupId) {
    case "corpus":
      return <DocumentRegular />;
    case "lexicon":
      return <BookRegular />;
    case "workflow":
      return <DesktopFlowRegular />;
    case "runs":
      return <HistoryRegular />;
    case "system":
      return <SettingsRegular />;
    default:
      return <FolderRegular />;
  }
}

function itemIcon(item: WorkbenchNavigationItem) {
  switch (item.selection.kind) {
    case "corpus_collection":
      return <DatabaseRegular />;
    case "ingestion_spec":
      return <TableRegular />;
    case "lexicon_kind":
    case "lexicon_table":
      return <BookRegular />;
    case "workflow":
    case "workflow_toolbox":
    case "workflow_action":
    case "workflow_library":
    case "workflow_node":
    case "workflow_edge":
      return <DesktopFlowRegular />;
    case "run":
      return <HistoryRegular />;
    case "artifact":
      return <DocumentRegular />;
    default:
      return <FolderRegular />;
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function InspectorHost({
  selection,
  snapshot,
  loading,
  onSendToWorkflow,
  onOpenRun,
  onOpenArtifact,
  onExportFormats
}: {
  selection: WorkbenchSelection;
  snapshot: WorkspaceSnapshot;
  loading: boolean;
  onSendToWorkflow: () => void;
  onOpenRun: (run: RunRecord) => void;
  onOpenArtifact: (artifact: ArtifactRecord) => void;
  onExportFormats: (formats: ExportFormat[]) => void | Promise<void>;
}) {
  const project = snapshot.current_project;

  if (!project) {
    return (
      <InspectorSection
        eyebrow="属性检查器"
        title="尚未打开项目"
        rows={[
          ["状态", "等待创建或打开项目"],
          ["对象模型", "语料 / 词库 / 节点图"]
        ]}
      />
    );
  }

  switch (selection.kind) {
    case "project":
      return (
        <InspectorSection
          eyebrow="项目"
          title={project.name}
          rows={[
            ["语料", `${snapshot.corpus.length} 篇文档`],
            ["词库", `${Object.keys(project.dictionary_set.collections).length} 类`],
            ["节点图", `${project.workflow_definitions.length} 张`],
            ["运行记录", `${project.run_history.length} 次`]
          ]}
        />
      );
    case "corpus_collection":
    case "corpus_document":
    case "ingestion_spec":
      return (
        <CorpusInspector
          selection={selection}
          project={project}
          corpus={snapshot.corpus}
          onSendToWorkflow={onSendToWorkflow}
        />
      );
    case "lexicon_kind":
    case "lexicon_table":
    case "lexicon_entry":
      return (
        <LexiconInspector
          selection={selection}
          project={project}
          onBindToWorkflow={onSendToWorkflow}
        />
      );
    case "workflow":
    case "workflow_toolbox":
    case "workflow_action":
    case "workflow_library":
    case "workflow_node":
    case "workflow_edge": {
      const persistedWorkflow = project.workflow_definitions.find((item) => item.workflow_id === selection.workflowId)
        ?? project.workflow_definitions.find((item) => item.workflow_id === project.active_workflow_id)
        ?? project.workflow_definitions[0];
      const workflow = workflowForSelection(persistedWorkflow, selection);
      const inspectorSelection: WorkbenchSelection = selection.kind === "workflow_action" || selection.kind === "workflow_library" || selection.kind === "workflow_toolbox"
        ? { kind: "workflow", projectId: selection.projectId, workflowId: selection.workflowId }
        : selection;
      return (
        <WorkflowInspector
          selection={inspectorSelection}
          project={project}
          workflow={workflow}
        />
      );
    }
    case "run":
    case "artifact": {
      return (
        <RunInspector
          selection={selection}
          project={project}
          loading={loading}
          onOpenRun={onOpenRun}
          onOpenArtifact={onOpenArtifact}
          onExportFormats={onExportFormats}
        />
      );
    }
    default:
      return (
        <InspectorSection
          eyebrow="属性检查器"
          title="对象已选中"
          rows={[
            ["类型", "未知对象"],
            ["项目", project.name]
          ]}
        />
      );
  }
}

function workflowForSelection(
  workflow: WorkflowDefinition | undefined,
  selection: WorkbenchSelection
): WorkflowDefinition | undefined {
  if (!workflow) {
    return workflow;
  }

  if (selection.kind === "workflow_node" && !workflow.nodes.some((node) => node.node_id === selection.nodeId)) {
    if (selection.node) {
      return {
        ...workflow,
        nodes: [...workflow.nodes, selection.node]
      };
    }

    const matchingNode = selection.nodeType
      ? workflow.nodes.find((node) => node.node_type === selection.nodeType)
      : null;
    if (matchingNode) {
      return {
        ...workflow,
        nodes: workflow.nodes.map((node) =>
          node.node_id === matchingNode.node_id
            ? { ...node, node_id: selection.nodeId }
            : node
        )
      };
    }
  }

  if (selection.kind === "workflow_edge" && selection.edge && !workflow.edges.some((edge) => edge.edge_id === selection.edgeId)) {
    return {
      ...workflow,
      edges: [...workflow.edges, selection.edge]
    };
  }

  return workflow;
}

function InspectorSection({ eyebrow, title, rows }: { eyebrow: string; title: string; rows: Array<[string, string]> }) {
  return (
    <div className="workbench-inspector-card">
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
    </div>
  );
}
