# RenderPop Server

独立 Python 后端：`FastAPI` + `SQLModel` + `MySQL` + `Dramatiq(Redis)`。

分层：`api` → `service` → `repo`；HTTP 请求内共用一个异步 MySQL `AsyncSession`；依赖注入用 FastAPI `Depends`。

**新会话 / 续作请先读 [`docs/HANDOFF.md`](docs/HANDOFF.md)**。  
产品 PRD：[`docs/RenderPop_Backend_PRD_v1.0.md`](docs/RenderPop_Backend_PRD_v1.0.md)。

当前能力：**积分账本 + 月会员商品 + Fast/Pro 生图 + Dodo 结账/Webhook 骨架**（登录与 S3 转存仍占位）。

## 栈

| 层 | 选型 |
| --- | --- |
| API | FastAPI（全部 async 路由） |
| 校验 / 配置 | Pydantic v2 + pydantic-settings |
| ORM | SQLModel + SQLAlchemy asyncio |
| DB | MySQL 8（aiomysql 运行时 / pymysql 迁移） |
| 迁移 | Alembic |
| 队列 | Dramatiq + Redis（支持 async actor） |
| 生图 | RunningHub AI App（Fast / Pro） |
| 支付 | Dodo Checkout Sessions + Webhooks |
| 登录（下一步） | Google OAuth + 服务端 Session |

## 环境

```bash
conda activate renderpop
cd /Users/zx/python_workspace/renderpop_server
cp .env.example .env   # 勿覆盖已有密钥

pip install -r requirements-dev.txt
docker compose up -d

alembic upgrade head
python -m scripts.seed_products   # 5 个 SKU（sandbox 已填 Dodo id）

uvicorn app.main:app --reload --port 8000
# 另开终端
dramatiq app.workers.tasks
```

## 本地联调（登录占位）

```bash
# 建用户
curl -s -X POST localhost:8000/api/v1/dev/users \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com"}'

# 发测试积分
curl -s -X POST localhost:8000/api/v1/dev/grant-credits \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"<USER_ID>","amount":100}'

# Pro 生图
curl -s -X POST localhost:8000/api/v1/generations \
  -H 'Content-Type: application/json' \
  -H 'X-Dev-User-Id: <USER_ID>' \
  -H 'Idempotency-Key: demo-1' \
  -d '{"job_type":"PRO_IMAGE","prompt":"a cat","aspect_ratio":"3:4"}'

# 轮询
curl -s -X POST localhost:8000/api/v1/generations/<JOB_ID>/poll \
  -H 'X-Dev-User-Id: <USER_ID>'
```

## 主要 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health/live` | 存活 |
| GET | `/api/v1/me/entitlements` | 会员/额度/积分 |
| POST | `/api/v1/generations` | 创建 Fast/Pro 任务 |
| GET | `/api/v1/billing/products` | 当前环境可售 SKU |
| POST | `/api/v1/billing/checkout-sessions` | Dodo 结账 |
| POST | `/api/v1/billing/webhooks/dodo` | 支付回调 |
| POST | `/api/v1/webhooks/generation/runninghub` | RH 任务回调 |

## 目录

```text
app/
  api/routes/   # health, me, generations, billing, webhooks, dev, auth
  service/      # credit, entitlement, generation, billing, health
  repo/         # 异步 SQL
  models/       # 领域表
  providers/    # runninghub, dodo
  core/         # config, commerce, db, deps, errors
  workers/      # Dramatiq
scripts/seed_products.py
alembic/
docs/
```

## 请求内 Session

`get_db_session`：一请求一 session，成功 commit / 异常 rollback。  
Worker 使用 actor 内短生命周期 session。


dramatiq app.workers.tasks
alembic upgrade head
