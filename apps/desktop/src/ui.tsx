import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from "react";
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

export function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="mini-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
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
  rows,
  rowKey
}: {
  columns: string[];
  rows: Array<object>;
  rowKey?: string | ((row: object, index: number) => string);
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
            <tr
              key={typeof rowKey === "function"
                ? rowKey(row, index)
                : rowKey
                  ? String((row as Record<string, unknown>)[rowKey] ?? index)
                  : `${index}`}
            >
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

export function PaginatedTable({
  columns,
  rows,
  pageSize = 25,
  rowKey
}: {
  columns: string[];
  rows: Array<object>;
  pageSize?: number;
  rowKey?: string | ((row: object, index: number) => string);
}) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));

  useEffect(() => {
    setPage(1);
  }, [rows.length, pageSize]);

  const safePage = Math.min(page, totalPages);
  const visibleRows = useMemo(
    () => rows.slice((safePage - 1) * pageSize, safePage * pageSize),
    [pageSize, rows, safePage]
  );

  return (
    <>
      <Table columns={columns} rows={visibleRows} rowKey={rowKey} />
      <div className="button-row dictionary-page-nav">
        <span className="helper-note">
          当前显示第 {safePage} / {totalPages} 页，
          第 {rows.length ? (safePage - 1) * pageSize + 1 : 0} - {Math.min(safePage * pageSize, rows.length)} 条，
          每页 {pageSize} 条。
        </span>
        <button type="button" className="toolbar-button ghost" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={safePage <= 1}>
          上一页
        </button>
        <button type="button" className="toolbar-button ghost" onClick={() => setPage((current) => Math.min(totalPages, current + 1))} disabled={safePage >= totalPages}>
          下一页
        </button>
      </div>
    </>
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
  const [page, setPage] = useState(1);
  const pageSize = 24;
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const visibleRows = useMemo(
    () => rows.slice((safePage - 1) * pageSize, safePage * pageSize),
    [rows, safePage]
  );

  useEffect(() => {
    setPage(1);
  }, [rows.length]);

  return (
    <>
      <div className="rank-list">
        {visibleRows.map((row) => (
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
      <div className="button-row dictionary-page-nav">
        <span className="helper-note">当前显示第 {safePage} / {totalPages} 页，每页 {pageSize} 条。</span>
        <button type="button" className="toolbar-button ghost" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={safePage <= 1}>
          上一页
        </button>
        <button type="button" className="toolbar-button ghost" onClick={() => setPage((current) => Math.min(totalPages, current + 1))} disabled={safePage >= totalPages}>
          下一页
        </button>
      </div>
    </>
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
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [hoveredRow, setHoveredRow] = useState<DocumentClusterRow | null>(null);
  const width = 320;
  const height = 240;
  const padding = 24;
  const colors = ["#d6a84f", "#264653", "#2a9d8f", "#c65d3b", "#6d597a"];

  const plottedRows = useMemo(() => {
    if (!rows.length) {
      return [];
    }
    const xs = rows.map((row) => row.x);
    const ys = rows.map((row) => row.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const scaleX = (value: number) => padding + ((value - minX) / Math.max(maxX - minX, 1e-6)) * (width - padding * 2);
    const scaleY = (value: number) => height - padding - ((value - minY) / Math.max(maxY - minY, 1e-6)) * (height - padding * 2);
    return rows.map((row) => ({
      ...row,
      px: scaleX(row.x),
      py: scaleY(row.y)
    }));
  }, [rows]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#f5efe2";
    context.fillRect(0, 0, width, height);
    context.strokeStyle = "#b9ad93";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(padding, height / 2);
    context.lineTo(width - padding, height / 2);
    context.moveTo(width / 2, padding);
    context.lineTo(width / 2, height - padding);
    context.stroke();

    plottedRows.forEach((row) => {
      context.beginPath();
      context.fillStyle = colors[row.cluster_id % colors.length] ?? colors[0];
      context.arc(row.px, row.py, hoveredRow?.doc_id === row.doc_id ? 7 : 5, 0, Math.PI * 2);
      context.fill();
    });
  }, [colors, hoveredRow?.doc_id, plottedRows]);

  const handlePointerMove = (event: ReactMouseEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * width;
    const y = ((event.clientY - rect.top) / rect.height) * height;
    let candidate: DocumentClusterRow | null = null;
    let minDistance = 12;
    plottedRows.forEach((row) => {
      const distance = Math.hypot(row.px - x, row.py - y);
      if (distance <= minDistance) {
        minDistance = distance;
        candidate = row;
      }
    });
    setHoveredRow(candidate);
  };

  return (
    <div className="scatter-card">
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="chart-canvas"
        role="img"
        aria-label="document clusters"
        onMouseMove={handlePointerMove}
        onMouseLeave={() => setHoveredRow(null)}
      />
      <p className="chart-caption">
        {hoveredRow
          ? `${hoveredRow.doc_id} · 簇 ${hoveredRow.cluster_id} · ${hoveredRow.title}`
          : "移动到点上可查看文档信息。"}
      </p>
    </div>
  );
}

export function KeywordPanel({
  featureTerms,
  keywords
}: {
  featureTerms: FeatureTermRow[];
  keywords: Array<{ keyword: string; score: number; scope: string }>;
}) {
  const [featurePage, setFeaturePage] = useState(1);
  const featurePageSize = 48;
  const totalFeaturePages = Math.max(1, Math.ceil(featureTerms.length / featurePageSize));
  const safeFeaturePage = Math.min(featurePage, totalFeaturePages);
  const visibleFeatureTerms = useMemo(
    () => featureTerms.slice((safeFeaturePage - 1) * featurePageSize, safeFeaturePage * featurePageSize),
    [featureTerms, safeFeaturePage]
  );

  useEffect(() => {
    setFeaturePage(1);
  }, [featureTerms.length]);

  return (
    <>
      <div className="pill-cloud">
        {visibleFeatureTerms.map((term) => (
          <span key={term.term} className={`pill ${term.selected ? "selected" : ""}`}>
            {term.term} · {term.score.toFixed(2)}
          </span>
        ))}
      </div>
      <div className="button-row dictionary-page-nav">
        <span className="helper-note">特征词第 {safeFeaturePage} / {totalFeaturePages} 页，每页 {featurePageSize} 条。</span>
        <button type="button" className="toolbar-button ghost" onClick={() => setFeaturePage((current) => Math.max(1, current - 1))} disabled={safeFeaturePage <= 1}>
          上一页
        </button>
        <button type="button" className="toolbar-button ghost" onClick={() => setFeaturePage((current) => Math.min(totalFeaturePages, current + 1))} disabled={safeFeaturePage >= totalFeaturePages}>
          下一页
        </button>
      </div>
      <PaginatedTable
        columns={["scope", "keyword", "score"]}
        rows={keywords.map((row) => ({
          scope: row.scope,
          keyword: row.keyword,
          score: row.score.toFixed(2)
        }))}
        rowKey={(row) => `${(row as { scope: string; keyword: string }).scope}-${(row as { scope: string; keyword: string }).keyword}`}
        pageSize={18}
      />
    </>
  );
}

export function TopicPanel({
  rows
}: {
  rows: Array<{ institution: string; topic_label: string; cooccurrence_count: number; representative_terms: string[] }>;
}) {
  const [page, setPage] = useState(1);
  const pageSize = 18;
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const visibleRows = useMemo(
    () => rows.slice((safePage - 1) * pageSize, safePage * pageSize),
    [rows, safePage]
  );

  useEffect(() => {
    setPage(1);
  }, [rows.length]);

  return (
    <>
      <div className="stack-list">
        {visibleRows.map((row) => (
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
      <div className="button-row dictionary-page-nav">
        <span className="helper-note">当前显示第 {safePage} / {totalPages} 页，每页 {pageSize} 条。</span>
        <button type="button" className="toolbar-button ghost" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={safePage <= 1}>
          上一页
        </button>
        <button type="button" className="toolbar-button ghost" onClick={() => setPage((current) => Math.min(totalPages, current + 1))} disabled={safePage >= totalPages}>
          下一页
        </button>
      </div>
    </>
  );
}

export function AuditTable({ rows }: { rows: AuditRow[] }) {
  return (
    <PaginatedTable
      columns={["doc_id", "source_term", "target_term", "rule_type", "action"]}
      rows={rows.map((row) => ({
        doc_id: row.doc_id,
        source_term: row.source_term,
        target_term: row.target_term ?? "—",
        rule_type: row.rule_type,
        action: row.action
      }))}
      rowKey={(row, index) => `${(row as { doc_id: string; source_term: string }).doc_id}-${(row as { doc_id: string; source_term: string }).source_term}-${index}`}
      pageSize={20}
    />
  );
}
