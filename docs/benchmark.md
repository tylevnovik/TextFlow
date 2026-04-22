# 大规模压测记录

本文档记录仓库当前保留的万条级 workflow 压测入口和最近一轮结果，用于评估 native DAG 是否真的带来了性能收益。

## 压测入口

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-large-benchmark.ps1
```

可选参数：

- `--limit 2000`
  先做小规模调试。
- `--workspace-root C:\path\to\benchmark-workspace`
  把压测数据写到隔离工作区。

## 当前 benchmark 配置

- 数据集：`20 Newsgroups train`
- 默认规模：`11314` 条
- benchmark 脚本：`services/python-engine/benchmarks/large_workflow_benchmark.py`
- 默认工作流：

```text
corpus_input
  -> clean_text
  -> normalize_text
  -> tokenize
  -> apply_dictionary_rules
  -> filter_terms
  -> frequency_statistics
  -> cooccurrence_analysis
  -> feature_term_selection
  -> keyword_extraction
  -> keyword_clustering
  -> document_clustering
  -> save_csv / save_png / save_html_report
```

## 仓库当前记录的关键结果

下面这些数字来自仓库当前保留的 benchmark 记录，代表最近一轮已整理的阶段性结果：

- 旧 bridge 冷启动：`151.32s`
- native DAG 初版冷启动：`313.715s`
- native DAG 第一轮优化后冷启动：`153.548s`
- native DAG 第二轮优化后冷启动：`87.64s`
- native DAG 第二轮优化后二次重跑：`53.47s`
- 二次重跑缓存命中：`12/16` 节点

这说明两件事：

- native DAG 不是天然更快，初版甚至明显更慢
- 但经过结构性优化之后，native DAG 已经明显超过旧 bridge，并且二次运行收益更明显

## 当前性能热点

目前最大的热点已经不再是“DAG 框架本身”，而是：

- 大语料关键词提取
- `corpus_snapshot.json` 等大文件写盘
- 大型 CSV / PNG / HTML 产物导出

## 已经完成的关键优化

- 去掉节点间大语料 `deepcopy`
- 节点缓存从更重的 `gzip json` 迁移到普通 `json`
- 把 `TF-IDF` 与 `YAKE` 的部分联算拆开
- 词表应用改成运行时查表结构
- 审计表只记录真实命中规则
- 对超大语料的关键词提取切到更快路径
- 给长时间节点和导出阶段补了中途进度回传

## 为什么这份 benchmark 重要

这份 benchmark 的价值不是“证明我们有一张漂亮的性能表”，而是它验证了当前架构方向：

- 输出节点回溯活跃子图是有效的
- 节点缓存确实能让二次运行更快
- 运行热点已经可以定位到具体节点和具体 I/O 阶段

## 当前结论

当前 native DAG 已经值得继续推进，但下一阶段的收益点更偏向：

- 减少大型 run snapshot 的写盘成本
- 继续压缩关键词提取和导出阶段的热点
- 逐步把更多 bridge 逻辑迁到更明确的节点执行路径
