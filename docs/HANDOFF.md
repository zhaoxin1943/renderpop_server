# RenderPop Server — 交接总结

> 更新日期：2026-07-20  
> 用途：新会话 / 新窗口先读本文，再动手写代码。  
> 前端与产品文档在：`/Users/zx/web_workspace/renderpop`（尤其 `docs/HANDOFF.md`）。

---

## 1. 新窗口先做什么

```bash
conda activate renderpop
cd /Users/zx/python_workspace/renderpop_server
# 读本文件 + README.md
# 未获用户明确批准前：不要 alembic upgrade、不要 push、不要改共享 Redis 其它前缀
```

相关路径：

| 仓库 | 路径 |
|------|------|
| 本后端 | `/Users/zx/python_workspace/renderpop_server` |
| 前端 / 产品 | `/Users/zx/web_workspace/renderpop` |
| 旧 Dance 参考 | `web_workspace/renderpop/legacy/igrecent-dance/` |

产品域名：`renderpop.app`。首页 `/` = Face Swap AI；`/dance` = Instagram 流量的 AI Dance。

---

## 2. 产品与架构已拍板（不要回退）

| 决策 | 结论 |
|------|------|
| 后端形态 | **独立纯 Python 工程**，不嵌在 Next.js 仓库内 |
| 栈 | FastAPI + SQLModel + **MySQL 8** + Dramatiq + Redis |
| 分层 | `api` → `service` → `repo`；全部 async |
| Session | **一请求一 `AsyncSession`**（`get_db_session`），成功 commit / 异常 rollback |
| DI | FastAPI `Depends`（`app/core/deps.py`），**暂不引入 container.py** |
| 登录（目标） | Google OAuth + 服务端 Session Cookie（HttpOnly） |
| 商业模式 | freemium + 付费生成次数/权益账本；对用户少说「通用 credits」，内部用 entitlement ledger |
| 试用 | 图片换脸可对已验证账户 **一次严格受限试用**；视频/Dance **不免费生成** |
| 支付 MVP | **Dodo Payments**（新业务独立商户，不用旧站中转链路） |
| 支付抽象 | 业务只依赖 `PaymentProvider` + `orders` / `payment_events`，不绑死 Dodo payload |
| Redis | 实例可共享；**所有 key 必须带 `REDIS_PREFIX`**（默认 `renderpop_server_`） |

### 支付讨论结论（2026-07-20）

- **首发唯一提供商：Dodo**（MoR，团队熟悉；全球税/合规压力小于纯 Stripe）。
- **不要 MVP 双写** Stripe + Dodo。
- 用户正在 **重新注册 Dodo 新业务**（旧链路经另一网站中转，已废弃不可用）。
- 表单建议：类别 **SaaS / AI 软件**；阶段 **构建 MVP**；交付 **即时访问**；集成 **API/SDK**；获客 **网站 SEO + 社交媒体**。
- **过审有风险**：Dodo Merchant Acceptance 欢迎 SaaS/AI，但 AI 生成工具需加强审核；政策里出现过 face-swap / deepfake 相关敏感表述。申请描述强调「用户自有素材、创意特效、站内登录交付、禁止 NSFW/非自愿」，避免 deepfake 话术。可邮件 `compliance@dodopayments.com` 预审。
- Config 已预留：`DODO_API_KEY`、`DODO_WEBHOOK_KEY`（`.env` / Settings）。

### 订单状态机（目标）

```text
pending → paid → entitlement_granted → consumed
               └→ refund_pending → refunded
pending → expired | failed
```

生成任务：

```text
created → awaiting_entitlement → queued → running → transferring → succeeded
                              └→ failed → compensated / refunded
```

---

## 3. 工程现状（已完成 / 未完成）

### 已完成

- [x] 工程骨架：FastAPI `app/main.py`、健康检查、分层目录
- [x] `pyproject.toml` + **pinned** `requirements.txt` / `requirements-dev.txt`
- [x] Config（pydantic-settings）、`.env.example`、Redis prefix、Dodo/Google/S3/RunningHub 占位
- [x] Async MySQL engine / `get_db_session`（`app/core/db.py`）
- [x] DI 接线示例：health repo → health service（`app/core/deps.py`）
- [x] Dramatiq RedisBroker + `namespace=REDIS_PREFIX` + AsyncIO middleware
- [x] `app/core/redis_keys.py`：`redis_key(*parts)`
- [x] **领域 models 全套**（见下表）+ mixin base
- [x] **Alembic 初始迁移**（仅生成，**用户 review 后才 upgrade**）：  
  `alembic/versions/20260720_0001_initial_schema.py`
- [x] `UserRepo` 骨架（尚未完整业务）
- [x] 健康检查测试可通过（以本机环境为准）

### 未完成（下一阶段实现顺序建议）

1. **用户 review 后** `alembic upgrade head`（建表）
2. **Google OAuth + Session**（persist `users` / `identities` / `sessions`）
3. **Dodo**：创建 checkout、webhook 验签与幂等、`payment_events`、订单状态、发放 entitlement
4. **Products / SKU** 种子数据与服务端定价（禁止客户端报价格）
5. **权益账本** 扣减 / 失败补偿 / 与 refund 对齐
6. **生成任务**：入队 Dramatiq、RunningHub / face-swap provider、结果进 S3
7. **PaymentProvider 接口** + Dodo 适配器（勿把 Dodo JSON 散落业务层）
8. BaseRepo 可选：默认过滤 `deleted_at IS NULL`（提出过，**未要求则先不做**）

---

## 4. 数据模型约定

### Base mixins（`app/models/base.py`）

| 类型 | 字段 | 用途 |
|------|------|------|
| `IdMixin` | `id` CHAR(36) UUID | 主键 |
| `CreatedAtMixin` | `created_at` | 只写插入时间 |
| `UpdatedAtMixin` | `updated_at` | 更新时间 |
| `SoftDeleteMixin` | `deleted_at` nullable | **可选**软删 |
| `CreatedModel` | id + created_at | 账本 / 事件 / 尝试 |
| `TimestampedModel` | id + created_at + updated_at | 可变业务表 |

**重要：**

- Mixin 字段必须用 `sa_type` + `sa_column_kwargs`，**禁止**在 mixin 里共享同一个 `Column()` 实例（会触发 “column already assigned to …”）。
- Soft delete **只**挂在需要下架/注销的表：当前 **`users` / `products` / `assets`**。
- **不要**给 append-only 表加 soft delete：`identities`、`payment_events`、`entitlement_ledger`、`generation_attempts`、`trial_grants` 等。
- 活行过滤：`Model.deleted_at.is_(None)`；属性 `is_deleted`。

### 表一览

| 表 | Base | 说明 |
|----|------|------|
| `users` | SoftDelete + Timestamped | 账户 |
| `identities` | Created | Google 等外部身份 |
| `sessions` | Timestamped | 服务端会话 |
| `assets` | SoftDelete + Timestamped | 上传/结果素材元数据 |
| `products` | SoftDelete + Timestamped | SKU |
| `orders` | Timestamped | 订单；默认 `payment_provider=dodo` |
| `payment_events` | Created | Webhook 幂等：`uq (provider, event_id)` |
| `entitlements` | Timestamped | 用户权益余额/配额视图 |
| `entitlement_ledger` | Created | 不可改流水 |
| `generation_jobs` | Timestamped | 生成任务 |
| `generation_attempts` | Created | 供应商尝试 |
| `refunds` | Timestamped | 退款 |
| `trial_grants` | Created | 试用发放记录（防刷） |

迁移 revision：`20260720_0001`（文件名 `20260720_0001_initial_schema.py`）。

---

## 5. 目录与分层规则

```text
app/
  api/routes/     # 只调 service；薄路由
  service/        # 业务编排、事务边界
  repo/           # 异步 SQL，不写业务规则
  models/         # SQLModel 表
  schemas/        # API Pydantic DTO
  core/           # config, db, deps, redis_keys
  workers/        # Dramatiq broker + actors（自建短 session）
alembic/
docs/HANDOFF.md   # 本文
```

- 浏览器只打 RenderPop 同源；FastAPI 是支付与生成状态的权威源。
- Worker **无** HTTP session 作用域：用 `worker_session()` 或 actor 内短生命周期 session。
- 价格与 SKU **仅服务端**可信；webhook 必须验签 + 事件幂等。

---

## 6. 本地环境

```bash
conda activate renderpop
cd /Users/zx/python_workspace/renderpop_server
cp .env.example .env   # 用户已填过 .env，勿覆盖真实密钥

# 依赖（固定版本优先）
pip install -r requirements-dev.txt
# 或：pip install -e ".[dev]"   # 若与 pin 冲突，以 reinstall -e 对齐过

docker compose up -d   # 本地 MySQL + Redis（若用）

# 迁移：先 review 再执行
# alembic upgrade head

uvicorn app.main:app --reload --port 8000
# 另终端：dramatiq app.workers.tasks
```

| 变量 | 含义 |
|------|------|
| `DATABASE_URL` | 运行时 async（aiomysql） |
| `DATABASE_URL_SYNC` | Alembic（pymysql） |
| `REDIS_URL` / `REDIS_PREFIX` | 队列与缓存；前缀隔离 |
| `SESSION_SECRET` | 会话签名 |
| `GOOGLE_*` | OAuth（未接） |
| `DODO_API_KEY` / `DODO_WEBHOOK_KEY` | 支付（未接） |
| `RUNNINGHUB_API_KEY` | Dance 供应商 |
| `AWS_*` / `S3_*` | 私有素材 |

**注意：** 曾出现 editable 安装与 `requirements.txt` pin 冲突（cryptography 等）→ 以 `pip install -e ".[dev]"` 或统一 pin 后重装解决。

---

## 7. 建议下一会话实现切片（支付优先时）

用户意向：**继续写代码 / 接入支付**。推荐切片：

### Slice A — 库表落地（需用户确认后）

```bash
alembic upgrade head
# 验证表结构与 soft delete 列
```

### Slice B — Dodo 接入最小闭环

1. Settings 校验 Dodo key（dev 可 mock）。
2. `app/payments/` 或 `app/service/payment/`：
   - `PaymentProvider` Protocol
   - `DodoPaymentProvider`：create checkout、parse webhook
3. Routes：
   - `POST /api/v1/payments/checkout`（需登录后；可先 stub auth）
   - `POST /api/v1/payments/webhooks/dodo`（无 session，验签）
4. Service：创建 pending `Order` → provider checkout → webhook：
   - 写 `payment_events`（幂等）
   - `order` → `paid` → 写 `entitlement_ledger` + 更新 `entitlements`
5. 失败生成补偿策略可先只实现 **退 entitlement**，卡退款后置。

### Slice C — Google 登录（与支付可并行，但 checkout 最终要绑定 user）

- OAuth 回调、建 user/identity、session cookie、`get_current_user` Depends。

### 暂不做

- container.py / 复杂 DI 框架  
- 双支付通道  
- 完整 RunningHub 生成链路（可在权益闭环后再接）  
- 未批准的 `alembic upgrade` 到生产  

---

## 8. 与前端仓库的关系

- 前端：`/Users/zx/web_workspace/renderpop/web`（Next.js 16；**API 有 breaking changes**，改 Next 前读 `web/node_modules/next/dist/docs/`）。
- 前端产品 HANDOFF 仍提示「先讨论再编码」；**后端已按用户指示开工**。两边文档若冲突，以**用户最新口头/本会话决策** + 本文件为准，并回写前端 `docs/`。
- 旧 IGRecent credits / 中转支付 **不复用**；独立 SKU、webhook、订单。

---

## 9. 给新窗口的推荐开场白

```text
请先阅读 /Users/zx/python_workspace/renderpop_server/docs/HANDOFF.md。
conda 环境 renderpop。当前：models + 初始 migration 已写，尚未 upgrade；
支付选定 Dodo 新商户（用户在注册），业务层 PaymentProvider 抽象。
下一步按 HANDOFF §7：确认后 upgrade → Dodo checkout/webhook 最小闭环。
未确认前不要 alembic upgrade，不要改无关重构。
```

---

## 10. 变更日志（后端会话摘要）

| 日期 | 事项 |
|------|------|
| 2026-07-20 | 独立后端脚手架；MySQL；Depends DI；Dramatiq + REDIS_PREFIX |
| 2026-07-20 | requirements pin；修复 editable 与 pin 冲突 |
| 2026-07-20 | 全量 domain models + mixin base + soft delete 策略 |
| 2026-07-20 | 初始 Alembic migration（review only，未 upgrade） |
| 2026-07-20 | 支付选型讨论：MVP = Dodo；用户注册新业务；合规风险已说明 |
| 2026-07-20 | 本文档写入 `docs/HANDOFF.md` |
