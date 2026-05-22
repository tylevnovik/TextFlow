import { useEffect, useMemo, useState } from "react";
import { Button } from "@fluentui/react-components";
import type { ArtifactRecord } from "@textflow/shared-types";
import { MiniMetric, Panel } from "../../ui";

export interface ArtifactPreview {
  artifact_id: string;
  columns?: string[];
  rows: Array<Record<string, unknown>>;
  row_count?: number;
  preview_rows?: number;
}

export interface ArtifactBrowserProps {
  artifacts: ArtifactRecord[];
  loading?: boolean;
  onLoadPreview: (artifactId: string) => Promise<ArtifactPreview>;
  onOpenArtifact?: (artifact: ArtifactRecord) => void;
  selectedArtifactId?: string;
  title?: string;
}

function printableValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

export function ArtifactBrowser({
  artifacts,
  loading = false,
  onLoadPreview,
  onOpenArtifact,
  selectedArtifactId,
  title = "节点产物"
}: ArtifactBrowserProps) {
  const [preview, setPreview] = useState<ArtifactPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const selectedArtifact = preview ? artifacts.find((artifact) => artifact.artifact_id === preview.artifact_id) : null;
  const previewColumns = useMemo(() => {
    if (!preview) {
      return [];
    }
    if (preview.columns?.length) {
      return preview.columns;
    }
    return Array.from(new Set(preview.rows.flatMap((row) => Object.keys(row))));
  }, [preview]);

  const handleLoadPreview = async (artifactId: string) => {
    setPreviewError(null);
    setPreviewLoading(artifactId);
    try {
      const nextPreview = await onLoadPreview(artifactId);
      setPreview(nextPreview);
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : "产物预览加载失败");
    } finally {
      setPreviewLoading(null);
    }
  };

  useEffect(() => {
    if (!selectedArtifactId || preview?.artifact_id === selectedArtifactId) {
      return;
    }
    if (!artifacts.some((artifact) => artifact.artifact_id === selectedArtifactId)) {
      return;
    }
    void handleLoadPreview(selectedArtifactId);
  }, [artifacts, preview?.artifact_id, selectedArtifactId]);

  return (
    <Panel title={title} className="artifact-browser-panel">
      <div className="surface-metric-row">
        <MiniMetric label="产物" value={String(artifacts.length)} />
        <MiniMetric label="可预览" value={String(artifacts.length)} />
        <MiniMetric label="总行数" value={String(artifacts.reduce((total, artifact) => total + (artifact.row_count ?? 0), 0))} />
      </div>

      <div className="artifact-browser-layout">
        <div className="stack-list">
          {artifacts.map((artifact) => {
            const isActive = artifact.artifact_id === selectedArtifactId || artifact.artifact_id === preview?.artifact_id;
            return (
            <article key={artifact.artifact_id} className={`project-card artifact-record-card ${isActive ? "is-active" : ""}`.trim()}>
              <div>
                <div className="run-head">
                  <h4>{artifact.artifact_id}</h4>
                  <span className="pill">{artifact.kind}</span>
                </div>
                {artifact.path && <p className="project-path">{artifact.path}</p>}
                <p className="muted">
                  run {artifact.run_id} · node {artifact.node_id} · {artifact.row_count ?? "未知"} 行
                </p>
              </div>
              <div className="button-row">
                <Button
                  size="small"
                  onClick={() => void handleLoadPreview(artifact.artifact_id)}
                  disabled={loading || previewLoading === artifact.artifact_id}
                >
                  {previewLoading === artifact.artifact_id ? "加载中" : "加载预览"}
                </Button>
                <Button
                  size="small"
                  appearance="subtle"
                  onClick={() => onOpenArtifact?.(artifact)}
                  disabled={loading || !onOpenArtifact}
                >
                  打开
                </Button>
              </div>
            </article>
            );
          })}
          {!artifacts.length && (
            <div className="status-panel">
              <strong>还没有运行产物</strong>
              <span className="muted">完成一次工作流后，这里会列出节点产物并支持懒加载预览。</span>
            </div>
          )}
        </div>

        <div className="artifact-preview-card">
          <div className="run-head">
            <h4>预览</h4>
            <span className="badge ready">{preview?.rows.length ?? 0} rows</span>
          </div>
          {previewError && <p className="warning-text">{previewError}</p>}
          {preview ? (
            <>
              <p className="muted">
                {selectedArtifact?.artifact_id ?? preview.artifact_id} · 共 {preview.row_count ?? selectedArtifact?.row_count ?? preview.rows.length} 行
              </p>
              <div className="table-wrap artifact-preview-table">
                <table>
                  <thead>
                    <tr>
                      {previewColumns.map((column) => (
                        <th key={column}>{column}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row, index) => (
                      <tr key={`${preview.artifact_id}-${index}`}>
                        {previewColumns.map((column) => (
                          <td key={column}>{printableValue(row[column])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="muted">选择一个产物并点击“加载预览”，表格才会读取到界面里。</p>
          )}
        </div>
      </div>
    </Panel>
  );
}
