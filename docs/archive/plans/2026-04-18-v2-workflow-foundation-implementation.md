# V2 Workflow Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 TextFlow Studio 落下 V2 节点工作流的第一阶段基础数据层，让项目 manifest、默认 schema、旧项目迁移和 run 记录都能识别 `workflow`，同时不破坏当前线性执行器。

**Architecture:** 保持当前 `pipeline` 作为真实执行输入，在 `ProjectManifest` 上新增 `workflow_definitions` 与 `active_workflow_id`。项目加载时自动把旧 `pipeline` 迁移成默认 workflow；运行时继续走线性 pipeline，但在 `RunRecord` 中记录 workflow 来源。

**Tech Stack:** TypeScript shared types、React demo data、Python project store / defaults / pipeline、pytest

---

### Task 1: Shared Types And Demo Data

**Files:**
- Modify: `packages/shared-types/src/index.ts`
- Modify: `apps/desktop/src/data/demoProject.ts`

**Step 1: Add failing type surface mentally**

目标：

- `ProjectManifest` 需要新增 `workflow_definitions`、`active_workflow_id`
- `RunRecord` 需要新增 `workflow_id`、`workflow_name`、`workflow_hash`
- shared types 需要新增 `WorkflowDefinition`、`WorkflowNodeInstance`、`WorkflowEdge`

**Step 2: Write minimal type additions**

要求：

- 不改掉现有 `pipeline` 字段
- `WorkflowDefinition` 先只覆盖 Phase 1 需要的字段
- demo project 同步补齐新字段

**Step 3: Verify TypeScript-facing consistency**

检查：

- `ProjectManifest` 的构造对象能通过类型检查
- demo data 的 run record 和 manifest 都包含新字段

### Task 2: Python Defaults And Manifest Migration

**Files:**
- Modify: `services/python-engine/app/defaults.py`
- Modify: `services/python-engine/app/project_store.py`

**Step 1: Write failing tests first**

目标测试：

- 新项目默认带一个 `workflow_definitions[0]`
- 旧项目缺失 workflow 字段时，`load_project()` 会自动补齐
- `active_workflow_id` 会指向默认 workflow

**Step 2: Add default workflow builders**

要求：

- 从当前线性 `pipeline` 生成一个默认单链 workflow
- 节点状态来自 `enabled_steps` / `execution_order`
- `recipe_id` / `output_bundle_id` 写入 workflow meta

**Step 3: Hook normalization**

要求：

- `normalize_project_manifest()` 自动补齐 workflow 字段
- 对旧 manifest 不破坏已有 `pipeline`

### Task 3: RunRecord Workflow Linkage

**Files:**
- Modify: `services/python-engine/app/pipeline.py`
- Modify: `services/python-engine/app/project_store.py`
- Test: `services/python-engine/tests/test_pipeline.py`

**Step 1: Write failing tests**

目标测试：

- 跑 pipeline 后，`run_record` 带有 `workflow_id` / `workflow_name` / `workflow_hash`
- 旧 `run_history` 重新加载时能补默认 workflow 信息

**Step 2: Implement minimal runtime linkage**

要求：

- 运行时读取 `active_workflow_id`
- 若 workflow 缺失则回退到默认迁移 workflow
- `workflow_hash` 基于 workflow 定义稳定生成

**Step 3: Keep execution model unchanged**

要求：

- 仍由 `manifest["pipeline"]` 进入 `run_project_pipeline`
- 不引入局部执行或节点缓存逻辑

### Task 4: Verification

**Files:**
- Test: `services/python-engine/tests/test_workspace_cli.py`
- Test: `services/python-engine/tests/test_pipeline.py`

**Step 1: Run focused tests**

Run:

- `.\services\python-engine\.venv\Scripts\python.exe -m pytest services/python-engine/tests/test_workspace_cli.py -q`
- `.\services\python-engine\.venv\Scripts\python.exe -m pytest services/python-engine/tests/test_pipeline.py -q`

**Step 2: Fix regressions**

范围：

- schema default
- legacy manifest normalization
- demo data type breakage

**Step 3: Re-run focused tests**

预期：

- 上述测试全部通过

### Task 5: Final Sanity Check

**Files:**
- Modify if needed: `README.md`
- Modify if needed: `docs/pipeline-spec.md`

**Step 1: Ensure docs still match implementation**

检查：

- 当前代码确实只实现 foundation，不实现画布运行时
- 文档中没有把未完成能力写成已完成

**Step 2: Summarize delivered slice**

输出：

- 本轮新增了哪些 schema / migration / test 能力
- 下一轮建议从 `workflow -> pipeline` 编译器开始
