# TextFlow Studio Pipeline Spec

> 说明：本文档描述当前仓库已经落地的 V1 线性运行时，也是 V2 节点工作流在迁移期需要编译到的兼容执行目标。  
> V2 节点规格见 [docs/workflow-node-spec.md](./workflow-node-spec.md)，运行时适配见 [docs/node-runtime-spec.md](./node-runtime-spec.md)。

## V1 线性流程

```text
Ingestion
  -> Cleaning
  -> Normalization
  -> Tokenization
  -> Dictionary Application
  -> Filtering
  -> Analysis
  -> Export
```

## V2 迁移关系

V2 首期不会直接替换这条线性执行链，而是：

- 在前端引入节点工作流画布
- 在持久化层引入 `workflow_definitions`
- 在运行前把工作流图编译回本文定义的线性 `pipeline`

因此，本文仍是当前 Python sidecar 的执行基线。

## 运行意图层

V1 虽然仍按线性 pipeline 执行，但界面会在运行前显式确认 3 件事：

- `处理对象`：全部资料、筛选后的资料子集，或手动点选文档
- `处理配方`：围绕“快速清洗 / 标准分析 / 关键词与主题 / 汇报导出”等目标组织默认参数
- `输出包`：表格、图表、汇报或完整结果组合

运行记录必须写入所选范围摘要、实际处理文档数、配方标识和输出包摘要，保证一次 run 可以被复盘。

## 步骤要求

### Ingestion
- 支持 `txt/csv/xlsx/json`
- 统一输出核心字段
- 记录映射、空文本、重复文档与额外元数据
- 字段映射基于项目导入模板执行，而不是写死列名
- 导入源文件复制到项目 `corpus/imported/`，源文件记录写入 `source_files`
- 主文本支持多字段拼接、连接符配置和空值跳过

### Cleaning
- 去 HTML / URL / 空白归一
- 大小写、全半角、标点统一
- 记录命中摘要

### Normalization
- 正则规则、数字表达、时间表达占位
- 生成可追溯审计

### Tokenization
- 混合中英文分词
- 支持短语词典和领域短语保留
- 保留 token 原始顺序

### Dictionary Application
- 排除词、标准词、同义词、近义词、停用词
- 输出 token 审计表

### Filtering
- 长度过滤
- 数字词过滤
- 全项目低频过滤

### Analysis
- 词频统计
- 词文档关系
- 词年份关系
- 共现
- 特征词与关键词
  - 特征词默认基于 TF-IDF
  - 关键词默认基于轻量级 `YAKE`
- 关键词聚类
- 机构 × 关键词 / 主题
  - 机构主题默认基于 `scikit-learn NMF`
- 文档聚类

### Export
- CSV / XLSX / PNG / HTML
- 项目摘要、流程摘要、图表摘要、审计摘要
- PNG 图表默认支持高分辨率导出、可选水印与中文字体处理
- PNG 图表至少包括：高频词图、项目关键词图、关键词词云、机构主题热力图、文档聚类图
