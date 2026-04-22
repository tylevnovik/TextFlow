import type { ReactNode } from "react";
import type {
  AuditRow,
  CorpusItem,
  DictionarySheet,
  DocumentClusterRow,
  FeatureTermRow,
  FrequencyRow
} from "@textflow/shared-types";

export type DocumentPreviewMode = "raw_text" | "metadata";

export function Panel({
  children,
  title,
  className = "",
  actions
}: {
  children: ReactNode;
  title?: string;
  className?: string;
  actions?: ReactNode;
}) {
  return (
    <section className={`panel ${className}`.trim()}>
      {(title || actions) && (
        <header className="panel-head">
          <div>{title && <h3>{title}</h3>}</div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <Panel className="empty-panel">
      <h3>{title}</h3>
      <p>{body}</p>
    </Panel>
  );
}

export function StatCard({
  label,
  value,
  tone
}: {
  label: string;
  value: string;
  tone: "gold" | "ink" | "emerald" | "rose";
}) {
  return (
    <article className={`stat-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

export function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="meta-item">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function Table({
  columns,
  rows
}: {
  columns: string[];
  rows: Array<object>;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${index}-${columns.map((column) => String((row as Record<string, unknown>)[column] ?? "")).join("-")}`}>
              {columns.map((column) => (
                <td key={column}>{String((row as Record<string, unknown>)[column] ?? "—")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DocumentPreview({
  doc,
  mode,
  onModeChange
}: {
  doc: CorpusItem;
  mode: DocumentPreviewMode;
  onModeChange: (mode: DocumentPreviewMode) => void;
}) {
  const previewModes: Array<{ id: DocumentPreviewMode; label: string }> = [
    { id: "raw_text", label: "原文" },
    { id: "metadata", label: "元数据" }
  ];

  const previewContent = (() => {
    if (mode === "metadata") {
      return JSON.stringify(doc.extra_metadata ?? {}, null, 2);
    }
    return doc.raw_text || "当前文档没有正文内容。";
  })();

  return (
    <article className="preview-card">
      <div className="run-head">
        <h4>{doc.title}</h4>
        <span className={`badge ${doc.status}`}>{doc.status}</span>
      </div>
      <ul className="micro-list">
        <li>doc_id: {doc.doc_id}</li>
        <li>institution: {doc.institution ?? "—"}</li>
        <li>year: {doc.year ?? "—"}</li>
      </ul>
      <div className="tab-row">
        {previewModes.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`tab-button ${mode === item.id ? "is-active" : ""}`}
            onClick={() => onModeChange(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {mode === "metadata" ? (
        <pre className="code-box preview-code">{previewContent}</pre>
      ) : (
        <p className="body-copy preview-copy">{previewContent}</p>
      )}
    </article>
  );
}

export function DictionaryTable({ sheet }: { sheet: DictionarySheet }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>原词 / 模式</th>
            <th>目标词</th>
            <th>命中次数</th>
            <th>是否启用</th>
          </tr>
        </thead>
        <tbody>
          {sheet.entries.map((entry) => (
            <tr key={entry.id}>
              <td>{entry.source || "—"}</td>
              <td>{entry.target || "—"}</td>
              <td>{entry.hits}</td>
              <td>{entry.enabled ? "启用" : "停用"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function FrequencyTable({ rows }: { rows: FrequencyRow[] }) {
  return (
    <div className="rank-list">
      {rows.map((row) => (
        <article className="rank-row" key={row.term}>
          <div>
            <h4>{row.term}</h4>
            <p>
              TF {row.tf} / DF {row.df} / 占比 {(row.ratio * 100).toFixed(1)}%
            </p>
          </div>
          <strong>{row.avg_per_doc.toFixed(1)}</strong>
        </article>
      ))}
    </div>
  );
}

export function LineChart({ values, labels }: { values: number[]; labels: string[] }) {
  const max = Math.max(...values, 1);
  const width = 420;
  const height = 180;
  const points = values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * (width - 32) + 16;
      const y = height - 20 - (value / max) * (height - 40);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" role="img" aria-label="trend chart">
      <polyline fill="none" stroke="currentColor" strokeWidth="3" points={points} />
      {values.map((value, index) => {
        const x = (index / Math.max(values.length - 1, 1)) * (width - 32) + 16;
        const y = height - 20 - (value / max) * (height - 40);
        return (
          <g key={`${labels[index]}-${value}`}>
            <circle cx={x} cy={y} r="5" />
            <text x={x} y={height - 2} textAnchor="middle">
              {labels[index]}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function ScatterChart({ rows }: { rows: DocumentClusterRow[] }) {
  return (
    <svg viewBox="0 0 320 240" className="chart-svg" role="img" aria-label="document clusters">
      <line x1="20" y1="120" x2="300" y2="120" />
      <line x1="160" y1="20" x2="160" y2="220" />
      {rows.map((row) => {
        const x = 160 + row.x * 100;
        const y = 120 - row.y * 100;
        return (
          <g key={row.doc_id}>
            <circle cx={x} cy={y} r="8" className={`cluster-${row.cluster_id % 3}`} />
            <text x={x} y={y - 14} textAnchor="middle">
              {row.doc_id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function KeywordPanel({
  featureTerms,
  keywords
}: {
  featureTerms: FeatureTermRow[];
  keywords: Array<{ keyword: string; score: number; scope: string }>;
}) {
  return (
    <>
      <div className="pill-cloud">
        {featureTerms.map((term) => (
          <span key={term.term} className={`pill ${term.selected ? "selected" : ""}`}>
            {term.term} · {term.score.toFixed(2)}
          </span>
        ))}
      </div>
      <Table
        columns={["scope", "keyword", "score"]}
        rows={keywords.map((row) => ({
          scope: row.scope,
          keyword: row.keyword,
          score: row.score.toFixed(2)
        }))}
      />
    </>
  );
}

export function TopicPanel({
  rows
}: {
  rows: Array<{ institution: string; topic_label: string; cooccurrence_count: number; representative_terms: string[] }>;
}) {
  return (
    <div className="stack-list">
      {rows.map((row) => (
        <article className="topic-card" key={`${row.institution}-${row.topic_label}`}>
          <div className="run-head">
            <strong>{row.institution}</strong>
            <span className="pill">{row.cooccurrence_count} 次命中</span>
          </div>
          <h4>{row.topic_label}</h4>
          <p>{row.representative_terms.join(" / ")}</p>
        </article>
      ))}
    </div>
  );
}

export function AuditTable({ rows }: { rows: AuditRow[] }) {
  return (
    <Table
      columns={["doc_id", "source_term", "target_term", "rule_type", "action"]}
      rows={rows.map((row) => ({
        doc_id: row.doc_id,
        source_term: row.source_term,
        target_term: row.target_term ?? "—",
        rule_type: row.rule_type,
        action: row.action
      }))}
    />
  );
}
