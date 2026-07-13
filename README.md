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
| `AUTH_TOKEN` | — | 管理接口鉴权密钥（必填，未设置时所有管理接口返回 401） |
| `PUBLIC_BASE_URL` | — | 图片直链的公网前缀，如 `https://img.example.com` |
| `MAX_UPLOAD_MB` | `10` | 单文件大小上限（MB） |
| `CLEANUP_INTERVAL_SEC` | `600` | 过期文件清理间隔（秒） |
| `UPLOAD_DIR` | `app/uploads` | 图片和元数据存储目录 |
| `TUNNEL_TOKEN` | — | Cloudflare Tunnel 令牌（docker-compose 使用） |

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
