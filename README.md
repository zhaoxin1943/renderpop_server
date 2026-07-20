# RenderPop Server

独立 Python 后端：`FastAPI` + `SQLModel` + `MySQL` + `Dramatiq(Redis)`。

分层：`api` → `service` → `repo`；HTTP 请求内共用一个异步 MySQL `AsyncSession`；依赖注入用 FastAPI `Depends`。

## 栈

| 层 | 选型 |
| --- | --- |
| API | FastAPI（全部 async 路由） |
| 校验 / 配置 | Pydantic v2 + pydantic-settings |
| ORM | SQLModel + SQLAlchemy asyncio |
| DB | MySQL 8（aiomysql 运行时 / pymysql 迁移） |
| 迁移 | Alembic |
| 队列 | Dramatiq + Redis（支持 async actor） |
| 登录（下一步） | Google OAuth + 服务端 Session |

## 环境

```bash
# conda
conda activate renderpop

cd /Users/zx/python_workspace/renderpop_server
cp .env.example .env

# 依赖（二选一）
pip install -r requirements-dev.txt   # 固定版本，含 dev 工具
# pip install -e ".[dev]"             # 可编辑安装，版本见 pyproject.toml

# 本地 MySQL + Redis
docker compose up -d

# 迁移
alembic revision --autogenerate -m "init users"
alembic upgrade head

# API
uvicorn app.main:app --reload --port 8000

# Worker（另开终端）
dramatiq app.workers.tasks
```

## 健康检查

- `GET /api/health/live` — 进程存活（不连库）
- `GET /api/health` — service → repo 异步 ping MySQL
- `GET /docs` — OpenAPI（非 production）

## 目录

```text
app/
  api/          # 路由，只调 service
  service/      # 业务编排
  repo/         # 异步 SQL
  models/       # SQLModel 表
  schemas/      # Pydantic DTO（API 入出参）
  core/         # config / db / deps
  workers/      # Dramatiq broker + actors
alembic/        # 迁移
```

## 请求内 Session

`app/core/db.py` 的 `get_db_session` 在单次请求内 yield 同一个 `AsyncSession`。  
`app/core/deps.py` 把该 session 注入 repo，再注入 service。成功 commit，异常 rollback。

Worker 无 HTTP 作用域，使用 `worker_session()` 或 actor 内自建短生命周期 session。
