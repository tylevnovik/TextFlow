# V2 Workflow Inspect Preview Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为当前 workflow 画布补上节点预览与连线 Inspect，让用户不止能改参数，还能看到数据流和最近一次运行快照。

**Architecture:** 不改 Python 运行时，也不新增节点 artifact registry。本阶段只在桌面端基于当前项目快照、最近运行记录和现有 `results` 构建轻量 preview / inspect 视图；节点与边都可以被选中，右侧 inspector 根据选中对象切换内容。

**Tech Stack:** React + TypeScript, existing workflow canvas, desktop build verification

---

### Task 1: Add Inspect State

**Files:**
- Modify: `apps/desktop/src/screens.tsx`

**Step 1: Track selected edge**

要求：

- 节点点击选中节点
- 连线点击选中 edge
- inspector 根据当前 selection 切换

**Step 2: Keep drag safe**

要求：

- 节点拖拽不误触 edge inspect
- 连线仍保持可点击

### Task 2: Add Node Preview

**Files:**
- Modify: `apps/desktop/src/screens.tsx`

**Step 1: Build lightweight previews from current snapshot**

包括：

- 处理对象节点：文档数与样本文档
- 文本节点：原文 / 清洗 / 标准化片段
- 切词节点：tokens / phrase hits
- 分析节点：高频词、主题/关键词结果摘要
- 导出节点：报告文件与运行产物摘要

**Step 2: Label the boundary clearly**

要求：

- 明确写出“预览基于最近一次项目快照/运行结果”
- 不假装这是 draft 参数实时重算的结果

### Task 3: Add Edge Inspect

**Files:**
- Modify: `apps/desktop/src/screens.tsx`
- Modify: `apps/desktop/src/styles.css`

**Step 1: Make edges inspectable**

要求：

- 边可点击
- 选中边高亮
- 展示 from/to node、port label、port type

**Step 2: Add data summary by port type**

要求：

- 语料类端口显示文档规模
- 词表端口显示启用词条规模
- 分析端口显示结果摘要
- 导出端口显示报告文件数

### Task 4: Verify

**Files:**
- Build: `apps/desktop`
- Test: `services/python-engine/tests/test_workspace_cli.py`
- Test: `services/python-engine/tests/test_pipeline.py`

**Step 1: Run desktop build**

Run:

- `npm run build --workspace apps/desktop`

**Step 2: Run backend regression**

Run:

- `.\services\python-engine\.venv\Scripts\python.exe -m pytest services/python-engine/tests/test_workspace_cli.py -q`
- `.\services\python-engine\.venv\Scripts\python.exe -m pytest services/python-engine/tests/test_pipeline.py -q`
