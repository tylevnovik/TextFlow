# 大规模压测记录

本文档记录当前 workflow-only native DAG 主链的压测入口和最近一次结果。

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
- artifact store：启用，summary 会记录 `artifact_store_enabled` 和 `artifact_record_count`
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

## 最近一次记录

命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-large-benchmark.ps1 --limit 1200
```

结果：

- 导入耗时：`0.04s`
- 运行耗时：`14.068s`
- 总耗时：`18.067s`
- 处理文档数：`1200`
- 运行状态：`completed`
- 产物数：`8`
- artifact record 数：由 `manifest.artifact_records` 统计，需与 run artifact handle 数保持同向增长
- 报告文件数：`11`

核心结果规模：

- `frequency_rows`: `23279`
- `cooccurrence_rows`: `88435`
- `feature_term_rows`: `23279`
- `selected_feature_terms`: `1000`
- `keyword_rows`: `9611`
- `keyword_cluster_rows`: `1000`
- `document_cluster_rows`: `1200`

## 当前性能热点

当前最大的热点主要集中在：

- 关键词提取
- 大规模 CSV / PNG / HTML 导出
- 超大项目在当前项目装载时对词表与结果快照的水合
- `corpus_snapshot.json` 等大文件写盘

## 已完成的关键优化

- workflow 运行时统一切到 native DAG，不再在 bridge 与 DAG 之间来回切换
- 项目持久化切到 workflow-only，避免保存阶段重复写独立流程快照
- 节点缓存使用二进制 `.pkl`，降低大量 JSON 序列化开销
- 去掉节点间大语料 `deepcopy`
- 词表应用改成运行时查表结构
- 正则规则、短语规则和分词词典注入改成运行时缓存
- 中等规模语料上的 `YAKE` 关键词提取改为多进程并行
- 审计表只记录真实命中规则
- 大语料聚类图改成簇级标注，降低 PNG 导出成本
- 保存阶段增加已归一化快路径，减少重复 manifest 归一化与深拷贝
- 项目保存支持按脏区写盘，并对 unchanged JSON 跳过重复落盘
- `workflow_run` 进度支持 `node_state_delta` 增量回传，降低高频轮询负担
- `corpus_snapshot.json` 改成轻量快照策略，大语料默认不再全量塞入原文
- 聚类分析切到 `MiniBatchKMeans` + 稀疏矩阵降维路径，减少大矩阵 `toarray()` 开销
- benchmark summary 现在显式记录 artifact store 是否启用和项目级 artifact record 数，防止压测绕开产物索引链路
- 共现统计改成整数 term-id 计数路径，降低大语料字符串哈希负担
- 首次空工作区冷启动中，示例项目生成已跳过重复的大词表全量归一化，冷启动基准从约 `24.9s` 降到约 `5-7s`
- 给长时间节点和导出阶段补了中途进度回传

## 当前结论

当前 benchmark 说明：

- native DAG 主链已经稳定可用
- workflow-only 持久化没有带来明显性能回退
- 当前瓶颈已经从“运行框架切换成本”转向“关键词提取 + 导出 I/O + 当前项目水合”

下一阶段最值得继续优化的是：

- 更细粒度的 ready-queue 并行调度
- 大语料导出阶段写盘
- 关键词提取与主题分析热点
- 局部重跑与更细粒度的 artifact 管理
