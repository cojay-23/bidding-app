# BidScope 部署指南（阿里云 CentOS x86）

## 环境要求

- CentOS 7/8/Stream x86_64
- 2 核 4G 以上（大模型分析需要内存）
- Docker 20.10+

---

## 第一步：连接服务器并安装 Docker

```bash
ssh root@<你的服务器公网IP>

# 安装 Docker（CentOS 7+ 通用）
yum install -y yum-utils
yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 启动 Docker 并设开机自启
systemctl start docker
systemctl enable docker

# 验证
docker --version
docker compose version
```

> 如果 yum 安装慢，可先换阿里云镜像源：
> ```bash
> yum install -y wget
> wget -O /etc/yum.repos.d/CentOS-Base.repo https://mirrors.aliyun.com/repo/Centos-7.repo  # CentOS 7
> ```

---

## 第二步：上传项目文件

在**本地 Mac** 上打包项目（排除不需要的文件）：

```bash
cd /Users/zhangwj/Desktop/bidding-app

# 打包（排除 .env，因为会在服务器上重新配置）
tar -czf bidding-app.tar.gz \
  --exclude='.env' \
  --exclude='data' \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='.DS_Store' \
  .
```

上传到服务器：

```bash
scp bidding-app.tar.gz root@<服务器IP>:/root/
```

在**服务器**上解压：

```bash
cd /root
mkdir bidding-app
tar -xzf bidding-app.tar.gz -C bidding-app
cd bidding-app
```

---

## 第三步：配置环境变量

在服务器上创建 `.env` 文件：

```bash
cd /root/bidding-app

cat > .env << 'EOF'
# Kimi API 密钥（必需，用于高级分析）
MOONSHOT_API_KEY=sk-你的真实密钥

# 管理员账号密码（必需，生产环境务必修改）
ADMIN_USERNAME=admin
ADMIN_PASSWORD=你的强密码

# 会话密钥（可选，自动生成随机值，设置固定值可避免重启后全部登出）
SESSION_SECRET=你的会话密钥随机串

# 可选：模型选择
LLM_MODEL=kimi-k2.6

# 容器内运行用户（需与 data 目录授权一致）
APP_UID=999
APP_GID=999
EOF
```

> **注意**：`.env` 已在 `.gitignore` 中，不会进版本控制。请将 API Key 替换为你的真实密钥。

---

## 第四步：构建并启动

```bash
cd /root/bidding-app

# 创建持久化目录，并授权给容器内非 root 用户。
# 如果 .env 中修改了 APP_UID/APP_GID，这里也要使用相同值。
mkdir -p data/projects
chown -R 999:999 data

docker compose up -d --build
```

验证服务是否正常：

```bash
# 检查容器状态
docker ps | grep bidding-app

# 检查日志
docker logs bidding-app --tail 20

# 看到 "Uvicorn running on http://0.0.0.0:8000" 即启动成功
```

本地测试接口：

```bash
curl http://localhost:8000/api/health
# 应返回 {"status":"ok"}
```

---

## 第五步：配置阿里云安全组

在 **阿里云控制台 → ECS → 安全组** 中添加入方向规则：

| 协议 | 端口 | 来源 | 说明 |
|------|------|------|------|
| TCP | 8000 | 0.0.0.0/0 | BidScope Web 服务 |

> 生产环境建议限制来源 IP 为你的办公 IP，或使用 Nginx 反向代理 + HTTPS。

配置完成后，浏览器访问 `http://<服务器公网IP>:8000` 即可看到登录页。

默认账号 `admin`，密码为 `.env` 中 `ADMIN_PASSWORD` 设置的值。

---

## 第六步（强烈建议）：Nginx 反向代理 + HTTPS

### 6.1 安装 Nginx

```bash
yum install -y nginx
systemctl start nginx
systemctl enable nginx
```

### 6.2 配置反向代理

```bash
cat > /etc/nginx/conf.d/bidscope.conf << 'EOF'
server {
    listen 80;
    server_name 你的域名或IP;

    client_max_body_size 100M;   # 允许上传大文件

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;  # 大模型分析可能耗时较长
    }
}
EOF

# 重启 Nginx
nginx -t && systemctl reload nginx
```

### 6.3 配置 HTTPS（使用 Certbot 免费证书）

```bash
# 安装 Certbot
yum install -y epel-release
yum install -y certbot python3-certbot-nginx

# 申请证书（需要域名已解析到本机）
certbot --nginx -d your-domain.com

# 自动续期
echo "0 3 * * * certbot renew --quiet" | crontab -
```

配置 HTTPS 后，将安全组入口从 8000 改为 443。

---

## 第七步：设置开机自启

Docker 容器不会在服务器重启后自动启动，需要配置：

```bash
# 方法一：使用 docker compose restart policy（已在 docker-compose.yml 中配置 restart: unless-stopped）
# 确认配置生效
docker compose down
docker compose up -d

# 方法二：创建 systemd 服务（推荐，确保 Docker 启动后再启动容器）
cat > /etc/systemd/system/bidscope.service << 'EOF'
[Unit]
Description=BidScope Container
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/root/bidding-app
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable bidscope.service
```

---

## 日常维护

### 更新代码后重新部署

```bash
cd /root/bidding-app
git pull  # 如果用 git 管理
# 或重新 scp 上传新包

docker compose up -d --build   # 重建镜像
docker logs bidding-app -f      # 查看实时日志
```

### 查看项目数据

```bash
# 所有项目文件存储在
ls /root/bidding-app/data/projects/

# 数据库文件
ls /root/bidding-app/data/app.db
```

### 修改密码

修改 `.env` 中的 `ADMIN_PASSWORD` 和 `ADMIN_USERNAME`，然后重启容器：

```bash
vim /root/bidding-app/.env
docker compose up -d
```

### 备份数据

```bash
tar -czf backup-$(date +%Y%m%d).tar.gz /root/bidding-app/data/
```

---

## 故障排查

| 现象 | 检查 |
|------|------|
| 页面打不开 | `docker ps` 看容器是否在跑；检查安全组规则 |
| 新建/删除项目 500 | `docker logs bidding-app --tail 100`；重点检查 `/app/data` 或 `/app/data/app.db` 是否不可写；执行 `chown -R 999:999 /root/bidding-app/data` 后重建启动 |
| 高级分析报错 | `docker logs bidding-app \| grep -i error`；确认 .env 中 API Key 正确 |
| 大文件上传失败 | Nginx 配置中 `client_max_body_size` 是否够大；Docker 剩余磁盘空间 `df -h` |
| 容器启动失败 | `docker compose up` 看构建报错信息 |
