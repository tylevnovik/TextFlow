export type LexiconCommandId =
  | "import_table"
  | "export_table"
  | "add_table"
  | "duplicate_table"
  | "bind_to_workflow";

export interface LexiconCommand {
  id: LexiconCommandId;
  label: string;
  disabled?: boolean;
}

export interface LexiconCommandState {
  loading: boolean;
  hasCurrentTable: boolean;
  canDuplicateTable: boolean;
}

export function buildLexiconCommands(state: LexiconCommandState): LexiconCommand[] {
  return [
    {
      id: "import_table",
      label: "导入词表",
      disabled: state.loading
    },
    {
      id: "export_table",
      label: "导出词表",
      disabled: state.loading || !state.hasCurrentTable
    },
    {
      id: "add_table",
      label: "新增资源表",
      disabled: state.loading
    },
    {
      id: "duplicate_table",
      label: "复制内置表",
      disabled: state.loading || !state.canDuplicateTable
    },
    {
      id: "bind_to_workflow",
      label: "绑定到节点",
      disabled: state.loading || !state.hasCurrentTable
    }
  ];
}
