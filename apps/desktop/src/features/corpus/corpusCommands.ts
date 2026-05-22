export type CorpusCommandId = "import_files" | "save_ingestion_spec" | "create_view" | "send_to_workflow";

export interface CorpusCommand {
  id: CorpusCommandId;
  label: string;
  disabled?: boolean;
}

export interface CorpusCommandState {
  loading: boolean;
  canSaveImportSpec: boolean;
  canCreateView: boolean;
  hasCorpus: boolean;
}

export function buildCorpusCommands(state: CorpusCommandState): CorpusCommand[] {
  return [
    {
      id: "import_files",
      label: "导入文件",
      disabled: state.loading
    },
    {
      id: "save_ingestion_spec",
      label: "保存导入规范",
      disabled: state.loading || !state.canSaveImportSpec
    },
    {
      id: "create_view",
      label: "创建语料视图",
      disabled: state.loading || !state.canCreateView
    },
    {
      id: "send_to_workflow",
      label: "发送到节点图",
      disabled: state.loading || !state.hasCorpus
    }
  ];
}
