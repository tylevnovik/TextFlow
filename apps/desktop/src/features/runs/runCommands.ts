import type { ExportFormat, RunRecord, ArtifactRecord } from "@textflow/shared-types";

export type RunCommandId =
  | "open_run"
  | "compare_latest"
  | "open_artifact"
  | "export_csv"
  | "export_xlsx"
  | "export_html"
  | "export_png";

export interface RunCommand {
  id: RunCommandId;
  label: string;
  formats?: ExportFormat[];
  disabled?: boolean;
}

export function buildRunCommands({
  loading,
  run,
  artifact,
  canCompare = false
}: {
  loading: boolean;
  run?: RunRecord | null;
  artifact?: ArtifactRecord | null;
  canCompare?: boolean;
}): RunCommand[] {
  return [
    {
      id: "open_run",
      label: "打开运行",
      disabled: loading || !run
    },
    {
      id: "compare_latest",
      label: "比较最近两次",
      disabled: loading || !canCompare
    },
    {
      id: "open_artifact",
      label: "打开产物",
      disabled: loading || !artifact
    },
    {
      id: "export_csv",
      label: "导出 CSV",
      formats: ["csv"],
      disabled: loading
    },
    {
      id: "export_xlsx",
      label: "导出 XLSX",
      formats: ["xlsx"],
      disabled: loading
    },
    {
      id: "export_html",
      label: "导出 HTML",
      formats: ["html"],
      disabled: loading
    },
    {
      id: "export_png",
      label: "导出 PNG",
      formats: ["png"],
      disabled: loading
    }
  ];
}
