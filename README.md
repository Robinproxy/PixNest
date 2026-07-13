<div align="center">
  <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect x='3' y='5' width='26' height='22' rx='6' fill='%238fa99b'/%3E%3Cpath d='M7 22l5.5-7 4 5 3-3.5L25 22H7z' fill='%23c9d6cd'/%3E%3Ccircle cx='12' cy='12' r='2.2' fill='%23f0d68a'/%3E%3C/svg%3E" width="64" height="64" alt="PixNest">
  <br>
  <h1>PixNest</h1>
  <p>轻量级私有图床 · 浏览器端压缩与水印 · Token 鉴权</p>
</div>

![License](https://img.shields.io/badge/license-MIT-green)

## 功能特性

| 分类 | 说明 |
|---|---|
| **安全** | Token 鉴权，登录限流（每 IP 5 次/60 秒），Magic Bytes 文件格式校验 |
| **上传** | 点击 / 拖拽 / 粘贴上传，批量上传，进度条显示 |
| **处理** | 客户端 WebP 转换，质量滑块，文字水印，EXIF 方向自动修正 |
| **分发** | 直链 / HTML / Markdown / BBCode 一键复制，图库浏览，灯箱导航 |
| **存储** | 可选自动过期（1 天/7 天），定时清理，本地磁盘持久化 |

## 快速开始

```bash
docker run -d -p 8000:8000 \
  -e AUTH_TOKEN=my-secret-key \
  -v ./uploads:/app/uploads \
  ghcr.io/robinproxy/pixnest:latest
```

打开 http://localhost:8000 ，输入密钥即可使用。

## 配置说明

通过环境变量配置：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `AUTH_TOKEN` | `123456` | 管理接口鉴权密钥 |
| `PUBLIC_BASE_URL` | — | 图片直链的公网前缀，如 `https://img.example.com` |
| `MAX_UPLOAD_MB` | `10` | 单文件大小上限（MB） |
| `CLEANUP_INTERVAL_SEC` | `600` | 过期文件清理间隔（秒） |
| `UPLOAD_DIR` | `app/uploads` | 图片和元数据存储目录 |
| `TUNNEL_TOKEN` | — | Cloudflare Tunnel 令牌（docker-compose 使用） |

## Docker Compose 部署（生产）

```yaml
services:
  pixnest:
    image: ghcr.io/robinproxy/pixnest:latest
    build: .
    container_name: pixnest
    restart: always
    volumes:
      - ./app/uploads:/app/uploads
    environment:
      AUTH_TOKEN: ${AUTH_TOKEN:?Set AUTH_TOKEN in .env}
      PUBLIC_BASE_URL: ${PUBLIC_BASE_URL:-}
      MAX_UPLOAD_MB: ${MAX_UPLOAD_MB:-10}
      CLEANUP_INTERVAL_SEC: ${CLEANUP_INTERVAL_SEC:-600}
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3

  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: cloudflared-pixnest
    restart: always
    command: tunnel run
    environment:
      TUNNEL_TOKEN: ${TUNNEL_TOKEN:?Set TUNNEL_TOKEN in .env}
    depends_on:
      pixnest:
        condition: service_healthy
```

使用步骤：

1. 复制 `cp .env.example .env`，填写 `AUTH_TOKEN` 和 `TUNNEL_TOKEN`
2. 如需自定义图片链接域名，设置 `PUBLIC_BASE_URL`
3. 执行 `docker compose up -d`

应用容器不暴露宿主机端口，仅通过 Cloudflare Tunnel 访问。上传目录持久化在 `./app/uploads`。

> 容器以非 root 用户（uid 1000）运行。如果使用宿主机目录挂载，需将目录归属设为 uid 1000：
> ```bash
> sudo chown -R 1000:1000 ./app/uploads
> ```

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
- 图片直链 `/i/*` 不鉴权（图床通用模型）
- 登录接口限流：每 IP 60 秒内最多 5 次尝试
- 上传文件通过 Magic Bytes 校验真实格式，不依赖扩展名
- 文件名做路径规范化处理，防止目录穿越
- 鉴权密钥不会出现在日志中

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
.env.example      环境变量模板
Dockerfile        容器构建
docker-compose.yml  生产部署
```

## 许可证

[MIT](LICENSE)
