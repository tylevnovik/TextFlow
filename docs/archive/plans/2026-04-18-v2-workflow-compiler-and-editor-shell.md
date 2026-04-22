# V2 Workflow Compiler And Editor Shell Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 TextFlow 的 V2 workflow 不再只是 manifest 里的占位数据，而是成为真实可编辑、可保存、可驱动现有线性引擎运行的最小入口。

**Architecture:** 以 `active_workflow` 为权威配置源，在 Python `project_store` 保存/加载链路中把 workflow 编译回当前 `pipeline`，继续复用现有执行器。桌面端把“处理与分析”页切成 workflow editor shell：左侧展示节点链，右侧展示选中节点参数，保存时提交 workflow，运行时仍走现有 `runPipeline()`。

**Tech Stack:** Python project store / defaults / pytest，React + TypeScript，shared types，Tauri desktop bridge

---

### Task 1: Define The Workflow Compiler Surface

**Files:**
- Modify: `services/python-engine/app/project_store.py`
- Modify: `packages/shared-types/src/index.ts`

**Step 1: Write down the supported node-to-pipeline mapping**

本阶段只支持现有单链 workflow：

- `filter_corpus` -> `run_scope`
- `clean_text` -> `cleaning`
- `normalize_text` -> `normalization`
- `tokenize` -> `tokenization`
- `apply_dictionary_rules` -> `dictionary`
- `filter_terms` -> `filtering`
- `analyze_corpus` -> `analysis`
- `export_results` -> `export`

**Step 2: Keep it intentionally narrow**

要求：

- 只支持 `graph_mode = single_chain_dag`
- 不支持分支执行或自动布局写回
- 节点 `ui_state.bypassed` 仅用于映射可选步骤开关

### Task 2: Make Workflow The Saved Source Of Truth

**Files:**
- Modify: `services/python-engine/app/project_store.py`
- Test: `services/python-engine/tests/test_workspace_cli.py`

**Step 1: Add a failing test**

目标测试：

- 当 `active_workflow` 中节点参数变化后，调用 `save_project()` 会把 `manifest["pipeline"]` 编译成对应的新值
- 当可选节点被 bypass 时，对应 `enabled_steps` 会被正确关闭

**Step 2: Implement compile helpers**

要求：

- 先 `normalize_pipeline_record()`
- 再 `normalize_workflow_definitions()`
- 解析 `active_workflow`
- 用 active workflow 重新编译 `pipeline`
- 最终 `run_history` 继续基于 active workflow 补齐元信息

**Step 3: Keep backward compatibility**

要求：

- 老项目如果没有 workflow，仍从 pipeline 自动迁移
- 旧客户端如果只提交 pipeline，也仍能保存成功

### Task 3: Add Frontend Workflow Editing Helpers

**Files:**
- Create: `apps/desktop/src/workflow.ts`
- Modify: `apps/desktop/src/screens.tsx`

**Step 1: Add a small frontend compiler**

用途：

- 从 `WorkflowDefinition` 派生当前页展示用的 `PipelineDefinition`
- 让现有配方卡片、输出摘要、文档筛选逻辑尽量复用

**Step 2: Add workflow draft helpers**

要求：

- 读取 active workflow
- 更新节点 `config`
- 更新节点 `ui_state.bypassed`
- 更新 workflow `meta.template_id` / `meta.output_bundle_id`

### Task 4: Replace The Pipeline Page With A Workflow Shell

**Files:**
- Modify: `apps/desktop/src/screens.tsx`
- Modify: `apps/desktop/src/styles.css`

**Step 1: Build the shell layout**

要求：

- 页面顶部保留保存 / 运行入口
- 中部改成 workflow shell：节点列表 + 参数面板
- 节点点击后切换右侧参数
- 明确提示“当前仍编译回 V1 线性执行器运行”

**Step 2: Keep the first node set minimal**

节点面板只覆盖当前已实现节点：

- `filter_corpus`
- `clean_text`
- `normalize_text`
- `tokenize`
- `apply_dictionary_rules`
- `filter_terms`
- `analyze_corpus`
- `export_results`

**Step 3: Reuse existing controls**

要求：

- 处理对象筛选继续复用现有 run scope 控件
- 配方 / 输出包控件继续可用，但改写到 workflow `meta`
- 右侧参数表单沿用现有各步骤字段

### Task 5: Verify The End-To-End Slice

**Files:**
- Test: `services/python-engine/tests/test_workspace_cli.py`
- Test: `services/python-engine/tests/test_pipeline.py`
- Build: `apps/desktop`

**Step 1: Run backend tests**

Run:

- `.\services\python-engine\.venv\Scripts\python.exe -m pytest services/python-engine/tests/test_workspace_cli.py -q`
- `.\services\python-engine\.venv\Scripts\python.exe -m pytest services/python-engine/tests/test_pipeline.py -q`

**Step 2: Run desktop build**

Run:

- `npm run build --workspace apps/desktop`

**Step 3: Check the regression boundary**

确认：

- 保存 workflow 后重新加载，UI 仍显示同一套节点参数
- 运行记录继续落在现有 `run_history`
- 没有引入 drag-and-drop、局部执行、节点缓存等超出本阶段范围的行为
