import type { ReactNode } from "react";
import { Toolbar, ToolbarButton, Tooltip } from "@fluentui/react-components";
import {
  ArrowUploadRegular,
  DesktopFlowRegular,
  SaveRegular,
  TableRegular
} from "@fluentui/react-icons";
import type { CorpusItem, ProjectManifest } from "@textflow/shared-types";
import { buildCorpusCommands, type CorpusCommandId } from "./corpusCommands";

export function CorpusWorkspace({
  project,
  corpus,
  loading,
  canSaveImportSpec,
  canCreateView,
  onImportFiles,
  onSaveImportSpec,
  onCreateCorpusView,
  onSendToWorkflow,
  showToolbar = false,
  children
}: {
  project: ProjectManifest;
  corpus: CorpusItem[];
  loading: boolean;
  canSaveImportSpec: boolean;
  canCreateView: boolean;
  onImportFiles: () => void | Promise<void>;
  onSaveImportSpec: () => void | Promise<void>;
  onCreateCorpusView: () => void | Promise<void>;
  onSendToWorkflow: () => void;
  showToolbar?: boolean;
  children: ReactNode;
}) {
  const commands = showToolbar
    ? buildCorpusCommands({
        loading,
        canSaveImportSpec,
        canCreateView,
        hasCorpus: corpus.length > 0
      })
    : [];
  const sourceProfiles = new Set(corpus.map((item) => item.source_profile));
  const readyDocuments = corpus.filter((item) => item.status === "ready").length;
  const sourceFileCount = project.source_files?.length ?? 0;

  const runCommand = (id: CorpusCommandId) => {
    switch (id) {
      case "import_files":
        return onImportFiles();
      case "save_ingestion_spec":
        return onSaveImportSpec();
      case "create_view":
        return onCreateCorpusView();
      case "send_to_workflow":
        return onSendToWorkflow();
      default:
        return undefined;
    }
  };

  return (
    <div className="corpus-workspace">
      {showToolbar && (
        <section className="corpus-workspace-toolbar" aria-label="语料命令栏">
          <Toolbar>
            {commands.map((command) => (
              <Tooltip key={command.id} content={command.label} relationship="label">
                <ToolbarButton
                  icon={commandIcon(command.id)}
                  appearance={command.id === "send_to_workflow" ? "primary" : "subtle"}
                  disabled={command.disabled}
                  onClick={() => void runCommand(command.id)}
                >
                  {command.label}
                </ToolbarButton>
              </Tooltip>
            ))}
          </Toolbar>
        </section>
      )}

      <section className="corpus-workspace-summary" aria-label="语料对象摘要">
        <article>
          <span>文档</span>
          <strong>{corpus.length}</strong>
        </article>
        <article>
          <span>可运行</span>
          <strong>{readyDocuments}</strong>
        </article>
        <article>
          <span>资料类型</span>
          <strong>{sourceProfiles.size || 0}</strong>
        </article>
        <article>
          <span>导入批次</span>
          <strong>{sourceFileCount}</strong>
        </article>
      </section>

      {children}
    </div>
  );
}

function commandIcon(id: CorpusCommandId) {
  switch (id) {
    case "import_files":
      return <ArrowUploadRegular />;
    case "save_ingestion_spec":
      return <SaveRegular />;
    case "create_view":
      return <TableRegular />;
    case "send_to_workflow":
      return <DesktopFlowRegular />;
    default:
      return <TableRegular />;
  }
}
