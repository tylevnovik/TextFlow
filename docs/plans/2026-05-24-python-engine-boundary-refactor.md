# Python Engine Boundary Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 继续收紧 `services/python-engine/app` 的模块边界，把领域默认值、项目存储、实验执行和报告输出从大文件中拆出，并保持现有 action、manifest、workflow 行为不变。

**Architecture:** 本轮采用低风险的“先搬职责、后改行为”策略。新模块只承接已有函数，调用方逐步改到职责更清晰的位置；旧聚合模块只保留向后兼容导出，避免一次性改动所有测试和业务入口。

**Tech Stack:** Python 3.11+, pytest, npm engine test scripts, SQLite project store, TextFlow native DAG workflow runtime.

---

## 本轮范围

- [ ] 拆分 `domain/defaults.py`：把词表、导入模板、workflow graph、runtime profile、result bundle、project manifest 的职责迁到独立 domain 模块。
- [ ] 移除 `domain -> workflow -> domain` 的循环依赖：runtime profile compiler 直接依赖 domain 子模块，不再经 `defaults.py` 回跳。
- [ ] 瘦身 `storage/projects.py`：将 workspace 路径/状态、词表序列化、模板管理、项目包导入导出拆到独立 storage 模块。
- [ ] 将 `storage/experiments.py` 中的执行矩阵逻辑迁到 workflow/application 侧，storage 只保留实验规格读写。
- [ ] 拆分 `reporting/core.py` 的报告职责：将 run 参数快照从 workflow runtime 传入 reporting，避免 reporting 反向认识 runtime。
- [ ] 更新文档并统一运行 engine 测试。

## 非目标

- [ ] 不改 workflow 节点行为和执行顺序。
- [ ] 不改项目文件格式和已有数据库 schema。
- [ ] 不改前端 API action 名称、payload 或响应结构。
- [ ] 不做 UI 调整，不跑浏览器 smoke。

## 目标文件结构

- Create: `services/python-engine/app/domain/common.py`
  - 时间戳、JSON 序列化等无业务依赖的通用 domain helper。
- Create/expand: `services/python-engine/app/domain/dictionary.py`
  - 词表 kind、collection/table/entry 默认构造和 sheet 合并。
- Create: `services/python-engine/app/domain/import_profiles.py`
  - source profile 导入模板。
- Create/expand: `services/python-engine/app/domain/workflow.py`
  - workflow payload hash、port compatibility、edge normalization、默认 workflow graph。
- Create/expand: `services/python-engine/app/domain/results.py`
  - result bundle 默认键和 normalize helper。
- Create/expand: `services/python-engine/app/domain/project.py`
  - project manifest 默认结构。
- Modify: `services/python-engine/app/domain/defaults.py`
  - 改为兼容聚合导出，不再承载实现。
- Create: `services/python-engine/app/storage/workspace.py`
  - workspace root、projects/data/templates root、workspace state。
- Create: `services/python-engine/app/storage/dictionaries.py`
  - 词表 manifest/database storage 序列化与可编辑表定位。
- Create: `services/python-engine/app/storage/templates.py`
  - project/import template 通用读写。
- Create: `services/python-engine/app/storage/packages.py`
  - `.tfproj` 打包、导入、复制。
- Modify: `services/python-engine/app/storage/projects.py`
  - 保留项目 CRUD、manifest normalize、workspace snapshot，并从新模块导入职责函数。
- Create: `services/python-engine/app/workflow/experiments.py`
  - 实验矩阵执行。
- Modify: `services/python-engine/app/storage/experiments.py`
  - 只保留 experiment spec normalize/save/list。
- Modify: `services/python-engine/app/reporting/core.py`
  - 保留 HTML、chart、table/run output helper；`write_run_outputs()` 改为由 workflow runtime 传入参数快照，移除对 workflow runtime support 的 import。

## 验收标准

- [ ] `rg "from \\.\\.workflow|from \\.\\.workflow\\.runtime" services/python-engine/app/domain services/python-engine/app/reporting` 没有 domain/reporting 反向依赖 workflow runtime 的结果。
- [ ] `storage/experiments.py` 不再导入 `workflow.runner`。
- [ ] `domain/defaults.py` 只做兼容导出；核心实现函数位于 `domain/*` 子模块。
- [ ] `storage/projects.py` 文件长度明显下降，workspace path、template、package、dictionary serialization 不再直接实现于该文件。
- [ ] 现有内部 import 全部解析成功：`python -m pytest services/python-engine/tests/test_port_compatibility.py services/python-engine/tests/test_node_catalog_parity.py -q` 通过。
- [ ] 快速引擎测试通过：`npm run test:engine:fast`。
- [ ] 因本轮触及 samples/bootstrap 间接依赖和项目导入导出链路，完整引擎测试通过：`npm run test:engine:full`。
- [ ] `git diff --check` 无空白错误。

## 执行步骤

### Task 1: 拆 domain 基础模块

- [ ] 创建 `domain/common.py`，迁入 `utc_now_iso()` 与 `json_ready()`。
- [ ] 扩展 `domain/dictionary.py`，迁入词表常量、entry/table/collection builder、默认词表 seed。
- [ ] 创建 `domain/import_profiles.py`，迁入 `profile_import_template()` 与 `default_import_template()`。
- [ ] 扩展 `domain/results.py`，迁入 `empty_result_bundle()`。
- [ ] 扩展 `domain/workflow.py`，迁入 workflow hash、默认 workflow graph、edge/port helper。
- [ ] 扩展 `domain/project.py`，迁入 `default_project_manifest()`。
- [ ] 将 `domain/defaults.py` 改为从上述模块聚合导出。

### Task 2: 修正 runtime profile compiler 依赖方向

- [ ] 修改 `workflow/runtime_profile_compiler.py`，直接从 `domain.runtime_profile`、`domain.workflow` 导入。
- [ ] 修改 `workflow/runtime/support.py`，不再通过 `domain.defaults` 获取 compiler。
- [ ] 跑 focused import/port 测试，确认循环依赖解除。

### Task 3: 拆 storage 项目相关职责

- [ ] 创建 `storage/workspace.py`，迁出 workspace root/state 函数。
- [ ] 创建 `storage/templates.py`，迁出 template path/list/load/save。
- [ ] 创建 `storage/dictionaries.py`，迁出词表 normalize/serialize/load helpers。
- [ ] 创建 `storage/packages.py`，迁出 project package export/import/duplicate 相关 helpers。
- [ ] 更新 `storage/projects.py` 调用新模块，并保留旧函数名的 re-export 以降低调用方改动。

### Task 4: 迁移实验执行

- [ ] 创建 `workflow/experiments.py`，迁入 `run_experiment_matrix()` 及 workflow variant helpers。
- [ ] 从 `storage/experiments.py` 删除 workflow runner 依赖。
- [ ] 更新 `api/actions/experiments.py` 的 import。

### Task 5: 拆 reporting run output

- [ ] 修改 `reporting/core.py`，让 `write_run_outputs()` 接收 `params_snapshot`，不再 import workflow runtime support。
- [ ] 或将 `write_run_outputs()` 搬到 `reporting/run_outputs.py`，由 runtime 传入 `build_run_params_snapshot()` 的结果。
- [ ] 更新 `workflow/runtime/native.py` 调用。

### Task 6: 文档与验证

- [ ] 更新 `docs/architecture.md` 或 `docs/technical-overview.md` 的模块边界说明。
- [ ] 运行 `git diff --check`。
- [ ] 运行 focused pytest。
- [ ] 运行 `npm run test:engine:fast`。
- [ ] 运行 `npm run test:engine:full`。

## 执行结果（2026-05-24）

- [x] 已创建中文计划和验收标准。
- [x] 已拆分 `domain/defaults.py`，当前该文件仅保留兼容聚合导出。
- [x] 已创建 `domain/common.py`、`domain/import_profiles.py`、`domain/runtime_profile.py`，并扩展 `domain/dictionary.py`、`domain/workflow.py`、`domain/results.py`、`domain/project.py`。
- [x] 已将 workflow runtime profile compiler 的 domain 依赖改为直接依赖 domain 子模块。
- [x] 已创建 `storage/constants.py`、`storage/io.py`、`storage/workspace.py`、`storage/templates.py`、`storage/dictionaries.py`、`storage/packages.py`。
- [x] 已将 `storage/projects.py` 从约 1643 行降到约 789 行。
- [x] 已将实验矩阵执行迁到 `workflow/experiments.py`，`storage/experiments.py` 不再导入 workflow runner。
- [x] 已让 `reporting/core.py` 不再导入 workflow runtime support。
- [x] 已更新 `docs/architecture.md` 的模块边界说明。
- [x] `git diff --check` 通过；PowerShell 输出了既有 CRLF 转换 warning，但没有 whitespace error。
- [x] Focused pytest 通过：`25 passed`。
- [x] `npm run test:engine:fast` 通过：`147 passed, 10 deselected, 3 warnings`。
- [x] `npm run test:engine:full` 通过：`157 passed, 3 warnings`。
