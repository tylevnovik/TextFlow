import type { ReactNode } from "react";
import { Button, Divider } from "@fluentui/react-components";
import { DesktopFlowRegular } from "@fluentui/react-icons";
import type { DictionaryEntry, DictionaryTableResource, ProjectManifest } from "@textflow/shared-types";
import type { WorkbenchSelection } from "../../app/workbenchSelection";
import { lexiconKindLabels } from "./LexiconExplorer";

type LexiconInspectorSelection = Extract<
  WorkbenchSelection,
  { kind: "lexicon_kind" | "lexicon_table" | "lexicon_entry" }
>;

export function LexiconInspector({
  selection,
  project,
  onBindToWorkflow
}: {
  selection: LexiconInspectorSelection;
  project: ProjectManifest;
  onBindToWorkflow?: () => void;
}) {
  const collection = project.dictionary_set.collections[selection.dictionaryKind];

  if (selection.kind === "lexicon_entry") {
    const table = collection?.tables.find((item) => item.id === selection.tableId) ?? null;
    const entry = table?.entries.find((item) => item.id === selection.entryId) ?? null;
    return <LexiconEntryInspector table={table} entry={entry} onBindToWorkflow={onBindToWorkflow} />;
  }

  if (selection.kind === "lexicon_table") {
    const table = collection?.tables.find((item) => item.id === selection.tableId) ?? null;
    return <LexiconTableInspector table={table} onBindToWorkflow={onBindToWorkflow} />;
  }

  const tables = collection?.tables ?? [];
  const enabledEntries = tables.reduce((sum, table) => {
    if (!table.enabled) {
      return sum;
    }
    return sum + table.entries.filter((entry) => entry.enabled).length;
  }, 0);

  return (
    <InspectorCard
      eyebrow="词库分类"
      title={collection?.name ?? lexiconKindLabels[selection.dictionaryKind]}
      rows={[
        ["资源表", `${tables.length} 张`],
        ["启用资源", `${tables.filter((table) => table.enabled).length} 张`],
        ["启用规则", `${enabledEntries} 条`],
        ["说明", collection?.description || "暂无说明"]
      ]}
      footer={<BindButton onBindToWorkflow={onBindToWorkflow} disabled={!tables.length} />}
    />
  );
}

function LexiconTableInspector({
  table,
  onBindToWorkflow
}: {
  table: DictionaryTableResource | null;
  onBindToWorkflow?: () => void;
}) {
  if (!table) {
    return (
      <InspectorCard
        eyebrow="词库资源表"
        title="资源表未找到"
        rows={[["状态", "当前选择已不在词库中"]]}
      />
    );
  }

  const enabledEntries = table.entries.filter((entry) => entry.enabled).length;
  const totalHits = table.entries.reduce((sum, entry) => sum + entry.hits, 0);

  return (
    <InspectorCard
      eyebrow="词库资源表"
      title={table.name}
      rows={[
        ["类型", lexiconKindLabels[table.kind]],
        ["条目", `${table.entries.length} 条`],
        ["启用条目", `${enabledEntries} 条`],
        ["命中", `${totalHits} 次`],
        ["来源", table.built_in ? "内置资源" : "项目资源"],
        ["编辑", table.editable ? "可编辑" : "只读"]
      ]}
      footer={<BindButton onBindToWorkflow={onBindToWorkflow} disabled={!table.entries.length} />}
    >
      <div className="lexicon-inspector-excerpt">
        <strong>说明</strong>
        <p>{table.description || "暂无说明。"}</p>
      </div>
      <div className="lexicon-inspector-token-strip" aria-label="词库条目样例">
        {table.entries.slice(0, 12).map((entry) => (
          <span key={entry.id}>{entry.source}</span>
        ))}
      </div>
    </InspectorCard>
  );
}

function LexiconEntryInspector({
  table,
  entry,
  onBindToWorkflow
}: {
  table: DictionaryTableResource | null;
  entry: DictionaryEntry | null;
  onBindToWorkflow?: () => void;
}) {
  if (!entry || !table) {
    return (
      <InspectorCard
        eyebrow="词库条目"
        title="条目未找到"
        rows={[["状态", "当前选择已不在词库中"]]}
      />
    );
  }

  return (
    <InspectorCard
      eyebrow="词库条目"
      title={entry.source || entry.id}
      rows={[
        ["资源表", table.name],
        ["目标词", entry.target || "无"],
        ["状态", entry.enabled ? "启用" : "停用"],
        ["命中", `${entry.hits} 次`],
        ["标签", entry.tags?.join("、") || "无"],
        ["备注", entry.notes || "无"]
      ]}
      footer={<BindButton onBindToWorkflow={onBindToWorkflow} />}
    />
  );
}

function InspectorCard({
  eyebrow,
  title,
  rows,
  children,
  footer
}: {
  eyebrow: string;
  title: string;
  rows: Array<[string, string]>;
  children?: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="workbench-inspector-card lexicon-inspector-card">
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
      {footer}
    </div>
  );
}

function BindButton({
  onBindToWorkflow,
  disabled
}: {
  onBindToWorkflow?: () => void;
  disabled?: boolean;
}) {
  return (
    <Button
      appearance="primary"
      icon={<DesktopFlowRegular />}
      onClick={onBindToWorkflow}
      disabled={disabled}
    >
      绑定到节点
    </Button>
  );
}
