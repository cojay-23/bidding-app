# BidScope — 智能标书分析工作台

BidScope 是一款面向招投标场景的智能分析工具。上传招标文件（.docx / .pdf），即可自动生成涵盖废标条款、评分标准、资质门槛、价格限制、装订要求、投标文件框架等 15 章的交互式 HTML 分析报告。

## 适用场景

| 角色 | 使用场景 |
|------|---------|
| **售前工程师** | 快速拆解招标文件，定位废标风险、评分要点和加分机会，制定应标策略 |
| **投标专员** | 自动提取时间节点、资质门槛、材料清单，生成投标文件骨架和自检 Checklist |
| **项目经理** | 评估投标可行性，对标竞争对手，规划资源投入 |
| **销售团队** | 多项目并行时快速横向对比，优先分配精力到高胜率项目 |

核心价值：**把几百页招标文件的分析时间从 1-2 天压缩到 5 分钟。**

## 功能概览

### 双引擎分析

| 引擎 | 原理 | 速度 | 精度 | 适用 |
|------|------|------|------|------|
| **通用分析（快速）** | 基于四级关键词体系（33 个关键词）的正则匹配 | 秒级 | 中等 | 快速预筛、关键词定位 |
| **高级分析（大模型深度分析）** | 调用 Kimi K2.6 大模型，完整理解全文语义 | 30-90 秒 | 高 | 正式应标、深度解读 |

### 分析报告包含 15 章

1. 项目基本信息速览
2. 废标条款清单（⭐星号否决 / 🔴致命 / 🟡严重 / 🟠需注意 四级分类）
3. 评分标准详解
4. 我方方案得分测算
5. 资质门槛清单
6. 价格限制与报价策略参考
7. 加分机会与满分材料清单
8. 截图与证明材料清单
9. 装订封装要求
10. 投标文件框架（可直接粘贴到 Word）
11. 投标文件自检 Checklist（可交互打勾）
12. 素材准备 TodoList
13. 得分补强行动清单
14. 综合分析与建议

### 交互特性

- 废标条款按风险等级彩色卡片展示（红/橙/黄四色）
- 星号否决条款红色双边框突出
- 时间轴 + 倒计时天数
- 可交互 Checklist（点击打勾 + 进度条）
- 报告历史版本管理（每次分析自动归档）

## 快速开始

### 前提条件

- Docker 和 Docker Compose
- （高级分析功能）Kimi API Key（在 [platform.kimi.com](https://platform.kimi.com/console/api-keys) 申请）

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd bidding-app
```

### 2. 配置大模型 API（可选，仅高级分析需要）

```bash
cp .env.example .env
# 编辑 .env，填入你的 Kimi API Key：
# MOONSHOT_API_KEY=sk-xxxxxxxx
```

| 可选环境变量 | 说明 | 默认值 |
|-------------|------|--------|
| `MOONSHOT_API_KEY` | Kimi API 密钥 | 无（高级分析不可用） |
| `LLM_MODEL` | 大模型名称 | `kimi-k2.6` |
| `LLM_BASE_URL` | API 地址 | `https://api.moonshot.cn/v1` |

### 3. 启动服务

```bash
docker compose up -d --build
```

访问 [http://localhost:8000](http://localhost:8000)，默认账号 `admin`，密码 `dJSK2o91D*`。

### 4. 使用流程

1. 登录 → 新建项目 → 上传招标文件（.docx / .pdf / .txt / .md）
2. 选择分析引擎：通用分析（快速）或 高级分析（大模型深度分析）
3. 等待分析完成，点击「查看完整报告」浏览交互式 HTML 报告
4. 可查看历史报告版本

## 技术架构

```
bidding-app/
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口：路由、中间件
│   │   ├── analyzer.py               # 分析引擎：通用分析（正则关键词）+
│   │   │                             #   高级分析（Kimi LLM）调度
│   │   ├── bidding_analyst_core.py   # 高级分析核心：文本提取 → prompt 构建 →
│   │   │                             #   Kimi API 调用 → HTML 报告生成
│   │   ├── auth.py                   # 认证模块：session-based 登录
│   │   ├── database.py               # SQLite 数据层：项目/文件/报告 CRUD
│   │   └── config.py                 # 路径配置
│   ├── static/
│   │   ├── index.html                # 主工作台 SPA（原生 JS，无框架依赖）
│   │   └── login.html                # 登录页（Google Material Design 风格）
│   ├── requirements.txt              # Python 依赖
│   └── Dockerfile
├── docker-compose.yml
├── data/                             # 持久化数据（挂载到容器）
│   └── projects/{id}/
│       ├── uploads/                  # 原始文件
│       ├── extracted/                # 提取的纯文本
│       ├── reports/                  # HTML 报告（含历史归档）
│       └── logs/                     # 错误日志
└── README.md
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **后端** | FastAPI (Python 3.12) | 异步 Web 框架 |
| **数据库** | SQLite | 内嵌数据库，零配置 |
| **文档解析** | python-docx + pypdf | docx/pdf 文本提取 |
| **大模型** | Kimi K2.6 (Moonshot API) | OpenAI 兼容接口 |
| **认证** | itsdangerous | Session 签名 + HttpOnly Cookie |
| **前端** | 原生 HTML/CSS/JS | SPA，无框架依赖 |
| **部署** | Docker + Docker Compose | 一键构建启动 |

### 通用分析引擎原理

```
招标文件 (.docx/.pdf)
    │
    ▼
extract_text() — python-docx / pypdf 提取纯文本
    │
    ▼
四级关键词匹配体系（33 个关键词，参照 bidding-analyst skill）
    ├── RISK_FATAL:  废标/否决/作废/取消中标资格... (9 词)
    ├── RISK_STAR:   ★ / *                              (2 符)
    ├── RISK_STRICT: 必须/不得/严禁/否则废标...         (10 词)
    └── RISK_REVIEW: 资格审查/符合性审查/初步评审...     (12 词)
    │
    ▼
extract_risk_detail() — 段落级提取 + TOC 噪声过滤 + 风险分类排序
    │
    ▼
render_report() — 生成带 CSS/JS 的交互式 HTML 报告
```

### 高级分析引擎原理

```
招标文件 (.docx/.pdf)
    │
    ▼
extract_text() — 提取纯文本（最大 120,000 字）
    │
    ▼
build_prompt() — 构建 180+ 行结构化 prompt
    │  角色：10 年资深标书分析师
    │  任务：七大模块分析 + 12 章 HTML 报告
    │  规则：原文引用、风险分级、摘要 JSON 嵌入
    ▼
Kimi K2.6 API (OpenAI 兼容接口)
    │  256K 上下文，temperature=1，无 max_tokens 限制
    ▼
ensure_html_closed() — 自动补齐缺失标签
    │
    ▼
extract_summary() — 从 <script id="report-summary"> 提取 JSON 元数据
    │
    ▼
写入 HTML 报告文件 → 归档历史版本
```

## 安全说明

- 登录态基于签名的 HttpOnly Cookie（24 小时过期）
- 密码使用 `hmac.compare_digest` 防时序攻击
- 当前为单用户模式（admin），注册功能将在正式版开放
- Session Secret 每次容器重启随机生成，重启后需重新登录

## License

Internal Use
