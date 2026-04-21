# V2 Workflow Canvas Layout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把当前 workflow shell 的中间区域升级为真正按节点坐标渲染的自由画布，并支持拖拽调整与布局持久化。

**Architecture:** 继续保持 `workflow -> pipeline -> existing runtime` 的执行链不变，只改前端 workflow 编辑体验。画布根据 `WorkflowDefinition.nodes[*].position` 绝对定位节点，拖拽后直接写回 `draftWorkflow`，保存项目时连同节点位置与 viewport 一起持久化。

**Tech Stack:** React + TypeScript, existing workflow helpers, desktop build verification

---

### Task 1: Add Layout Helpers

**Files:**
- Modify: `apps/desktop/src/workflow.ts`

**Step 1: Add default node layout helpers**

要求：

- 提供默认节点坐标
- 提供自动整理函数
- 提供节点位置更新函数

**Step 2: Keep it phase-safe**

要求：

- 不引入任意图布局算法
- 仍按当前单链 DAG 节点集布局
- 保留现有 workflow meta/config 编译逻辑

### Task 2: Upgrade The Canvas UI

**Files:**
- Modify: `apps/desktop/src/screens.tsx`
- Modify: `apps/desktop/src/styles.css`

**Step 1: Replace the static horizontal track**

要求：

- 中间区域改成自由画布
- 节点按 `position.x / position.y` 绝对定位
- 选中节点仍驱动右侧 Inspector

**Step 2: Add drag interaction**

要求：

- 鼠标按下即可拖拽节点
- 拖拽结束后位置保留在 draft workflow
- 不影响节点点击选中

**Step 3: Add layout controls**

要求：

- 自动整理布局
- 回到默认布局 / 聚焦布局
- 明确提示“保存后才会写回项目”

### Task 3: Verify

**Files:**
- Build: `apps/desktop`

**Step 1: Run desktop build**

Run:

- `npm run build --workspace apps/desktop`

**Step 2: Regression check**

确认：

- 现有参数编辑不受影响
- 保存/运行仍走当前 workflow compile 流程
- 中小窗口下仍能浏览画布与参数区
