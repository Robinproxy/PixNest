<div align="center">
  <img src="assets/logo.svg" width="64" height="64" alt="PixNest">
  <br>
  <h1>PixNest</h1>
  <p>轻量级私有图床 · 浏览器端压缩与水印 · Token 鉴权</p>
</div>

![License](https://img.shields.io/badge/license-MIT-green)

## 功能特性

| 分类 | 说明 |
|---|---|
| **安全** | Token 鉴权，登录/上传/API 三级限流，Magic Bytes 文件校验，Host 头防护，IP 伪造防护 |
| **上传** | 点击 / 拖拽 / 粘贴上传，批量上传，进度条显示 |
| **处理** | 客户端 WebP 转换，质量滑块，文字水印，EXIF 方向自动修正 |
| **分发** | 直链 / HTML / Markdown / BBCode 一键复制，图库浏览，灯箱导航 |
| **存储** | 可选自动过期（1 天/7 天），定时清理，本地磁盘持久化 |

## Docker Compose 部署

项目根目录附带 `docker-compose.yml`，一键启动 PixNest 应用。

### 前置准备

#### 1. 生成密钥并创建 .env

在项目目录下执行以下命令，自动生成 64 位随机 `AUTH_TOKEN` 并写入 `.env`：

```bash
TOKEN=$(openssl rand -hex 32)
cat > .env << EOF
AUTH_TOKEN=$TOKEN
PUBLIC_BASE_URL=https://img.your-domain.com
ALLOWED_HOSTS=img.your-domain.com
TRUSTED_PROXIES=127.0.0.1
MAX_UPLOAD_MB=10
CLEANUP_INTERVAL_SEC=600
EOF
```

> **PUBLIC_BASE_URL 说明：**
>
> | 场景 | 填什么 |
> |---|---|
> | 有域名指向这台 VPS，如 `img.example.com` | `https://img.example.com` |
> | 只通过 `http://VPS_IP:8000` 访问 | 不填（留空，链接自动用当前请求地址） |
>
> 如果暂时没域名，执行前把 `PUBLIC_BASE_URL` 那行删掉。
>
> `ALLOWED_HOSTS` 和 `TRUSTED_PROXIES` 为可选加固项，详见下方[部署加固](#部署加固)。

#### 2. 设置目录权限

容器以非 root 用户（uid 1000）运行。宿主机挂载目录需归该 uid 所有：

```bash
sudo chown -R 1000:1000 app/uploads
```

### 启动

```bash
docker compose up -d
```

### 访问

打开 http://localhost:8000 ，输入 `.env` 中配置的 `AUTH_TOKEN` 即可使用。

### 环境变量详解

`docker-compose.yml` 中的环境变量从 `.env` 文件读取，语法说明如下：

| Compose 写法 | 含义 |
|---|---|
| `${AUTH_TOKEN:?Set AUTH_TOKEN in .env}` | 从 `.env` 读取，**必填**，缺少时启动报错 |
| `${PUBLIC_BASE_URL:-}` | 从 `.env` 读取，**可选**，不填则为空 |
| `${ALLOWED_HOSTS:-}` | 可选，不填则不校验 Host 头 |
| `${TRUSTED_PROXIES:-}` | 可选，不填则不信任转发头 |
| `${MAX_UPLOAD_MB:-10}` | 可选，不填默认为 `10` |
| `${CLEANUP_INTERVAL_SEC:-600}` | 可选，不填默认为 `600` |

全部可用变量：

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `AUTH_TOKEN` | 是 | - | 管理接口鉴权密钥 |
| `PUBLIC_BASE_URL` | 否 | 空 | 图片直链的公网前缀，如 `https://img.example.com` |
| `ALLOWED_HOSTS` | 否 | 空 | 允许的 Host 头，逗号分隔，如 `img.example.com,localhost` |
| `TRUSTED_PROXIES` | 否 | 空 | 信任的代理 IP，逗号分隔，如 `127.0.0.1` |
| `MAX_UPLOAD_MB` | 否 | `10` | 单文件大小上限（MB） |
| `CLEANUP_INTERVAL_SEC` | 否 | `600` | 过期文件清理间隔（秒） |
| `UPLOAD_DIR` | 否 | `app/uploads` | 图片和元数据存储目录（仅 Docker 单容器运行） |

### 健康检查

```bash
docker compose ps
```

服务状态为 `healthy` 即正常运行。

## Docker 单容器运行

不使用 Compose 时：

```bash
docker run -d -p 8000:8000 \
  -e AUTH_TOKEN=my-secret-key \
  -v ./uploads:/app/uploads \
  ghcr.io/robinproxy/pixnest:latest
```

## API 参考

管理接口需要在请求头中添加 `X-Auth-Token`。图片直链无需鉴权。

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| `GET` | `/` | 否 | 前端页面 |
| `GET` | `/health` | 否 | 健康检查 |
| `GET` | `/verify` | 是 | 校验密钥（含限流） |
| `POST` | `/upload` | 是 | 上传图片（`file` + 可选 `expire_days`） |
| `GET` | `/api/history` | 是 | 图库列表（分页参数 `page`、`size`） |
| `DELETE` | `/api/delete/{filename}` | 是 | 删除图片 |
| `GET` | `/i/{filename}` | 否 | 图片直链 |

## 安全

- 写 / 列 / 删接口均需 `X-Auth-Token` 鉴权
- `AUTH_TOKEN` 未设置时所有管理接口返回 401，拒绝服务
- 图片直链 `/i/*` 不鉴权（图床通用模型）
- 三级限流：登录 5 次/60 秒，上传 30 次/60 秒，API 60 次/60 秒（均按 IP）
- 上传文件通过 Magic Bytes 校验真实格式，不依赖扩展名
- 文件名做路径规范化处理，防止目录穿越
- 鉴权密钥不会出现在日志中
- 响应头包含 CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy / HSTS

### 部署加固

以下两个环境变量为可选项，**建议在生产环境中配置**。它们的值是公开配置（非密钥），知道值不影响安全性。

#### `ALLOWED_HOSTS`

防止 **Host 头注入**。当 `PUBLIC_BASE_URL` 未设置时，上传返回的图片 URL 会取自请求的 `Host` 头，攻击者可伪造 Host 让 URL 指向钓鱼域名。

设置后，中间件会校验每个请求的 Host 头，不在白名单中的请求直接返回 400。

```bash
# .env
ALLOWED_HOSTS=img.example.com,localhost
```

> 配合 `PUBLIC_BASE_URL` 使用效果最佳：`PUBLIC_BASE_URL` 固定 URL 域名，`ALLOWED_HOSTS` 拦截伪造 Host 的请求。

#### `TRUSTED_PROXIES`

防止 **IP 伪造绕过限流**。默认情况下，`X-Forwarded-For` 和 `CF-Connecting-IP` 头被忽略，直接使用 TCP 连接的真实 IP。这意味着在反向代理后面，所有请求的 IP 都会显示为代理 IP，限流无法区分用户。

设置后，仅当请求来自信任的代理 IP 时，才会读取转发头来获取真实客户端 IP。

```bash
# .env
TRUSTED_PROXIES=127.0.0.1
```

#### 常见部署场景配置

| 场景 | ALLOWED_HOSTS | TRUSTED_PROXIES | 说明 |
|---|---|---|---|
| Cloudflare Tunnel | `img.example.com` | `127.0.0.1` | Tunnel 在本地连接，Cloudflare 设置 `CF-Connecting-IP` |
| Nginx 反向代理 | `img.example.com` | `127.0.0.1` | Nginx 设置 `X-Forwarded-For` |
| 直接暴露端口 | 不设 | 不设 | 无反代，TCP IP 即真实 IP，无需信任转发头 |
| 本地开发 | 不设 | 不设 | 默认行为，不做额外校验 |

> **安全原理**：这些值是校验规则而非密钥。攻击者即使知道 `TRUSTED_PROXIES=127.0.0.1`，也无法伪造 TCP 连接的来源 IP；知道 `ALLOWED_HOSTS` 也不会获得任何额外权限。唯一需要保密的是 `AUTH_TOKEN`。

## 开发

```bash
# 本地环境
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# 启动服务
cd app && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 代码检查
ruff check app/

# 运行测试
pytest tests/ -v
```

## 项目结构

```
app/
  main.py         FastAPI 后端
  index.html      单页前端
  uploads/        图片与 meta.json
tests/
  test_api.py     API 集成测试
assets/
  logo.svg        项目图标
.env.example      环境变量模板
Dockerfile        容器构建
docker-compose.yml  生产部署
```

## 许可证

[MIT](LICENSE)
