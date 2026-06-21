# 标书分析内部工具

这是一个内部快速使用版应用：无登录、单机部署、本地磁盘保存文件、SQLite 保存项目状态。

## 本机启动

```bash
docker compose up -d --build
```

打开：

```text
http://127.0.0.1:8000
```

## 数据目录

所有业务数据都在：

```text
data/
  app.db
  projects/
```

后续迁移到阿里云时，保留并迁移 `data/` 即可。

## 当前能力

- 新建项目
- 上传 docx、pdf、txt、md
- 抽取文档文本
- 识别项目名称、编号、招标人、预算、截止时间
- 提取废标/风险、评分、材料准备线索
- 生成 HTML 报告和结果包

## 后续接入点

完整的 `bidding-analyst` 得分测算流程可以接入：

```text
backend/app/analyzer.py
```

保持 API 和前端不变，只替换分析逻辑即可。
