import type { PageId } from "@textflow/shared-types";
import { useWorkspace } from "./store/workspaceStore";
import { PageView, pageMeta } from "./screens";

const primaryPages: PageId[] = ["home", "data", "dictionaries", "pipeline", "results"];

export function App() {
  const {
    state: { activePage, snapshot, loading, progress, statusLine },
    setActivePage,
    runPipeline,
    exportProject
  } = useWorkspace();

  const project = snapshot.current_project;

  return (
    <div className="app-shell">
      <div className="background-grid" />

      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true">TF</div>
            <div>
              <p className="eyebrow">TextFlow Studio</p>
              <h1>TextFlow</h1>
            </div>
          </div>
          <p className="brand-copy">文本整理与基础分析工具。按项目保存数据、词表和结果。</p>
        </div>

        <nav className="nav-list" aria-label="主导航">
          {primaryPages.map((page) => (
            <button
              key={page}
              className={`nav-item ${activePage === page ? "is-active" : ""}`}
              onClick={() => setActivePage(page as PageId)}
              type="button"
            >
              <span>{pageMeta[page].title}</span>
              <small>{pageMeta[page].tag}</small>
            </button>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div className="status-chip">
            <span className={`dot ${loading ? "loading" : "ready"}`} />
            {loading ? "后台处理中" : "可以继续操作"}
          </div>
          <p>当前项目位置</p>
          <strong>{project?.paths.root ?? "尚未加载 .tfproj"}</strong>
        </div>
      </aside>

      <main className="main-stage">
        <header className="topbar">
          <div>
            <p className="eyebrow">当前步骤</p>
            <h2>{pageMeta[activePage].headline}</h2>
            <p className="topbar-copy">{statusLine}</p>
          </div>

          <div className="toolbar">
            <button type="button" className="toolbar-button ghost" onClick={() => setActivePage("home")}>
              回到开始
            </button>
            <button type="button" className="toolbar-button" onClick={() => void runPipeline()} disabled={loading || !project}>
              开始处理
            </button>
            <button
              type="button"
              className="toolbar-button accent"
              onClick={() => void exportProject(["csv", "xlsx", "html", "png"])}
              disabled={loading || !project}
            >
              导出结果
            </button>
          </div>
        </header>

        {progress.status !== "idle" && (
          <section className={`progress-strip status-${progress.status}`}>
            <div className="progress-strip-copy">
              <strong>{progress.message || "后台正在处理"}</strong>
              <span>{Math.round(progress.value * 100)}%</span>
            </div>
            <div className="progress-track" aria-hidden="true">
              <div className="progress-fill" style={{ width: `${Math.max(6, progress.value * 100)}%` }} />
            </div>
          </section>
        )}

        <section className="content-grid">
          <PageView page={activePage} />
        </section>
      </main>
    </div>
  );
}
