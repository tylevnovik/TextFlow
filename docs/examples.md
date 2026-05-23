# 内置场景样例

TextFlow 首次打开空工作区时，会优先从安装包里的预构建样例工作区恢复 3 个官方样例项目。样例不是前端 demo，而是由 Python sidecar 预先导入 seed、写入 `.tfproj/project.db`、保存 workflow 和词表后的真实项目。

## 当前内置样例

| 样例 | Source profile | 主要覆盖 | 预期先看 |
| --- | --- | --- | --- |
| 示例 01 - WoS论文关键词与主题流程 | `wos` | WoS 字段映射、主文本拼接、元数据标准化、去重、清洗、切词、词表、特征词、关键词、主题、年份趋势、关键词白名单后的共现网络、导出 | 聚焦词项、工作流节点上的产物按钮 |
| 示例 02 - IncoPat专利技术识别与图分析 | `incopat` | 专利元数据标准化、claims 文本、关键词收窄、共现网络、图指标、社区、主路径、链接预测、技术指标和技术分类 | 聚焦词项摘要、技术指标、图分析和 HTML 报告产物 |
| 示例 03 - 论文专利融合分析流程 | `wos + incopat` | 多来源合并、source profile 保留、机构关键词/主题、跨来源统计、关键词白名单后的融合图谱与技术输出 | 多来源节点、机构分析、聚焦图谱和导出节点产物 |

这些样例的工作流目标不是“把所有节点串起来演示一遍”，而是先回答一个具体分析问题，再把相关节点放进可审计链路。每个样例的项目描述都会直接写清楚目标、处理流程和预期结果。复杂图计算默认不吃全量词项，而是经过语料范围控制、去重、词表规则、词频过滤、项目级关键词抽取和 `聚焦词项` 白名单后，再进入共现、构图和图算法节点。

Scopus 已有 import profile 和测试夹具，但当前没有内置 Scopus 样例。等拿到可再分发的 Scopus seed 后再加入新的官方样例。

## Seed 与授权

WoS、Scopus 和 IncoPat 导出通常受订阅协议限制，默认只能作为本地开发 seed。构建样例时使用这些环境变量：

```powershell
$env:TEXTFLOW_SAMPLE_WOS_SOURCE = "C:\path\to\wos.xls"
$env:TEXTFLOW_SAMPLE_INCOPAT_SOURCE = "C:\path\to\incopat.xlsx"
$env:TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA = "1"
```

也可以通过脚本参数传入：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-bundled-sample-workspace.ps1 `
  -WosSeed "C:\path\to\wos.xls" `
  -IncopatSeed "C:\path\to\incopat.xlsx" `
  -AllowRestrictedSampleData `
  -RowLimit 120
```

`sample_seed_sources/private/` 已被 git 忽略，适合放本地 seed。公开发布构建不应使用 `-AllowRestrictedSampleData`，除非 seed 元数据已经明确标记为可再分发。

## 存储形态

- 样例 `.tfproj` 内包含 `project.json` 和 `project.db`。
- 语料行写入 `project.db` 的 `corpus_documents` 表。
- 运行产物写入 `project.db` 的 `artifacts` 表，并通过 `artifact_records` 暴露懒加载索引。
- 打包样例不保留 `corpus/imported/*` 或 `metadata/sample_seed/*` 原始 seed 文件。
- `source_files` 只保留审计元数据；`relative_path` 为空，`retained_in_project=false`。

## 使用提醒

- 样例创建时不预跑分析；用户需要手动运行 workflow。
- 运行完成后，在工作流页面已完成且有产物的节点上点击“产物”按钮查看预览。
- 开发测试可通过 `TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT` 或脚本 `-RowLimit` 缩小样例规模；当前不再要求偶数或英中配比。
