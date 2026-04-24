# 内置场景样例

TextFlow 在首次打开空工作区时，会由 Python sidecar 自动创建 9 个官方场景样例项目。它们不是前端伪造 demo，而是基于真实公开数据、真实项目结构、真实词表和真实 workflow 生成的后端样例。

## 为什么官方样例做得比较大

- 这些样例要覆盖从清洗、标准化、切词到导出、复核、门禁的完整链路，过小语料会让很多节点只剩“能点一下”的演示价值。
- 官方样例默认至少包含 `10,000` 条公开来源文档；`示例 01` 默认是 `20,000` 条，其余 8 个样例默认是 `10,000` 条。
- 所有官方样例都保持严格 `1:1` 的英中行数配比，方便直接比较双语数据的分布和结果差异。
- 开发或测试时可以通过 `TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT` 降低样例规模，但该值必须是偶数，系统会继续保持英中 `1:1`。

## 公开数据如何进入样例项目

1. `services/python-engine/app/sample_dataset_sources.py` 维护公开数据源注册表，记录每个数据集的主页、下载入口、许可证、公开使用说明和再分发备注。
2. 官方样例使用归一化后的公开数据缓存：默认位于 `services/python-engine/app/public_sample_cache/`，也可以通过 `TEXTFLOW_PUBLIC_SAMPLE_CACHE_ROOT` 指向外部缓存目录。
3. `services/python-engine/app/sample_dataset_cache.py` 从缓存中读取归一化行，按样例里声明的来源比例分配英中配额，再交错写入项目语料，确保总量和语言平衡都符合要求。
4. `scripts/fetch-public-sample-data.ps1 -All` 会在缓存缺失或版本过旧时，从官方 Wikimedia / UN / OpenAlex 入口抓取真实公开行并重建 `manifest.json`；`scripts/build-python-sidecar.ps1` 会把这份离线缓存一并打进 sidecar。
5. `normalize_public_sample_row(...)` 会把 `language`、`source_dataset_id`、`source_url`、`source_license` 和可用的 `source_record_id` 写进规范化语料，样例项目再把这些归因信息保留下来。

## `language` 字段从哪里来

- 官方样例不会在 UI 侧做模糊语言识别。
- 每条样例语料的 `language` 由样例来源声明的语言决定，并在归一化时校验该语言是否受对应公开数据集支持。
- 如果上游公开数据本身带有来源记录 ID、来源 URL 或其他元数据，这些字段会一起保留到 `extra_metadata`，方便审计和回溯。

## 九个官方样例

| 样例 | 默认总行数 | 默认英/中拆分 | 真实公开数据集 | 这个样例主要教什么 | 建议先打开 | 预期运行级别 |
| --- | --- | --- | --- | --- | --- | --- |
| 示例 01 - 基础文本预处理 | 20,000 | `10,000 en + 10,000 zh` | Wikimedia English Wikipedia + Chinese Wikipedia | 清洗、标准化、切词、审计表和基础导出 | `HTML` 报告 | 低 |
| 示例 02 - 词表治理与词频统计 | 10,000 | `5,000 en + 5,000 zh` | United Nations Parallel Corpus v1.0 | 术语保留、同义词统一、噪声过滤、词频与词项-文档关系 | `XLSX` 词频结果 | 低 |
| 示例 03 - 学术摘要关键词与主题 | 10,000 | `5,000 en + 5,000 zh` | OpenAlex Works | 关键词提取、主题建模、年份趋势、文档聚类 | `HTML` 报告 | 中 |
| 示例 04 - 机构主题与技术方向 | 10,000 | `5,000 en + 5,000 zh` | OpenAlex Works | 机构关键词、机构主题、年份切片和双语机构比较 | `XLSX` 机构主题结果 | 中 |
| 示例 05 - 复核实验与增量运行 | 10,000 | `5,000 en + 5,000 zh` | United Nations Parallel Corpus v1.0 | 规则复核、实验矩阵、增量运行和对比 | `HTML` 报告，然后看 Review Queue / Experiment Matrix | 高 |
| 示例 06 - 多来源语料合并与抽样 | 10,000 | `5,000 en`=`2,500 Wiki + 2,500 OpenAlex`；`5,000 zh`=`2,500 Wiki + 2,500 OpenAlex` | Wikimedia English Wikipedia + Chinese Wikipedia + OpenAlex Works | 多格式 seed、来源过滤、去重、抽样和合并 | `HTML` 报告 | 中 |
| 示例 07 - 分组比较与关键性分析 | 10,000 | `5,000 en + 5,000 zh` | OpenAlex Works | 按组比较高频词、关键性分析、时间分桶 | `CSV` 分组比较结果 | 高 |
| 示例 08 - 切分评估与结果拼接 | 10,000 | `5,000 en + 5,000 zh` | Wikimedia English Wikipedia + Chinese Wikipedia | 训练/测试切分、聚类评估、结果拼接 | `XLSX` 拼接结果表 | 高 |
| 示例 09 - 条件路由与人工门禁 | 10,000 | `5,000 en`=`2,500 UN + 2,500 OpenAlex`；`5,000 zh`=`2,500 UN + 2,500 OpenAlex` | United Nations Parallel Corpus v1.0 + OpenAlex Works | 条件路由、指标门禁、人工复核入口 | `HTML` 报告，然后看 Review Queue | 高 |

## 使用提醒

- 官方样例文本来自真实公开数据，因此可能包含噪声、历史时期措辞、旧术语或带来源风格的表达；这属于样例的真实数据特征，不是前端渲染占位文本。
- `apps/desktop/src/data/demoProject.ts` 只是浏览器模式和组件测试时的轻量 fallback，不代表官方内置样例，也不应该镜像这些大规模公开语料。
