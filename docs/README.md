# 文档索引

这套文档只描述当前仓库已经实现或已经被代码验证的能力，不再把历史方案、迁移草图和未来目标混写成“当前规格”。

## 当前有效文档

- [当前现状](./current-status.md)
  当前仓库能跑到什么程度、哪些部分稳定、哪些部分还在打磨。
- [产品范围与完成度](./product-scope.md)
  以 V1 目标为基线，逐项对照当前完成情况。
- [架构说明](./architecture.md)
  说明桌面端、Python sidecar、项目存储、词表、运行记录和打包结构。
- [工作流与运行时](./workflow-runtime.md)
  说明 workflow-only 持久化、native DAG、缓存和插件节点的当前关系。
- [开发与构建说明](./development.md)
  开发环境、脚本、测试、打包、压测入口。
- [示例项目说明](./sample-projects.md)
  首次启动从安装包内置模板恢复的 3 个官方 revised-flow 样例及用途。
- [大规模压测记录](./benchmark.md)
  当前仓库保留的万条级工作流压测数据与性能边界。
- [插件节点说明](../plugins/nodes/README.md)
  本地纯 Python 节点插件的加载方式、注册接口和当前运行边界。

## 目录约定

- `docs/` 根目录放当前有效文档。
- `docs/archive/` 放历史方案、旧规格和旧计划，仅供追溯，不再作为当前实现依据。
- `plugins/nodes/README.md` 放插件节点接口说明，因为它直接对应插件目录本身。

## 不再作为当前依据的文档

旧版 `PRD`、线性流程规格、V2 迁移规格、画布布局草图和实施计划已移入归档区：

- [归档说明](./archive/README.md)
