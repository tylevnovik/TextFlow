# 示例项目说明

当前仓库会在首次打开空工作区时自动生成 3 个可直接体验的示例项目。它们的目标不是做“预渲染 demo”，而是让用户马上看到真实项目结构、真实语料、真实词表和真实 workflow。

## 生成规则

- 触发条件：第一次加载空工作区
- 生成位置：用户工作区的 `projects/`
- 默认当前项目：`示例项目 - 学术摘要机构主题`
- 运行状态：创建时不预跑分析，`run_history` 为空
- 源数据位置：每个示例项目都会在 `metadata/sample_seed/` 下写入种子 CSV

## 示例一：示例项目 - 学术摘要机构主题

- 数据来源：OpenAlex 小样本
- 许可：`CC0 / No Rights Reserved`
- 参考入口：[OpenAlex API](https://api.openalex.org/)
- 主要用途：看机构关键词、机构主题、年份关系和报告导出
- 默认工作流特点：
  - 保留特征词、关键词聚类、机构关键词、机构主题
  - 输出 `XLSX / PNG / HTML`

## 示例二：示例项目 - 新闻组主题聚类

- 数据来源：20 Newsgroups 小样本
- 许可：`CC BY 4.0`
- 参考入口：[UCI Twenty Newsgroups](https://archive.ics.uci.edu/dataset/113/twenty+newsgroups)
- 主要用途：看多主题文本的关键词聚类和文档聚类
- 默认工作流特点：
  - 保留特征词、关键词聚类、文档聚类
  - 输出 `CSV / PNG / HTML`

## 示例三：示例项目 - 短信词频与共现

- 数据来源：SMS Spam Collection 小样本
- 许可：公开研究语料汇编
- 参考入口：[UCI SMS Spam Collection](https://archive.ics.uci.edu/dataset/228/sms+spam+collection)
- 主要用途：快速理解短文本词频、共现和轻量报告流程
- 默认工作流特点：
  - 保留词频、共现、关键词
  - 输出 `CSV / PNG / HTML`

## 示例项目有什么价值

- 帮助新用户快速理解 `.tfproj` 项目里会保存什么
- 让用户在没有自有数据时也能跑通导入后链路
- 帮助开发者验证 workflow、词表、导出和报告是否还能跑通

## 当前边界

- 示例项目不是 benchmark 数据，也不是完整行业案例，只是小样本体验项目。
- 它们不会自动生成结果，第一次结果需要用户手动运行。
- 已有用户项目的工作区不会重复注入示例项目。
