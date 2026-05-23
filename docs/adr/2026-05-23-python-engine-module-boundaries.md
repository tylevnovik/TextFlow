# ADR: Python Engine 模块边界与渐进式重构

日期：2026-05-23

状态：Accepted

实现记录：

- 2026-05-23：完成第一轮包化迁移。`analysis`、`api`、`domain`、`ingestion`、`reporting`、`samples`、`storage`、`workflow/definitions`、`workflow/executors`、`workflow/runtime` 已建立，旧平铺模块名保留为兼容入口。
- 2026-05-23：彻底清理兼容性包装器（Wrappers），物理删除了所有旧平铺模块文件，并将全部测试和脚本的导入路径重定向到最新的新模块路径。

## 背景

`services/python-engine/app` 已经承载导入、项目存储、DAG workflow、节点目录、节点执行、文本分析、图计算、导出报告、内置样例和 sidecar action。功能已经连通，但目录仍基本平铺，多个文件承担了跨层职责：

- `node_executors.py` 同时包含语料、预处理、分析、图计算、导出和 legacy 节点执行器。
- `defaults.py` 同时包含默认值、词表 seed、import template、workflow schema、edge normalization 和 runtime profile helper。
- `project_store.py` 同时包含 workspace、project CRUD、manifest normalization、模板、项目包导入导出和摘要生成。
- `dag_runtime.py` 同时包含 DAG 调度、缓存、执行上下文、runtime preview、artifact 绑定和错误记录。
- `cli.py` 同时是 action router 和 action 业务实现。

这让新增节点或样例时很容易把代码继续塞进大文件，也让性能评估变难：读代码时不容易判断某个 import 是否会影响 sidecar 冷启动，某段拷贝是否在 workflow 热路径里。

## 决策

Python engine 继续保持单进程本地 sidecar，不引入微服务或额外运行时。重构方向是**包内分层 + 渐进迁移 + 旧 import 兼容层**。

最终目标结构如下：

```text
services/python-engine/app/
  api/
    service.py                  # HTTP task service and task manager
    actions/
      __init__.py
      projects.py               # project/workspace actions
      imports.py                # corpus and dictionary import/export actions
      workflows.py              # run, artifact, run history actions
      reviews.py                # review task actions
      experiments.py            # experiment matrix actions

  domain/
    corpus.py                   # corpus row helpers and typed domain helpers
    dictionary.py               # dictionary model helpers
    workflow.py                 # workflow graph helpers and compatibility rules
    results.py                  # result bundle keys and normalization
    project.py                  # manifest/domain-level project helpers

  ingestion/
    importers.py                # txt/csv/xlsx/json readers and mapping
    profiles.py                 # source profile templates
    specs.py                    # saved ingestion specs

  workflow/
    definitions/
      __init__.py
      builtin.py                # built-in node definitions
      ports.py                  # port and parameter helpers
    compilers.py                # node config -> runtime profile compilation
    registry.py                 # node registry and plugin loading boundary
    plugins.py                  # local node plugin discovery
    runtime/
      context.py                # WorkflowExecutionContext and node state
      scheduler.py              # topological batching and execution loop
      cache.py                  # node cache key and payload IO
      artifacts.py              # output binding and artifact materialization
      previews.py               # lightweight runtime output previews
    executors/
      __init__.py
      support.py                # executor shared helpers
      corpus.py                 # corpus input/filter/merge/sampling/splitting
      preprocessing.py          # clean/normalize/tokenize/dictionary/filter/focus
      analysis.py               # frequency, term-doc/year, keywords, topics, clusters
      graph.py                  # cooccurrence network and graph algorithms
      export.py                 # CSV/XLSX/PNG/HTML nodes
      legacy.py                 # compatibility nodes

  analysis/
    text.py                     # text cleaning, tokenization, dictionary application
    statistics.py               # frequency, term-document, term-year
    keywords.py                 # TF-IDF, YAKE, feature terms, keyword clustering
    topics.py                   # NMF/LDA and document clustering
    graph.py                    # graph construction and graph metrics
    technology.py               # technology indicators and classification

  storage/
    workspace.py                # workspace root/state/recent projects
    projects.py                 # project CRUD and manifest persistence
    database.py                 # SQLite schema and read/write adapters
    artifacts.py                # artifact payload store
    resources.py                # corpus views and project resources
    templates.py                # project/import templates

  reporting/
    html.py                     # HTML report
    charts.py                   # PNG/chart generation
    tables.py                   # result table selection and export helpers

  samples/
    projects.py                 # built-in sample specs and materialization
    seed_sources.py             # sample seed discovery and license checks
    bundled_workspace.py        # packaged sample workspace build/restore

  compatibility/
    legacy_modules.md           # removal checklist for old flat imports
```

经过对旧包装器的清理，所有过渡性的旧模块路径（如 `app.sample_projects`、`app.node_registry` 和 `app.project_store` 等）均已被彻底删除。新代码和现有代码必须直接导入对应的目标包路径。

## Dependency Rules

The target dependency direction is one-way:

```text
api/actions
  -> workflow/runtime, ingestion, storage, reporting, samples
workflow/runtime
  -> workflow/registry, workflow/executors, storage/artifacts, domain
workflow/executors
  -> analysis, domain, reporting only when executing export nodes
analysis
  -> domain and third-party compute libraries
storage
  -> domain and filesystem/sqlite only
samples
  -> ingestion, storage, workflow definitions/builders
```

Rules:

- `api` may orchestrate, but must not contain analysis or storage normalization logic.
- `analysis` must not import `api`, `storage`, `workflow.runtime`, or sample modules.
- `workflow.executors` may call analysis functions, but analysis functions must not know about node ids, run records, or UI artifact handles.
- Heavy third-party imports such as `pandas`, `sklearn`, `yake`, `matplotlib`, `wordcloud`, and graph libraries must stay out of `api/service.py` cold-start paths unless already required by an action.
- Compatibility wrappers must not add new behavior. They only forward imports while callers migrate. （注：兼容性包装器已在重构完成后彻底清理移除）。

## Migration Strategy

Use a strangler pattern:

1. Add target package directories and move one cohesive domain slice at a time.
2. Keep old flat module names as wrappers until all internal imports and tests use the new path.
3. For each moved module, run import compatibility tests and the smallest relevant engine suite.
4. Split large files only after their destination package and tests exist.
5. Remove wrappers only in a later cleanup release after repo-wide imports are migrated. （已完成：过渡包装器已被物理删除，所有代码的引用路径已被修正）。

Recommended order:

1. `samples/*`: low runtime risk and directly related to sample project work.
2. `workflow/registry.py`, `workflow/compilers.py`, `workflow/plugins.py`: establishes workflow package without changing execution behavior.
3. `workflow/executors/*`: split `node_executors.py` by node category.
4. `analysis/*`: split `analysis_ops.py` by statistics, keywords, topics, and clustering.
5. `storage/*`: split `project_store.py` and `project_database.py` after project package tests are stable.
6. `workflow/runtime/*`: split `dag_runtime.py` last, because it is the highest-risk orchestration path.
7. `api/actions/*`: split `cli.py` after storage/runtime boundaries are clearer.

## Performance Impact Assessment

Expected impact of pure module relocation is neutral for workflow runtime. The hot path cost is dominated by tokenization, TF-IDF/YAKE, clustering, graph construction, report export, SQLite/artifact IO, and cache serialization, not by which file contains the function.

Real performance risks are:

- **Cold-start regression**: moving code can accidentally import heavy analysis libraries during `app.cli` or `app.service` import.
- **Hot-loop dynamic import regression**: replacing direct function calls with repeated dynamic imports inside per-document or per-token loops would add measurable overhead.
- **Extra copying**: refactors around `WorkflowExecutionContext`, corpus rows, result bundles, or artifact payloads may reintroduce large `deepcopy` or JSON serialization in the run path.
- **Cache key churn**: changing runtime payload normalization can invalidate existing node caches or alter cache hit rates.
- **Path resolution bugs**: moving sample and bundled workspace code can change `Path(__file__)` semantics and accidentally read/write the wrong bundled resource directory.

Performance guardrails:

- Keep heavy imports lazy where they are already lazy, especially in node execution and sidecar startup paths.
- Do not add dynamic imports inside document/token loops.
- Do not add broad `deepcopy` of corpus rows, result bundles, or workflow graphs in runtime execution unless a test proves mutation isolation requires it.
- Keep old cache key inputs byte-for-byte stable during no-behavior migration.
- Preserve sample/bundled resource paths explicitly when moving files.

Minimum verification by change type:

```powershell
# Import compatibility and light engine checks
services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_node_catalog_parity.py services\python-engine\tests\test_workspace_cli.py -q

# Day-to-day engine guardrail
npm run test:engine:fast

# Required when touching samples, bundled workspace, sidecar build/bootstrap, or sample packaging paths
npm run test:engine:full

# Optional cold-start import visibility
Push-Location services\python-engine
.\.venv\Scripts\python.exe -X importtime -c "import app.cli" 2> ..\..\importtime-app-cli.log
Pop-Location

# Optional large workflow runtime check
powershell -ExecutionPolicy Bypass -File .\scripts\run-large-benchmark.ps1 --limit 1200
```

Acceptance criteria for structural refactors:

- Existing public action payloads and manifest formats remain compatible.
- Old module imports continue to work until wrappers are explicitly removed. （已完成：包装器已物理删除，所有新老代码彻底统一到了新模块路径）。
- Relevant tests pass.
- No new eager import of heavy analysis/export libraries on `import app.cli` without a documented reason.
- Benchmark changes, when measured, are explained by algorithm/data changes rather than file movement.

## Consequences

Benefits:

- New contributors can find code by product responsibility instead of hunting through large files.
- Node categories can evolve independently, which makes future node-based editor work easier.
- Performance ownership becomes clearer: startup, DAG scheduling, analysis compute, storage IO, and reporting have separate homes.
- Old modules can be retired gradually without breaking packaging in one large risky change.

Trade-offs:

- （已完成移除）在迁移期间存在新旧路径并存的情况。目前旧包装器已被彻底移除，导入已经完全直接化。
- 所有单元测试和脚本现直接针对新模块路径进行测试，移除了遗留的兼容性测试。
