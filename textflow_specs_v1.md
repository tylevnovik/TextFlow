# 文本预处理与初步文本挖掘工作台（V1）规格草案

## 0. 已确认的产品决策

### 平台与交付
- **首发平台**：Windows
- **架构预留**：从 V1 开始保证可平滑扩展到 macOS
- **交付目标**：面向最终用户的安装包，安装后即可使用，不要求用户自行配置 Python / Node / Java 等环境

### 交互与产品边界
- **V1 不做**拖拽式流程编排
- **但必须预留扩展位**，保证 V2 引入节点式流程时不需要推翻现有数据模型与执行引擎
- **产品定位**：桌面优先的本地文本预处理、项目化管理与初步文本分析/文本挖掘工具

### 技术路线
- **桌面壳**：Tauri
- **前端**：React + TypeScript
- **核心处理引擎**：Python sidecar/service
- **状态管理**：前端独立状态层，后端任务化执行
- **目标**：V1 保持 UI 技术路线不变，避免未来从桌面 UI 迁移时重写前端

---

## 1. 产品目标（PRD 初稿）

### 1.1 产品名称（暂定）
- TextFlow Studio
- 或：文本工坊 / 语料工作台

### 1.2 产品定位
一个**面向研究、论文整理、舆情分析、内容分析与语料整理场景**的桌面工具，提供从原始文本导入、清洗、标准化、词表治理、项目化流程复用，到基础文本统计分析与文本挖掘结果导出的完整闭环。

### 1.3 目标用户
- 社科、人文、新闻传播、情报学、数字人文研究者
- 做舆情、评论、社媒文本整理的人
- 需要规范文本预处理流程但不想写代码的业务用户
- 需要可复跑、可复核、可导出结果的文本分析用户

### 1.4 核心价值
- **安装即用**：最终用户不用配置开发环境
- **流程标准化**：降低手工清洗与重复劳动
- **项目化组织**：数据、词表、流程、结果按项目保存
- **规则可审计**：知道每一步改了什么、为什么改
- **结果可复现**：同一项目可重复执行同一流程
- **可扩展**：未来可平滑加入可视化编排、插件、更多挖掘算法

---

## 2. 功能范围定义

## 2.1 V1 必须上线的能力

### A. 项目化管理
#### 目标
让用户以“项目”为单位组织数据、流程、词表与结果。

#### 功能
- 新建项目
- 打开最近项目
- 保存项目
- 另存为项目模板
- 项目复制
- 项目导出/备份
- 项目内保存：
  - 原始数据源
  - 元数据映射
  - 预处理参数
  - 词表集合
  - 运行历史
  - 输出结果
  - 报告与图表

#### 必要特性
- 项目文件结构稳定，以.tfproj作为后缀
- 项目可以完整迁移到另一台机器
- 同一项目可多次运行并保留 run history

---

### B. 数据导入与语料组织
#### 支持格式
- txt
- csv
- xlsx
- json

#### 能力
- 批量导入文件
- 从表格中导入一列或多列文本
- 字段映射
- 元数据模板映射与数据源选择：
  - 内置数据源类型：
    - 通用结构化数据（generic）
    - 文献数据（literature）
    - WoS（Web of Science）
    - 专利数据（patent）
    - IncoPat
    - 商业数据（business，预留）
  - 用户先选择数据源类型，再加载对应字段模板、字段别名与校验规则
  - 支持将当前映射保存为“项目模板”或“自定义导入模板”
  - 对未进入统一核心字段的源字段，不直接丢弃，而是保存在 `extra_metadata`
- 主文本字段配置：
  - 支持单字段作为 `raw_text`
  - 支持多字段拼接生成分析文本（如 `title + abstract`、`title + abstract + claims`）
  - 支持设置字段拼接顺序、连接符与空值处理规则
- 统一核心元数据字段（建议）：
  - `doc_id`
  - `source_type`
  - `title`
  - `raw_text`
  - `year`
  - `source`
  - `author`
  - `institution`
  - `country_or_region`
  - `category_or_tag`
  - `keyword_field`
  - `extra_metadata`
- WoS 模板建议字段：
  - UT
  - TI
  - AB
  - AU / AF
  - SO
  - PY
  - DE / ID
  - C1
  - WC / SC
  - DI
  - TC
- IncoPat 模板建议字段：
  - application_no
  - publication_no
  - title
  - abstract
  - applicant / assignee
  - inventor
  - IPC
  - CPC
  - priority_date
  - application_date
  - publication_date
  - legal_status
  - country_or_region
- 数据预览
- 编码识别与统一
- 缺失字段提示
- 重复文本检测与去重

#### 语料组织
- 项目内语料库列表
- 文档级预览
- 按年份/来源/类别筛选
- 搜索文本或元数据

---

### C. 文本预处理流程
#### 流程阶段
1. 原始文本导入
2. 文本清洗
3. 文本标准化
4. 分词/切词
5. 词表规则处理
6. 过滤
7. 生成中间结果
8. 进入分析与挖掘

#### 具体能力
##### 清洗
- 去空行
- 去 HTML 标签
- 去 URL
- 去邮箱/手机号（可选）
- 去表情或特殊字符（可选）
- 全半角转换
- 繁简转换（可选）
- 标点统一
- 大小写统一
- 多空格归一
- 去重文本

##### 标准化
- 同义词归并
- 近义词归并
- 标准词替换
- 数字归一规则
- 时间表达归一（可选）
- 特定模式替换（regex 规则）

##### 分词
- 中文分词
- 英文 tokenization
- 英文常见词组识别
- 领域词组识别与保留（如技术短语、机构名、产品名、方法名）
- 中英混合文本处理
- 支持短语级切分，不只限于单词级切分
- 支持连字符、斜杠、下划线、大小写连写（camelCase）等形式的切分规则
- 自定义词典参与切词
- 自定义短语词典参与切词
- 分词结果需同时支持：
  - token 序列
  - phrase 命中结果
  - 原始顺序保留
- 为后续共现分析、关键词筛选、关键词聚类提供稳定输入

##### 过滤
- 停用词过滤
- 排除词过滤
- 词长阈值
- 低频词过滤
- 数字词过滤（可选）
- 词性过滤（可选，占位）

#### 输出中间产物
- clean_text
- normalized_text
- tokens
- filtered_tokens
- term list

---

### D. 词表与规则中心
#### 词表类型
- 停用词表
- 自定义词典
- 同义词表
- 近义词表
- 标准词库
- 排除词表
- 正则规则表

#### 功能
- 新建/导入/导出词表
- 表格形式编辑
- 批量粘贴
- 去重与冲突提示
- 词表版本号
- 词表绑定到项目
- 词表模板复用
- 显示规则命中数量

#### 审计需求
- 每条规则要能追踪命中次数
- 原词 -> 替换后词 -> 规则来源 可回查

---

### E. 初步文本分析与文本挖掘（V1 必须纳入）
> 这一部分不是“高级功能”，而是产品闭环的一部分。

#### 1. 词频统计
- 高频词统计表
- 总词频 TF
- 文档频率 DF
- 占比
- 词长
- 首次出现年份
- 最后出现年份

#### 2. 词项分布分析
- 按年份的词频趋势
- 按来源/类别的词频分布
- 多词对比趋势
- 热词变化

#### 3. 词-文档关系分析
- 某词出现在哪些文档
- 某文档包含哪些关键词
- 词项覆盖文档数
- 代表文档检索

#### 4. 词-年份关系分析
- 某词逐年频次
- 某词逐年文档数
- 年份 x 词项透视表

#### 5. 共现分析（V1 建议纳入）
- 词项共现频次
- 共现矩阵
- 指定词的共现词列表
- 可选窗口大小设置

#### 6. 基础聚类
- 文档向量化
- 文档聚类
- 聚类结果统计
- 2D 可视化散点图
- 点击点查看文档详情

#### 7. 特征词筛选与关键词分析（基础版）
> 这一部分不应仅理解为“自动抽关键词”，而应作为后续聚类、按年分析、机构主题分析的共同入口。

##### 7.1 特征词候选生成
- 按文档抽取关键词
- 按项目聚合关键词
- 支持简单权重方法（如 TF-IDF 类思路）
- 支持生成项目级候选特征词表

##### 7.2 用户筛选特征词集合（必需交互环节）
- 用户可选择后续分析所使用的关键词范围
- 支持直接选择：
  - top 100
  - top 500
  - top 1000
  - top 5000
  - top 10000
  - 全部关键词
  - 自定义数量
- 支持手动增删关键词
- 支持保存“本项目特征词集”
- 若用户未手动选择，则默认使用全部候选关键词
- 一旦用户选择了特征词集，则后续这些分析全部以该集合为基础：
  - 关键词聚类
  - 按年关键词分析
  - 关键词共现
  - 机构 × 关键词共现
  - 机构 × 主题共现

##### 7.3 关键词基础分析
- 关键词频次统计
- 关键词按年分布
- 关键词按来源/类别分布
- 多关键词趋势对比

##### 7.4 关键词聚类
- 基于所选特征词集合进行聚类
- 输出关键词聚类结果表
- 输出关键词聚类图
- 支持查看每个类的代表词

##### 7.5 机构 × 关键词共现分析
- 输出机构 × 关键词共现列表
- 支持查看某机构的高频/高权重关键词
- 支持查看某关键词主要出现在哪些机构
- 支持按年份查看机构 × 关键词关系变化

##### 7.6 机构 × 主题共现分析
- 主题来自前面的关键词聚类结果
- 每个主题可由该类中“最靠近中心点的若干个词”作为代表词
- 输出机构 × 主题共现表
- 输出机构 × 主题共现图
- 支持查看：
  - 某机构的核心主题
  - 某主题的主要机构分布
  - 机构—主题关系的年度变化

##### 7.7 设计要求
- “特征词筛选”必须先于“关键词聚类”和“机构主题分析”
- 主题标签默认可由代表词自动生成，但应允许用户手动改名
- 后续若扩展高级主题模型，V1 的关键词主题结构应可平滑兼容

#### 8. 初步挖掘占位功能
以下功能 V1 可先做占位与接口，不要求完整交互：
- 主题分析模块占位
- 命名实体识别模块占位
- 分类模型接口占位
- 节点式分析流程占位

---

### F. 结果输出与报告
#### 导出类型
- CSV
- XLSX
- PNG
- HTML 报告

#### 必须支持导出的结果
- 高频词统计表
- 词-文档关系表
- 词-年份关系表
- 共现表/矩阵
- 特征词筛选结果表
- 关键词结果表
- 关键词聚类结果表
- 机构 × 关键词共现表
- 机构 × 主题共现表
- 聚类结果表
- 规则替换审计表
- 项目运行日志

#### HTML 报告内容
- 项目概览
- 数据规模
- 流程参数摘要
- 核心词频结果
- 趋势图
- 关键词聚类摘要
- 机构 × 关键词摘要
- 机构 × 主题摘要
- 聚类图
- 规则审计摘要

---

### G. 运行与任务管理
#### 功能
- 单次运行
- 分步运行
- 重跑某一步
- 运行进度显示
- 后台任务执行
- 错误提示
- 日志查看
- 中间产物缓存

#### 必要要求
- UI 不阻塞
- 长任务可取消
- 可查看本次运行使用的参数快照

---

## 2.2 V1 不做但要预留的内容
- 拖拽式节点流程编辑器
- 插件系统
- 云同步
- 多用户协作
- 高级主题模型交互
- 复杂分类与标注闭环

---

## 3. 信息架构

### 3.1 顶层导航
- 首页
- 项目
- 数据
- 流程
- 词表
- 分析
- 结果
- 报告
- 设置

### 3.2 页面定义
#### 首页
- 最近项目
- 新建项目
- 从模板创建
- 打开项目

#### 项目页
- 项目基本信息
- 语料规模
- 当前词表集
- 最近运行记录

#### 数据页
- 导入文件
- 数据源模板选择
- 字段映射
- 主文本构建配置
- 文档列表
- 文档预览
- 筛选与搜索

#### 流程页
- 清洗配置
- 标准化配置
- 分词配置
- 过滤配置
- 运行按钮
- 预处理结果预览

#### 词表页
- 多种词表切换
- 词表编辑
- 导入导出
- 命中统计

#### 分析页
- 词频
- 趋势
- 词-文档关系
- 词-年份关系
- 共现
- 文档聚类
- 特征词筛选
- 关键词分析
- 关键词聚类
- 机构 × 关键词
- 机构 × 主题

#### 结果页
- 表格结果
- 图表结果
- 导出
- 历史运行版本选择
- 特征词结果与机构主题结果浏览

#### 报告页
- 报告预览
- 生成 HTML 报告

#### 设置页
- 默认路径
- 语言
- 主题
- 更新
- 性能偏好

---

## 4. 自适应界面与多端适配策略

### 4.1 自适应要求
#### 宽屏桌面
- 左侧导航
- 中央内容区
- 右侧参数/预览面板

#### 中等窗口
- 参数面板折叠为抽屉
- 图表改为单列

#### 小窗口
- 改为分步式布局
- 底部/顶部标签切换
- 表格与图表垂直堆叠

### 4.2 多端适配策略
- V1 首发 Windows
- 架构与打包方式预留 macOS
- 导出 HTML 报告天然支持浏览器跨设备查看
- 不承诺 V1 原生移动端

---

## 5. 非功能要求

### 5.1 安装与发布
- Windows 安装包
- 首次安装后可直接运行
- 不需要用户手动安装依赖
- 可检查更新（占位）

### 5.2 性能
- 中小规模项目流畅可用
- 大任务后台运行
- 图表懒加载
- 支持增量缓存

### 5.3 稳定性
- 每一步失败都要有错误提示
- 项目文件不可轻易损坏
- 异常退出后尽量恢复最近状态

### 5.4 隐私
- 本地优先
- 默认不上传文本
- 可关闭联网检查更新

---

## 6. 技术架构草案

## 6.1 总体架构
- **桌面壳**：Tauri
- **前端 UI**：React + TypeScript
- **本地状态层**：前端 store + 本地缓存
- **核心执行层**：Python 引擎
- **通信方式**：Tauri command / sidecar IPC
- **本地存储**：项目目录 + SQLite / JSON 元数据

## 6.2 为什么选这条路线
- Tauri/Electron 方案可以保持未来 UI 技术栈一致
- React 更利于做自适应界面、数据表格、图表、复杂表单
- Python 核心适合文本处理、统计与基础挖掘
- V1 虽首发 Windows，但未来迁移到 macOS 代价更低

## 6.3 模块拆分
### 前端模块
- project manager
- data import UI
- source profile & metadata mapping UI
- pipeline config UI
- dictionary manager UI
- feature-term selection UI
- analysis dashboard
- result viewer
- report viewer

### 后端核心模块（Python）
- ingestion
- cleaning
- normalization
- tokenization
- dictionary application
- statistics
- cooccurrence
- clustering
- feature term selection
- keyword extraction
- institution-topic analysis
- export/report generation
- task runner

### 平台层
- installer/build scripts
- local file system adapter
- sidecar lifecycle manager

---

## 7. 数据模型与项目结构

## 7.1 核心实体
### Project
- id
- name
- description
- created_at
- updated_at
- version
- default_language
- paths

### CorpusItem
- id
- source_profile
- title
- year
- source
- author
- institution
- country_or_region
- category_or_tag
- keyword_field
- extra_metadata
- raw_text
- clean_text
- normalized_text
- tokens
- phrase_hits
- filtered_tokens
- status

### DictionarySet
- id
- name
- stopwords
- custom_lexicon
- phrase_lexicon
- synonym_map
- near_synonym_map
- standard_terms
- exclusion_terms
- regex_rules
- version

### PipelineDefinition
- id
- name
- enabled_steps
- parameters
- reserved_graph_schema

### RunRecord
- run_id
- project_id
- pipeline_version
- dictionary_version
- started_at
- ended_at
- status
- logs
- warnings
- errors

### ResultBundle
- frequency_table
- term_document_table
- term_year_table
- cooccurrence_table
- selected_feature_terms
- keyword_result
- keyword_cluster_result
- institution_keyword_cooccurrence
- institution_topic_cooccurrence
- clustering_result
- audit_table
- report_files

---

## 7.2 项目目录建议

```text
project-root/
  project.json
  corpus/
    imported/
    normalized/
  dictionaries/
    stopwords.csv
    custom_lexicon.csv
    phrase_lexicon.csv
    synonym_map.csv
    near_synonym_map.csv
    standard_terms.csv
    exclusion_terms.csv
    regex_rules.csv
  pipelines/
    default_pipeline.json
  runs/
    run_2026_...
      params_snapshot.json
      logs.txt
      outputs/
        selected_feature_terms.csv
        keyword_cluster_result.csv
        institution_keyword_cooccurrence.csv
        institution_topic_cooccurrence.csv
      charts/
      report/
  cache/
  exports/
```

### 7.3 关键设计要求
- 项目数据与结果必须解耦于程序安装目录
- 项目目录可整体拷贝迁移
- pipeline schema 必须预留 graph/nodes 字段，即便 V1 不启用拖拽

---

## 8. V2 占位设计（为了不大改）

### 8.1 流程编排预留
在 `PipelineDefinition` 中预留：
- nodes
- edges
- node_configs
- execution_order

V1 运行时仍按线性流程执行，但 schema 不要只写死成扁平参数表。

### 8.2 分析模块预留
分析模块统一走 `analysis plugins registry` 的接口思想，即便 V1 先内建。

### 8.3 报表与导出预留
所有分析输出统一包装为 ResultBundle，便于以后新增主题模型、实体识别等结果。

---

## 9. 仓库结构建议

```text
text-prep-workbench/
  AGENTS.md
  README.md
  docs/
    prd.md
    architecture.md
    pipeline-spec.md
    dictionary-spec.md
    packaging-spec.md
    ui-spec.md
  apps/
    desktop/
      src/
      src-tauri/
  services/
    python-engine/
      app/
      tests/
      pyproject.toml
  packages/
    shared-types/
    ui-components/
  samples/
  scripts/
```

---

## 10. AGENTS.md 草案

```md
# AGENTS.md

## Project
Build a desktop-first text preprocessing and basic text mining utility for end users.
The first shipping target is Windows, but the architecture must remain portable to macOS.
The product must be install-and-run and must not require users to configure Python, Node, or other dependencies manually.

## Product Priorities
1. Stable shipping quality over flashy features
2. Project-based organization of data, pipelines, dictionaries, and outputs
3. Reproducible preprocessing workflow
4. Rule auditability and run history
5. Responsive desktop UI
6. Future compatibility with node-based pipeline editor

## Mandatory V1 Features
- Project management
- Corpus import from txt/csv/xlsx/json
- Metadata mapping with source profiles
- Main-text construction from one or multiple fields
- Cleaning and normalization pipeline
- Tokenization with phrase preservation
- Dictionary center
- Stopword / synonym / standard term / exclusion handling
- Frequency statistics
- Term-document relations
- Term-year relations
- Co-occurrence analysis
- Basic clustering visualization
- Feature-term selection
- Keyword extraction
- Keyword clustering
- Institution-keyword and institution-topic analysis
- Export to CSV/XLSX/PNG/HTML
- Saved runs and logs

## Explicit Non-Goals for V1
- Node-based drag-and-drop pipeline UI
- Cloud sync
- Multi-user collaboration
- Native mobile apps

## Architecture Rules
- Desktop shell: Tauri
- Frontend: React + TypeScript
- Core analysis engine: Python sidecar/service
- Separate UI, domain types, and execution engine cleanly
- Do not hardcode all pipeline logic into UI components
- Do not couple project file format to transient UI state
- Reserve graph-based pipeline schema even if V1 executes linearly

## Code Quality Rules
- Prefer typed interfaces and clear domain models
- Every major module must include tests
- All new features must update docs
- Avoid hidden magic behavior; users must be able to inspect what rules were applied
- Long-running tasks must not block UI

## Packaging Rules
- Windows build must produce an installer
- Sidecar packaging must be reproducible
- Do not assume user-installed Python runtime
- Keep macOS portability in mind when selecting dependencies

## UX Rules
- Support medium and small desktop window sizes
- Use empty states and guided defaults
- Expose presets/templates where possible
- Make audit trails visible in the UI

## Deliverables
- Working desktop app skeleton
- Python engine skeleton
- Sample project
- Documentation
- Packaging scripts
- Automated tests for core logic
```

---

## 11. 给 Codex 的分阶段任务清单

## Phase 0：仓库初始化
### 目标
搭出可持续开发的 monorepo 骨架。

### 任务
- 初始化 Tauri + React + TypeScript desktop app
- 初始化 Python engine service
- 建立 shared types
- 建立 docs 目录与基础规范
- 写 README 与开发启动说明

---

## Phase 1：项目系统与数据导入
### 目标
实现项目创建、保存、加载和基础语料导入。

### 任务
- 实现 project schema
- 实现 project folder bootstrap
- 实现 txt/csv/xlsx/json 导入
- 实现数据源模板选择
- 实现字段映射 UI
- 实现主文本构建规则
- 实现文档列表与预览
- 实现去重逻辑
- 实现项目保存/打开

---

## Phase 2：预处理引擎
### 目标
实现线性 pipeline 的后端执行闭环。

### 任务
- cleaning module
- normalization module
- tokenization module
- phrase recognition support
- filtering module
- audit log generation
- run history persistence
- params snapshot

---

## Phase 3：词表中心
### 目标
实现规则治理与项目绑定。

### 任务
- 词表 CRUD
- 导入导出
- 同义词/标准词/排除词规则执行
- 冲突检测
- 命中统计
- 词表版本记录

---

## Phase 4：分析与挖掘
### 目标
做出 V1 的分析闭环。

### 任务
- 词频统计
- 词-文档关系
- 词-年份关系
- 共现分析
- 基础聚类
- 特征词筛选
- 关键词抽取
- 关键词聚类
- 机构 × 关键词分析
- 机构 × 主题分析
- 图表输出

---

## Phase 5：结果导出与报告
### 目标
让用户拿到可交付结果。

### 任务
- CSV/XLSX 导出
- PNG 图导出
- HTML 报告生成
- 运行日志导出
- 审计表导出

---

## Phase 6：桌面体验与发布
### 目标
完成 Windows 首发质量。

### 任务
- 自适应 UI 调整
- 大任务进度反馈
- 错误处理
- 安装包构建
- 首次启动引导
- 示例项目

---

## 12. 第一轮给 Codex 的总任务提示词

```md
You are building a desktop-first text preprocessing and basic text mining utility for end users.

Product decisions:
- First shipping platform: Windows
- Architecture must remain extensible to macOS
- Use Tauri + React + TypeScript for desktop UI
- Use a Python sidecar/service for text processing and analysis
- V1 does NOT include a drag-and-drop pipeline editor
- But the data model must reserve graph-based pipeline schema for V2

The application must support:
- Project-based organization of datasets, dictionaries, pipelines, runs, and outputs
- Importing txt/csv/xlsx/json corpora with source-profile-based metadata mapping
- Building analysis text from one or multiple source fields
- Cleaning, normalization, tokenization, phrase preservation, stopword filtering, synonym merging, standard term replacement, exclusion filtering
- Dictionary center for editable rule tables
- Basic text analysis and text mining including:
  - frequency statistics
  - term-document relations
  - term-year relations
  - co-occurrence analysis
  - basic clustering
  - feature-term selection
  - keyword extraction
  - keyword clustering
  - institution-keyword analysis
  - institution-topic analysis
- Export to CSV/XLSX/PNG/HTML
- Run history, logs, parameter snapshots, and audit tables
- Responsive desktop UI for different window sizes
- Windows installer packaging

Implementation rules:
- Separate UI, shared domain types, and Python engine
- Keep project data format stable and portable
- Do not require user-side environment setup
- Prioritize stable shipping architecture over flashy features
- Generate documentation and tests alongside code
```

---

## 13. 建议的下一步文档拆分
后续可以从这个总文档拆成独立文件：
- `docs/prd.md`
- `docs/architecture.md`
- `docs/pipeline-spec.md`
- `docs/dictionary-spec.md`
- `docs/ui-spec.md`
- `docs/packaging-spec.md`
- `AGENTS.md`

---

## 14. 下一步建议
建议下一轮继续细化以下 3 份最关键文档：
1. `pipeline-spec.md`：把每一步输入输出和参数都写细
2. `ui-spec.md`：把页面、布局、组件与交互流写细
3. `project-schema.md`：把项目文件格式和目录结构完全定死

---

# 附录 A：`project-schema.md` 草案

## A.1 设计目标
`project-schema.md` 用于定义项目级持久化格式，保证：
- 项目可以完整迁移
- 程序升级后尽量兼容旧项目
- UI 状态与项目数据分离
- 运行结果、日志、缓存、导出产物边界清晰
- 为 V2 节点式流程编辑器预留结构位

---

## A.2 项目级目录结构

```text
project-root/
  project.json
  manifest.json
  corpus/
    imported/
      corpus_index.json
      raw_000001.txt
      raw_000002.txt
    snapshots/
      import_snapshot_2026_01.json
  metadata/
    field_mapping.json
    corpus_table.parquet
  dictionaries/
    dictionaries.json
    stopwords.csv
    custom_lexicon.csv
    phrase_lexicon.csv
    synonym_map.csv
    near_synonym_map.csv
    standard_terms.csv
    exclusion_terms.csv
    regex_rules.csv
  pipelines/
    pipeline_default.json
    pipeline_templates/
      academic_basic.json
      social_media_basic.json
  runs/
    run_2026_04_16_001/
      run.json
      params_snapshot.json
      step_logs/
        01_ingestion.log
        02_cleaning.log
        03_normalization.log
        04_tokenization.log
        05_dictionary.log
        06_filtering.log
        07_analysis.log
        08_export.log
      intermediates/
        clean_text.parquet
        normalized_text.parquet
        tokens.parquet
        filtered_tokens.parquet
      outputs/
        frequency_table.csv
        term_document_table.csv
        term_year_table.csv
        cooccurrence_table.csv
        selected_feature_terms.csv
        keyword_result.csv
        keyword_cluster_result.csv
        institution_keyword_cooccurrence.csv
        institution_topic_cooccurrence.csv
        clustering_result.csv
        audit_table.csv
      charts/
        term_trend.png
        cluster_scatter.png
      report/
        report.html
        assets/
  cache/
    engine_cache.db
    vector_cache/
  exports/
    manual_exports/
  templates/
    project_template.json
  ui/
    workspace_state.json
```

---

## A.3 目录职责说明

### `project.json`
项目主配置文件，记录项目身份、版本、默认配置、当前绑定资源。

### `manifest.json`
项目内容清单，记录关键文件版本、哈希、最近运行摘要、兼容性信息。

### `corpus/`
保存原始导入文本及导入快照。

### `metadata/`
保存字段映射和结构化元数据表。

### `dictionaries/`
保存词表实体及其注册信息。

### `pipelines/`
保存线性 pipeline 配置，并预留 graph schema。

### `runs/`
保存每一次执行记录，保证 run 级可追溯、可审计、可复查。

### `cache/`
保存可丢弃缓存，不应作为唯一事实来源。

### `exports/`
保存用户手动导出的交付文件。

### `templates/`
保存项目模板快照。

### `ui/`
保存 UI 布局和最近使用状态，必须与项目业务数据分离。

---

## A.4 `project.json` 结构

```json
{
  "schema_version": "1.0.0",
  "project_id": "proj_7f2c1a",
  "name": "Weibo Hot Search Study",
  "description": "微博热搜标题文本预处理与初步挖掘项目",
  "created_at": "2026-04-16T10:00:00+08:00",
  "updated_at": "2026-04-16T11:20:00+08:00",
  "default_language": "zh-CN",
  "target_platform": "windows",
  "preferred_pipeline_id": "pipeline_default",
  "active_dictionary_set_id": "dict_default",
  "current_run_id": "run_2026_04_16_001",
  "paths": {
    "corpus_root": "corpus/",
    "metadata_root": "metadata/",
    "dictionary_root": "dictionaries/",
    "pipeline_root": "pipelines/",
    "runs_root": "runs/",
    "cache_root": "cache/",
    "exports_root": "exports/"
  },
  "stats": {
    "document_count": 12034,
    "last_successful_run": "run_2026_04_16_001"
  },
  "feature_flags": {
    "graph_pipeline_reserved": true,
    "topic_model_placeholder": true,
    "ner_placeholder": true
  }
}
```

### 设计要求
- `schema_version` 必须存在，用于升级兼容
- `paths` 必须是相对路径，避免项目迁移失效
- `feature_flags` 仅用于项目级能力标识，不允许直接替代正式配置

---

## A.5 `manifest.json` 结构

```json
{
  "project_id": "proj_7f2c1a",
  "schema_version": "1.0.0",
  "engine_compatibility": {
    "min_engine_version": "0.1.0",
    "tested_engine_version": "0.1.0"
  },
  "files": [
    {
      "path": "dictionaries/stopwords.csv",
      "type": "dictionary",
      "sha256": "...",
      "updated_at": "2026-04-16T10:50:00+08:00"
    }
  ],
  "recent_runs": [
    "run_2026_04_16_001"
  ]
}
```

### 作用
- 方便项目一致性校验
- 支持未来项目修复与迁移工具
- 为增量重跑提供依据

---

## A.6 `field_mapping.json` 结构

```json
{
  "import_batch_id": "import_2026_04_16_001",
  "source_type": "xlsx",
  "source_profile": "wos",
  "source_file": "wos_records.xlsx",
  "text_build_strategy": {
    "mode": "concat_fields",
    "fields": ["title", "abstract"],
    "separator": "\n",
    "ignore_empty": true
  },
  "mapping": {
    "doc_id": "UT",
    "title": "TI",
    "raw_text_title": "TI",
    "raw_text_abstract": "AB",
    "year": "PY",
    "source": "SO",
    "author": "AU",
    "institution": "C1",
    "keyword_field": "DE",
    "category_or_tag": "WC",
    "doi": "DI",
    "citation_count": "TC"
  },
  "required_fields": ["raw_text_title"],
  "recommended_fields": ["doc_id", "title", "year", "source", "author", "institution"],
  "extra_field_policy": "keep_in_extra_metadata"
}
```

### 规则
- 导入时必须先确定 `source_profile`，以决定默认字段模板与校验规则
- `raw_text` 不必必须来自单字段，可由多个字段拼接生成
- `doc_id` 若缺失可由系统生成，但必须在导入后固化
- 未进入统一核心字段的源字段应保留到 `extra_metadata`，避免信息损失

---

## A.7 `corpus_table.parquet` 的逻辑字段

结构化语料表建议使用 Parquet 存储，逻辑字段如下：

| 字段名 | 类型 | 说明 |
|---|---|---|
| doc_id | string | 项目内唯一文档 ID |
| source_profile | string | 数据源模板类型，如 generic / wos / incopat |
| title | string/null | 标题 |
| raw_text | string | 用于分析的主文本 |
| raw_text_title | string/null | 标题文本 |
| raw_text_abstract | string/null | 摘要文本 |
| raw_text_claims | string/null | 权利要求/正文等扩展文本 |
| year | int/null | 年份 |
| source | string/null | 来源 |
| author | string/null | 作者 |
| institution | string/null | 机构 / 申请人 / 单位 |
| country_or_region | string/null | 国家或地区 |
| category_or_tag | string/null | 类别 |
| keyword_field | string/null | 原始关键词字段 |
| extra_metadata | json/null | 未映射到统一字段的扩展元数据 |
| raw_hash | string | 原始文本哈希 |
| is_duplicate | bool | 是否重复 |
| import_batch_id | string | 导入批次 |
| created_at | datetime | 首次入库时间 |
| updated_at | datetime | 最近更新时间 |

### 约束
- `doc_id` 在项目范围内唯一
- `raw_hash` 用于去重与缓存命中
- `extra_metadata` 用于保留源系统特有字段
- 不允许在结构化元数据表中直接覆写分析中间产物

---

## A.8 `dictionaries.json` 结构

```json
{
  "schema_version": "1.0.0",
  "active_set_id": "dict_default",
  "sets": [
    {
      "id": "dict_default",
      "name": "默认词表集",
      "version": "1.0.0",
      "files": {
        "stopwords": "dictionaries/stopwords.csv",
        "custom_lexicon": "dictionaries/custom_lexicon.csv",
        "phrase_lexicon": "dictionaries/phrase_lexicon.csv",
        "synonym_map": "dictionaries/synonym_map.csv",
        "near_synonym_map": "dictionaries/near_synonym_map.csv",
        "standard_terms": "dictionaries/standard_terms.csv",
        "exclusion_terms": "dictionaries/exclusion_terms.csv",
        "regex_rules": "dictionaries/regex_rules.csv"
      },
      "stats": {
        "stopword_count": 2310,
        "synonym_rule_count": 120,
        "regex_rule_count": 6
      },
      "updated_at": "2026-04-16T10:52:00+08:00"
    }
  ]
}
```

### 规则
- 词表文件采用独立物理文件，注册信息由 `dictionaries.json` 管理
- 词表版本更新后，不应覆盖历史 run 的参数快照引用

---

## A.9 词表文件字段约定

### `stopwords.csv`
| term | enabled | note |
|---|---|---|

### `custom_lexicon.csv`
| term | weight | pos | enabled | note |
|---|---|---|---|---|

### `phrase_lexicon.csv`
| phrase | weight | category | enabled | note |
|---|---|---|---|---|

### `synonym_map.csv`
| source_term | target_term | priority | enabled | note |
|---|---|---|---|---|

### `near_synonym_map.csv`
| source_term | target_term | confidence | enabled | note |
|---|---|---|---|---|

### `standard_terms.csv`
| source_term | standard_term | domain | enabled | note |
|---|---|---|---|---|

### `exclusion_terms.csv`
| term | reason | enabled | note |
|---|---|---|---|

### `regex_rules.csv`
| rule_id | pattern | replacement | scope | priority | enabled | note |
|---|---|---|---|---|---|---|

---

## A.10 `pipeline_default.json` 结构

```json
{
  "schema_version": "1.0.0",
  "pipeline_id": "pipeline_default",
  "name": "Default Linear Pipeline",
  "mode": "linear",
  "version": "1.0.0",
  "enabled_steps": [
    "ingestion",
    "cleaning",
    "normalization",
    "tokenization",
    "dictionary_application",
    "filtering",
    "analysis",
    "export"
  ],
  "parameters": {
    "cleaning": {},
    "normalization": {},
    "tokenization": {},
    "dictionary_application": {},
    "filtering": {},
    "analysis": {},
    "export": {}
  },
  "graph": {
    "nodes": [],
    "edges": [],
    "node_configs": {},
    "execution_order": []
  },
  "created_at": "2026-04-16T10:10:00+08:00",
  "updated_at": "2026-04-16T10:10:00+08:00"
}
```

### 关键要求
- V1 `mode` 固定为 `linear`
- `graph` 必须存在，作为 V2 兼容位
- 每次运行必须引用一个明确的 pipeline version

---

## A.11 `run.json` 结构

```json
{
  "run_id": "run_2026_04_16_001",
  "project_id": "proj_7f2c1a",
  "status": "success",
  "started_at": "2026-04-16T11:00:00+08:00",
  "ended_at": "2026-04-16T11:06:30+08:00",
  "engine_version": "0.1.0",
  "pipeline_id": "pipeline_default",
  "pipeline_version": "1.0.0",
  "dictionary_set_id": "dict_default",
  "dictionary_version": "1.0.0",
  "input_snapshot": {
    "document_count": 12034,
    "import_batch_ids": ["import_2026_04_16_001"]
  },
  "steps": [
    {"name": "cleaning", "status": "success", "duration_ms": 1530},
    {"name": "normalization", "status": "success", "duration_ms": 990},
    {"name": "tokenization", "status": "success", "duration_ms": 8020}
  ],
  "outputs": {
    "frequency_table": "outputs/frequency_table.csv",
    "selected_feature_terms": "outputs/selected_feature_terms.csv",
    "keyword_cluster_result": "outputs/keyword_cluster_result.csv",
    "institution_keyword_cooccurrence": "outputs/institution_keyword_cooccurrence.csv",
    "institution_topic_cooccurrence": "outputs/institution_topic_cooccurrence.csv",
    "audit_table": "outputs/audit_table.csv",
    "report": "report/report.html"
  },
  "warnings": [],
  "errors": []
}
```

### 规则
- 每个 run 必须形成独立目录
- 历史 run 不可被原地覆写
- 允许失败 run 存在，但必须写明失败步骤

---

## A.12 `params_snapshot.json` 结构

此文件用于完全冻结本次运行使用的参数与资源引用。

```json
{
  "run_id": "run_2026_04_16_001",
  "pipeline": {
    "pipeline_id": "pipeline_default",
    "version": "1.0.0",
    "parameters": {
      "cleaning": {
        "strip_html": true,
        "normalize_whitespace": true
      }
    }
  },
  "dictionaries": {
    "set_id": "dict_default",
    "version": "1.0.0",
    "files": {
      "stopwords": "../../dictionaries/stopwords.csv"
    }
  },
  "analysis": {
    "frequency_enabled": true,
    "cooccurrence_window": 5,
    "selected_feature_term_count": 1000,
    "keyword_cluster_k": 20,
    "cluster_k": 8
  }
}
```

### 原则
- run 重现优先依赖 `params_snapshot.json`
- 即便项目后续改词表，旧 run 仍必须可解释

---

## A.13 `workspace_state.json` 结构

```json
{
  "last_opened_page": "analysis",
  "layout": {
    "sidebar_collapsed": false,
    "right_panel_width": 360,
    "table_density": "compact"
  },
  "recent_filters": {
    "year": [2022, 2023, 2024],
    "source": ["weibo"]
  }
}
```

### 规则
- 不允许把业务关键数据写入 UI 状态文件
- 删除 UI 状态文件不影响项目可用性

---

## A.14 版本与兼容策略

### 版本层级
- App version：程序版本
- Engine version：Python 引擎版本
- Schema version：项目格式版本
- Pipeline version：流程定义版本
- Dictionary version：词表集版本

### 兼容要求
- 小版本升级优先保证 schema 向后兼容
- 打开旧项目时应提供自动迁移或只读告警
- 迁移脚本必须可测试

---

## A.15 项目模板要求

项目模板建议至少冻结以下内容：
- pipeline 配置
- 默认词表集
- 字段映射规则
- 默认导出项
- 默认分析面板布局

### 模板文件建议
`templates/project_template.json`

---

## A.16 禁止事项
- 不得把安装目录当作项目存储目录
- 不得将缓存文件作为唯一结果来源
- 不得将 UI 临时状态和正式业务参数混存
- 不得在 run 之间共享会影响可复现性的隐式状态

---

# 附录 B：`pipeline-spec.md` 草案

## B.1 目标
`pipeline-spec.md` 用于定义 V1 线性文本预处理与初步文本挖掘流程，包括：
- 每一步的输入输出
- 可配置参数
- 中间产物
- 错误处理
- 审计记录
- 与分析模块的衔接方式

---

## B.2 V1 总体流程

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

### 说明
- V1 执行顺序固定为线性
- 各 step 可以单独启停
- 每一步都必须定义输入、输出、日志、错误模型
- 每一步都应支持结果缓存与重跑

---

## B.3 Step 01：Ingestion

### 目的
将用户导入的 txt/csv/xlsx/json 统一转为项目内部结构化语料。

### 输入
- 原始文件
- 字段映射配置
- 数据源类型选择
- 主文本构建规则
- 导入选项

### 输出
- `corpus/imported/*`
- `metadata/field_mapping.json`
- `metadata/corpus_table.parquet`
- 导入日志

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| source_type | enum | auto | txt/csv/xlsx/json |
| source_profile | enum | generic | generic/literature/wos/patent/incopat/business_reserved |
| text_fields | list[string] | ["raw_text"] | 主文本来源字段 |
| text_build_mode | enum | single_field | single_field / concat_fields |
| id_field | string/null | null | ID 字段 |
| detect_encoding | bool | true | 自动检测编码 |
| deduplicate_on_import | bool | true | 导入时去重 |
| trim_text | bool | true | 去首尾空格 |
| keep_extra_metadata | bool | true | 保留未映射字段 |

### 处理逻辑
1. 检查源文件是否存在
2. 识别文件类型与编码
3. 读取文本与元数据
4. 根据 `source_profile` 加载字段模板、字段别名与校验规则
5. 生成或校验 `doc_id`
6. 依据 `text_build_mode` 构建 `raw_text`
7. 计算 `raw_hash`
8. 依据配置执行去重标记
9. 将未映射字段写入 `extra_metadata`
10. 写入结构化语料表

### 审计记录
- 导入总文档数
- 有效文档数
- 空文本数
- 重复文档数
- 缺失字段数
- 模板自动识别/手动选择结果
- 主文本构建方式

### 错误类型
- 文件不可读
- 字段映射错误
- 全部文本为空
- 格式不兼容
- 关键文本字段缺失

---

## B.4 Step 02：Cleaning

### 目的
移除明显噪声并统一基础文本形态。

### 输入
- `metadata/corpus_table.parquet`
- 原始文本字段 `raw_text`

### 输出
- `intermediates/clean_text.parquet`
- cleaning 日志

### 输出字段
| 字段 | 说明 |
|---|---|
| doc_id | 文档 ID |
| raw_text | 原始文本 |
| clean_text | 清洗后文本 |
| cleaning_flags | 命中规则摘要 |

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| strip_html | bool | true | 去 HTML 标签 |
| strip_urls | bool | true | 去 URL |
| strip_email | bool | false | 去邮箱 |
| strip_phone | bool | false | 去手机号 |
| normalize_whitespace | bool | true | 空白归一 |
| normalize_punctuation | bool | true | 标点统一 |
| full_half_width_normalize | bool | true | 全半角统一 |
| lowercase_english | bool | true | 英文小写 |
| remove_emoji | bool | false | 移除 emoji |
| remove_special_chars | bool | false | 移除特殊符号 |

### 审计记录
- 各规则命中文档数
- 各规则替换字符数
- 清洗后为空文本的文档数

### 错误与告警
- 文本经清洗后为空时应发 warning，不直接中止整批

---

## B.5 Step 03：Normalization

### 目的
进行面向分析的文本标准化与模式归一。

### 输入
- `intermediates/clean_text.parquet`
- `regex_rules.csv`
- 可选语言设置

### 输出
- `intermediates/normalized_text.parquet`
- normalization 日志

### 输出字段
| 字段 | 说明 |
|---|---|
| doc_id | 文档 ID |
| clean_text | 清洗后文本 |
| normalized_text | 归一化文本 |
| normalization_audit | 归一化命中摘要 |

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| convert_traditional_to_simplified | bool | false | 繁转简 |
| normalize_numbers | bool | false | 数字归一 |
| normalize_time_expr | bool | false | 时间表达归一 |
| apply_regex_rules | bool | true | 启用 regex 规则 |
| regex_rule_priority | enum | rule_order | 冲突策略 |

### 审计记录
- 规则 ID
- 替换前片段
- 替换后片段
- 命中次数
- 影响文档数

### 错误与告警
- 正则表达式非法
- 替换后文本异常变短/为空

---

## B.6 Step 04：Tokenization

### 目的
把标准化文本转为后续分析可用的 token 序列。

### 输入
- `intermediates/normalized_text.parquet`
- `custom_lexicon.csv`
- 可选短语词典 / 领域词组表

### 输出
- `intermediates/tokens.parquet`
- tokenization 日志

### 输出字段
| 字段 | 说明 |
|---|---|
| doc_id | 文档 ID |
| normalized_text | 标准化文本 |
| tokens | token 列表 |
| phrase_hits | 命中的短语列表 |
| token_count | token 总数 |
| language_stats | 语言占比摘要，可选 |

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| language_mode | enum | auto | zh/en/mixed/auto |
| tokenizer_backend | enum | default | 分词后端占位 |
| use_custom_lexicon | bool | true | 使用自定义词典 |
| use_phrase_lexicon | bool | true | 使用短语词典 |
| preserve_domain_phrases | bool | true | 保留领域词组 |
| split_hyphenated_terms | bool | true | 处理连字符形式 |
| split_slash_terms | bool | false | 处理斜杠形式 |
| normalize_camel_case | bool | true | 处理英文连写 |
| keep_original_order | bool | true | 保留词序 |
| min_token_length_before_filter | int | 1 | 分词后的最短保留长度 |

### 设计要求
- token 序列必须保留原顺序，以支持共现分析
- 必须兼顾“单词级切分”和“短语级保留”
- 英文 tokenization 不应只停留在空格切分
- 中英混合文本应尽量减少错误拆分
- 应支持未来替换分词器实现，但输出 schema 不变

### 告警
- 某些文本分词结果为空
- 文档平均 token 数异常低
- 短语识别命中率异常低

---

## B.7 Step 05：Dictionary Application

### 目的
应用词表规则，把 token 序列映射到更适合统计分析的统一词项空间。

### 输入
- `intermediates/tokens.parquet`
- 停用词表、自定义词典、同义词表、近义词表、标准词库、排除词表

### 输出
- `intermediates/dictionary_applied.parquet`
- `outputs/audit_table.csv`（可先生成中间版）
- dictionary 日志

### 输出字段
| 字段 | 说明 |
|---|---|
| doc_id | 文档 ID |
| original_tokens | 原始 token 列表 |
| normalized_tokens | 词表处理后的 token 列表 |
| replacement_count | 替换次数 |
| dropped_count | 删除次数 |

### 规则优先级建议
1. exclusion_terms
2. standard_terms
3. synonym_map
4. near_synonym_map
5. stopwords

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| apply_standard_terms | bool | true | 启用标准词替换 |
| apply_synonym_map | bool | true | 启用同义词映射 |
| apply_near_synonym_map | bool | false | 启用近义词映射 |
| apply_stopwords | bool | true | 启用停用词 |
| apply_exclusion_terms | bool | true | 启用排除词 |
| conflict_resolution | enum | priority | 冲突处理方式 |

### 审计表字段建议
| 字段 | 说明 |
|---|---|
| doc_id | 文档 ID |
| position | 词位 |
| source_term | 原词 |
| target_term | 替换后词 |
| rule_type | 规则类型 |
| rule_source | 规则文件 |
| rule_key | 规则主键 |
| action | replace/drop/keep |

### 错误与告警
- 同一词被多条高优先级规则命中
- 规则形成循环替换
- 词表文件字段缺失

---

## B.8 Step 06：Filtering

### 目的
在词表应用后执行最终分析过滤，得到正式词项集合。

### 输入
- `intermediates/dictionary_applied.parquet`

### 输出
- `intermediates/filtered_tokens.parquet`
- filtering 日志

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| min_token_length | int | 2 | 最短词长 |
| filter_numeric_tokens | bool | false | 过滤纯数字词 |
| min_term_frequency | int | 1 | 全项目最低词频 |
| filter_by_pos | bool | false | 词性过滤占位 |
| keep_single_char_important_terms | bool | true | 保留白名单中的单字词 |

### 输出字段
| 字段 | 说明 |
|---|---|
| doc_id | 文档 ID |
| filtered_tokens | 最终词项列表 |
| final_token_count | 最终词项数量 |

### 审计记录
- 低频过滤剔除词数
- 数字过滤剔除词数
- 长度过滤剔除词数

---

## B.9 Step 07：Analysis

### 目的
基于最终词项集合，完成 V1 的基础文本分析与文本挖掘。

### 输入
- `intermediates/filtered_tokens.parquet`
- 元数据表 `metadata/corpus_table.parquet`

### 输出
- `outputs/frequency_table.csv`
- `outputs/term_document_table.csv`
- `outputs/term_year_table.csv`
- `outputs/cooccurrence_table.csv`
- `outputs/selected_feature_terms.csv`
- `outputs/keyword_result.csv`
- `outputs/keyword_cluster_result.csv`
- `outputs/institution_keyword_cooccurrence.csv`
- `outputs/institution_topic_cooccurrence.csv`
- `outputs/clustering_result.csv`
- 对应图表文件

---

## B.9.1 子模块：Frequency Statistics

### 输出字段建议
| 字段 | 说明 |
|---|---|
| term | 词项 |
| tf | 总词频 |
| df | 文档频率 |
| ratio | 占比 |
| first_year | 首次出现年份 |
| last_year | 最后出现年份 |
| avg_per_doc | 平均每文档出现次数 |

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| top_n | int | 200 | 默认展示前 N 个词 |
| group_by | enum | none | year/source/category |

---

## B.9.2 子模块：Term-Document Relations

### 输出字段建议
| 字段 | 说明 |
|---|---|
| term | 词项 |
| doc_id | 文档 ID |
| title | 文档标题 |
| year | 年份 |
| term_count_in_doc | 文档内词频 |
| source | 来源 |

### 功能要求
- 支持 term -> docs
- 支持 doc -> terms 反查视图

---

## B.9.3 子模块：Term-Year Relations

### 输出字段建议
| 字段 | 说明 |
|---|---|
| term | 词项 |
| year | 年份 |
| tf_in_year | 该年总词频 |
| df_in_year | 该年文档频率 |
| ratio_in_year | 该年占比 |

### 要求
- 缺失年份可跳过，但要在报告中说明
- 应支持多词对比趋势图

---

## B.9.4 子模块：Co-occurrence Analysis

### 目的
衡量词项在局部上下文中的共现关系。

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| window_size | int | 5 | 共现窗口 |
| symmetric | bool | true | 是否对称 |
| min_cooccurrence | int | 2 | 最小共现次数 |
| top_n_pairs | int | 500 | 输出对数 |

### 输出字段建议
| 字段 | 说明 |
|---|---|
| term_a | 词 A |
| term_b | 词 B |
| cooccurrence_count | 共现次数 |
| score | 权重分数占位 |

### 设计要求
- 初期至少实现滑动窗口共现统计
- 网络图交互可延后，但表格与基础图必须有

---

## B.9.5 子模块：Feature Term Selection & Keyword Analysis

### 目的
先生成候选特征词，再由用户确定分析词集，并以此作为关键词聚类、按年分析、机构 × 关键词、机构 × 主题分析的共同输入。

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| method | enum | tfidf_basic | V1 先做基础方法 |
| candidate_pool_size | int | 10000 | 候选特征词池大小 |
| selected_feature_term_count | int/string | all | 用户选择的特征词规模，如 1000/5000/10000/all |
| top_k_per_doc | int | 10 | 每文档关键词数 |
| top_k_project | int | 100 | 项目级关键词数 |
| enable_manual_term_selection | bool | true | 允许用户手动调整特征词集 |
| save_feature_term_set | bool | true | 保存项目级特征词集 |

### 输出字段建议：`selected_feature_terms.csv`
| 字段 | 说明 |
|---|---|
| term | 特征词 |
| score | 候选权重 |
| selected | 是否被选中 |
| source | auto/manual |
| rank | 排名 |

### 输出字段建议：`keyword_result.csv`
| 字段 | 说明 |
|---|---|
| scope | doc/project |
| doc_id | 文档 ID，可空 |
| keyword | 关键词 |
| score | 权重 |
| rank | 排名 |

### 设计要求
- “特征词筛选”是后续关键词分析的上游前置步骤
- 若用户未选择特征词数量，则默认使用全部候选关键词
- 一旦形成 `selected_feature_terms`，后续关键词聚类、年度分析、机构分析都应基于这一集合

## B.9.5.1 子模块：Keyword Clustering

### 目的
基于用户选定的特征词集合进行聚类，形成可解释的主题簇。

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| cluster_method | enum | kmeans | 聚类方法 |
| cluster_k | int | 20 | 聚类数 |
| label_top_n_terms | int | 5 | 每个簇用于生成标签的代表词数 |

### 输出字段建议：`keyword_cluster_result.csv`
| 字段 | 说明 |
|---|---|
| term | 关键词 |
| cluster_id | 聚类编号 |
| distance_to_centroid | 到中心点距离 |
| is_label_term | 是否为代表词 |

## B.9.5.2 子模块：Institution-Keyword Co-occurrence

### 目的
分析机构与关键词之间的共现关系，用于识别机构核心技术主题或研究关注点。

### 输出字段建议：`institution_keyword_cooccurrence.csv`
| 字段 | 说明 |
|---|---|
| institution | 机构 |
| keyword | 关键词 |
| cooccurrence_count | 共现次数 |
| year | 年份，可空 |
| score | 权重分数占位 |

### 设计要求
- 支持 institution -> keywords
- 支持 keyword -> institutions
- 支持按年份查看关系变化

## B.9.5.3 子模块：Institution-Topic Co-occurrence

### 目的
基于关键词聚类结果，分析机构与主题之间的关系。

### 主题定义
- 每个主题来自关键词聚类结果
- 主题标签默认由“距离中心点最近的若干个词”自动生成
- 允许用户手动修改主题名称

### 输出字段建议：`institution_topic_cooccurrence.csv`
| 字段 | 说明 |
|---|---|
| institution | 机构 |
| topic_id | 主题编号 |
| topic_label | 主题标签 |
| cooccurrence_count | 共现次数 |
| representative_terms | 代表词列表 |
| year | 年份，可空 |

### 设计要求
- 机构 × 主题分析必须建立在已选特征词集合之上
- 主题的代表词生成逻辑应可追溯
- 应支持输出机构 × 主题共现图

---

## B.9.6 子模块：Basic Clustering

### 目的
对文档进行初步聚类，帮助发现语料结构。

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| vectorizer | enum | tfidf | 向量化方式 |
| reducer | enum | pca_or_umap_placeholder | 降维方式 |
| cluster_method | enum | kmeans | 聚类方法 |
| cluster_k | int | 8 | 聚类数 |
| random_seed | int | 42 | 随机种子 |

### 输出字段建议
| 字段 | 说明 |
|---|---|
| doc_id | 文档 ID |
| cluster_id | 聚类编号 |
| x | 2D 横坐标 |
| y | 2D 纵坐标 |
| title | 标题 |
| year | 年份 |
| source | 来源 |

### 要求
- 图上点选文档时可查看详情
- 算法可替换，但输出 schema 应稳定

---

## B.10 Step 08：Export

### 目的
将分析结果输出为用户可交付文件。

### 输入
- Analysis 结果表
- 图表资源
- 项目与 run 摘要信息

### 输出
- CSV/XLSX 文件
- PNG 图
- HTML 报告
- 导出日志

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| export_csv | bool | true | 导出 CSV |
| export_xlsx | bool | true | 导出 XLSX |
| export_png | bool | true | 导出图表 PNG |
| export_html_report | bool | true | 导出 HTML 报告 |
| include_audit | bool | true | 包含审计表 |

### HTML 报告至少包含
- 项目摘要
- 文档规模
- 流程参数摘要
- 高频词
- 词频趋势图
- 共现摘要
- 关键词聚类摘要
- 机构 × 关键词摘要
- 机构 × 主题摘要
- 聚类结果
- 审计摘要

---

## B.11 Step 级缓存策略

### 原则
- 每个 step 的输出可作为后续 step 输入缓存
- 当上游参数或资源变化时，下游缓存失效
- cache 命中与否必须在日志中可见

### 建议缓存键
缓存键建议基于以下内容生成哈希：
- 项目语料版本
- pipeline step 参数
- 词表版本
- engine version

---

## B.12 日志与错误模型

### 每步日志至少记录
- step 名称
- 开始/结束时间
- 输入规模
- 输出规模
- 参数摘要
- warning 数量
- error 数量
- cache hit/miss

### 错误等级建议
- `info`
- `warning`
- `error`
- `fatal`

### 中止规则
- ingestion 失败：整批中止
- cleaning/normalization/tokenization 局部失败：允许继续，但需标记受影响文档
- analysis/export 关键文件写出失败：run 标记失败

---

## B.13 审计体系要求

### V1 必做审计表
- regex 替换审计
- 词表替换审计
- 过滤剔除摘要
- run 参数快照

### 审计目标
- 用户可以追问某个词为何消失/变化
- 用户可以还原某次 run 的规则环境
- 审计结果可单独导出

---

## B.14 V2 预留字段

以下字段 V1 即便不完整启用，也建议预留：
- `step_id`
- `node_id`
- `upstream_nodes`
- `analysis_plugin_id`
- `artifact_refs`

这样未来从线性 pipeline 迁移到节点式流程时，中间产物和审计结构不必重写。

---

## B.15 建议的实现顺序
1. Ingestion
2. Cleaning
3. Tokenization
4. Dictionary Application
5. Filtering
6. Frequency / Term-Document / Term-Year
7. Feature-term Selection
8. Keyword Extraction
9. Keyword Clustering
10. Institution Analysis
11. Co-occurrence
12. Clustering
13. Export / Report

### 原因
- 先跑通预处理与基础统计闭环
- 再增加较重的挖掘模块
- 最后补导出与报告

---

## B.16 给 Codex 的 `project-schema` 实现提示词

```md
Define a stable, portable, project-based persistence schema for a desktop text preprocessing and basic text mining application.

Requirements:
- First shipping target is Windows, but schema must remain portable to macOS
- Project data must live outside the installation directory
- Separate business data, run artifacts, cache, exports, and UI state
- Support corpus import, metadata mapping, dictionary sets, linear pipeline configs, run history, parameter snapshots, outputs, charts, reports, and future graph-based pipeline reservation
- All important paths should be relative paths
- Run directories must be immutable after completion
- UI state must never contain business-critical data
- Add schema versioning and compatibility metadata
```

---

## B.17 给 Codex 的 `pipeline-spec` 实现提示词

```md
Define a V1 linear pipeline specification for a desktop text preprocessing and basic text mining application.

The pipeline must include:
- ingestion
- cleaning
- normalization
- tokenization
- dictionary application
- filtering
- analysis
- export

For each step, define:
- purpose
- inputs
- outputs
- output schema
- parameters
- warnings and errors
- audit requirements
- cache behavior

The analysis stage must include:
- frequency statistics
- term-document relations
- term-year relations
- co-occurrence analysis
- keyword extraction
- basic clustering

The spec must preserve compatibility with a future graph-based pipeline editor even though V1 executes linearly.
```

