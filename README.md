# PixNest

极简私有图床（原 nano-imgbed）。浏览器端可选 WebP 压缩与水印，本地磁盘存储，Token 鉴权，适合 Docker + Cloudflare Tunnel 部署。

## 功能

- 访问密钥登录（`X-Auth-Token`）
- 点击 / 拖拽 / 粘贴上传
- 客户端 WebP 压缩、质量滑块、水印
- 可选过期（1 / 7 天），服务端定时清理
- 图库浏览与删除
- 直链 / HTML / Markdown / BBCode 一键复制

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export AUTH_TOKEN=your-secret   # 可选，默认开发密钥 123456
cd app && uvicorn main:app --host 0.0.0.0 --port 8000
```

打开 http://localhost:8000

## Docker + Cloudflare Tunnel

```bash
cp .env.example .env
# 编辑 .env：设置 AUTH_TOKEN、TUNNEL_TOKEN，可选 PUBLIC_BASE_URL
docker compose up -d --build
```

- 应用容器不映射宿主机端口，仅通过 Tunnel 暴露
- 上传目录：`./app/uploads` → 容器 `/app/uploads`
- 健康检查：`GET /health`

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `AUTH_TOKEN` | `123456`（仅本地） | 管理接口密钥 |
| `PUBLIC_BASE_URL` | 空 | 生成链接时的公网根，如 `https://img.example.com` |
| `MAX_UPLOAD_MB` | `10` | 单文件大小上限 |
| `CLEANUP_INTERVAL_SEC` | `600` | 过期清理间隔（秒） |
| `TUNNEL_TOKEN` | — | Cloudflare Tunnel（compose 用） |

## API

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| `GET` | `/` | 否 | 前端页面 |
| `GET` | `/health` | 否 | 健康检查 |
| `GET` | `/verify` | 是 | 校验密钥 |
| `POST` | `/upload` | 是 | 上传（`file`, `expire_days`） |
| `GET` | `/api/history` | 是 | 图库列表 |
| `DELETE` | `/api/delete/{filename}` | 是 | 删除 |
| `GET` | `/i/{filename}` | 否 | 图片直链（知道 URL 即可访问） |

鉴权头：`X-Auth-Token: <AUTH_TOKEN>`

## 安全说明

- 写/列/删接口需密钥；**图片直链 `/i/*` 不鉴权**（图床常见模型）
- 生产务必设置强 `AUTH_TOKEN`，勿提交 `.env`
- 上传限制为常见图片类型与大小上限；删除做路径规范化，防止目录穿越
- 日志不会打印密钥

## 项目结构

```
app/main.py       # FastAPI 后端
app/index.html    # 单页前端
app/uploads/      # 图片与 meta.json
Dockerfile
docker-compose.yml
.env.example
```
