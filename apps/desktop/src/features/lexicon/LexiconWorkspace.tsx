import type { ReactNode } from "react";
import { Toolbar, ToolbarButton, Tooltip } from "@fluentui/react-components";
import {
  AddRegular,
  ArrowDownloadRegular,
  ArrowUploadRegular,
  CopyRegular,
  DesktopFlowRegular
} from "@fluentui/react-icons";
import type { DictionaryKind, DictionarySet, DictionaryTableResource } from "@textflow/shared-types";
import { buildLexiconCommands, type LexiconCommandId } from "./lexiconCommands";

export function LexiconWorkspace({
  dictionarySet,
  activeKind,
  currentTable,
  loading,
  onImportTable,
  onExportTable,
  onAddTable,
  onDuplicateTable,
  onBindToWorkflow,
  showToolbar = false,
  children
}: {
  dictionarySet: DictionarySet;
  activeKind: DictionaryKind;
  currentTable: DictionaryTableResource | null;
  loading: boolean;
  onImportTable: () => void | Promise<void>;
  onExportTable: () => void | Promise<void>;
  onAddTable: () => void;
  onDuplicateTable: () => void;
  onBindToWorkflow: () => void;
  showToolbar?: boolean;
  children: ReactNode;
}) {
  const commands = showToolbar
    ? buildLexiconCommands({
        loading,
        hasCurrentTable: Boolean(currentTable),
        canDuplicateTable: Boolean(currentTable)
      })
    : [];

  const runCommand = (id: LexiconCommandId) => {
    switch (id) {
      case "import_table":
        return onImportTable();
      case "export_table":
        return onExportTable();
      case "add_table":
        return onAddTable();
      case "duplicate_table":
        return onDuplicateTable();
      case "bind_to_workflow":
        return onBindToWorkflow();
      default:
        return undefined;
    }
  };

  return (
    <div className="lexicon-workspace">
      {showToolbar && (
        <section className="lexicon-workspace-toolbar" aria-label="词库命令栏">
          <Toolbar>
            {commands.map((command) => (
              <Tooltip key={command.id} content={command.label} relationship="label">
                <ToolbarButton
                  icon={commandIcon(command.id)}
                  appearance={command.id === "bind_to_workflow" ? "primary" : "subtle"}
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

      {children}
    </div>
  );
}

function commandIcon(id: LexiconCommandId) {
  switch (id) {
    case "import_table":
      return <ArrowUploadRegular />;
    case "export_table":
      return <ArrowDownloadRegular />;
    case "add_table":
      return <AddRegular />;
    case "duplicate_table":
      return <CopyRegular />;
    case "bind_to_workflow":
      return <DesktopFlowRegular />;
    default:
      return <DesktopFlowRegular />;
  }
}
