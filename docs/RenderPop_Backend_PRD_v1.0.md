# RenderPop 后端产品与技术需求文档（MVP）

> 版本：v1.0  
> 日期：2026-07-21  
> 实施顺序：后端优先  
> 产品范围：首页 AI Image Generator + `/dance` Photo to Dance Video + 统一账户、积分与支付体系

---

## 1. 文档目标

本文档用于指导 RenderPop MVP 后端实现。第一阶段优先搭建可复用的平台底座，使前端后续只需调用稳定接口即可完成：

1. 游客及登录用户的 Fast 免费生图；
2. 登录用户使用积分生成 Pro 图片；
3. 用户选择舞蹈模板、上传照片并使用积分生成 Dance 视频；
4. 月度会员订阅与一次性积分包购买；
5. 多种积分分账、过期、冻结、扣除和失败返还；
6. 生成任务异步执行、状态查询、失败重试与结果存储；
7. 内容安全、风控、限流和后台运营配置；
8. 支付回调、会员续期及发放积分的幂等处理。

本版本只定义 MVP 所需后端能力，不实现模型广场、社区、复杂图片编辑器、邀请返佣、团队账户或无限生成套餐。

---

## 2. 产品原则

### 2.1 用户不选择底层模型

前端只展示：

- `Fast`：免费、每日限额；
- `Pro`：质量更高、消耗积分。

具体供应商和模型仅由后端路由配置决定。更换模型不得要求前端改版，也不得影响历史任务记录。

### 2.2 首页与 Dance 共用资产

以下能力必须统一：

- 用户账户；
- 积分余额与积分账本；
- 会员状态；
- 支付订单；
- 生成任务记录；
- 文件存储；
- 内容安全与风控。

### 2.3 Dance 不强制订阅

非会员可以购买积分包并生成 Dance 视频。会员只是获得月度积分、较高 Fast 限额、优先队列和 Dance 会员价格。

### 2.4 计费采用“冻结—结算”

付费任务提交时冻结积分；任务成功后正式扣除；系统失败时释放冻结积分。所有余额变化必须进入不可变积分账本，不允许直接修改一个简单的余额字段作为唯一依据。

### 2.5 所有商业参数可配置

套餐价格、发放积分、任务消耗、免费限额、积分有效期、会员折扣、注册赠送等均通过后台配置管理。业务代码不得散落硬编码数值。

---

## 3. MVP 首发规则

### 3.1 用户与免费额度

| 用户类型 | Fast 生图额度 | Pro 生图 | Dance 视频 |
|---|---:|---|---|
| 游客 | 2 张/自然日 | 不可用 | 仅浏览模板，不可生成 |
| 免费注册用户 | 5 张/自然日 | 12 Credits/次 | 120 Credits/次 |
| Creator 会员 | 30 张/自然日 | 12 Credits/次 | 100 Credits/次 |
| Pro 会员 | 60 张/自然日 | 12 Credits/次 | 100 Credits/次 |

规则说明：

- 每日额度按系统业务时区的自然日重置，MVP 默认 `UTC`；前端可按用户本地时间展示下次刷新时间；
- Fast 额度不累计；
- 游客额度按“匿名访客 Cookie + IP 风险指纹”共同限制，不能只依赖 IP；
- 用户登录后，当天游客已消耗次数应合并计入登录账户当天额度，避免登录绕过；
- 后台可临时调整额度，不需要发版。

### 3.2 注册赠送

- 新用户首次完成有效注册后赠送 `20 Credits`；
- 有效期 `7 天`；
- 每个用户终身只发放一次；
- 同一高风险设备、支付身份或明显批量注册来源可不发放；
- 赠送积分足够体验至少 1 次 Pro Image，但不足以生成 Dance 视频；
- 发放操作必须幂等，幂等键建议为 `signup_bonus:{user_id}`。

### 3.3 会员套餐

| 套餐 | 建议售价 | 每账期发放 | Fast 限额 | 生成队列 |
|---|---:|---:|---:|---|
| Creator | $9.99/月 | 1,000 Credits | 30/日 | Priority |
| Pro | $19.99/月 | 2,400 Credits | 60/日 | High Priority |

MVP 仅月付，不做年付。会员积分规则：

- 每个成功账期支付后发放一次；
- 允许结转，但“当前可用会员积分”上限为当期发放量的 2 倍；
- 新账期发放时，若发放后超过上限，只发放至上限；
- 发放批次的过期时间建议设为“当前账期结束后再延长一个完整账期”；
- 取消订阅仅关闭自动续费，已付费账期内权益继续有效；
- 退款、拒付或支付撤销按第 10 节处理。

### 3.4 一次性积分包

| 商品 | 售价 | 发放积分 | 有效期 |
|---|---:|---:|---|
| Small Pack | $4.99 | 400 | 12个月 |
| Medium Pack | $9.99 | 900 | 12个月 |
| Large Pack | $19.99 | 2,000 | 12个月 |

### 3.5 积分类型与扣除顺序

| 类型 | 代码建议 | 默认有效期 |
|---|---|---|
| 注册赠送 | `SIGNUP_BONUS` | 7天 |
| 活动赠送 | `PROMO` | 运营配置 |
| 会员月度积分 | `SUBSCRIPTION` | 最多跨一个账期 |
| 单次充值积分 | `PURCHASED` | 12个月 |
| 人工补偿 | `COMPENSATION` | 运营配置，默认90天 |

扣除采用 FEFO（最早过期优先）：

1. 最早到期的赠送/活动积分；
2. 最早到期的会员积分；
3. 最早到期的充值积分；
4. 人工补偿按其实际过期时间参与排序。

退款不是发一笔新的通用积分，而是解除原冻结；如果已经完成扣除后需要返还，应尽可能恢复到原积分批次及原过期时间。原批次已过期时，系统补偿返还可设置最短 7 天有效期，并记录来源。

---

## 4. 系统模块划分

后端建议按领域拆分，MVP 可部署为模块化单体，不要求一开始拆微服务：

| 模块 | 职责 |
|---|---|
| Auth & User | 注册、登录、匿名身份合并、用户状态 |
| Entitlement | 会员状态、当前权益、免费额度 |
| Credit Ledger | 积分批次、可用余额、冻结、扣除、返还、过期 |
| Billing | 商品、结账、订单、支付回调、订阅同步 |
| Generation | 图片/视频任务创建、状态机、队列与结果 |
| Provider Adapter | Fast、Pro、Dance 供应商适配与路由 |
| Asset | 上传凭证、文件元数据、下载权限、生命周期 |
| Safety & Risk | 内容审核、限流、设备/IP 风险、封禁 |
| Admin & Config | 价格、额度、模型路由、模板、任务查询、人工补偿 |
| Observability | 日志、指标、告警、成本与转化数据 |

推荐基础设施：

- 关系型数据库：PostgreSQL；
- 缓存与限流：Redis；
- 异步队列：支持延迟任务、重试和死信队列的队列系统；
- 对象存储：S3 兼容存储；
- CDN：用于生成结果分发；
- 支付：通过 `PaymentProvider` 适配层接入，首个供应商由实施方确定；
- 身份认证：可使用第三方 Auth，也可自建，业务库必须保留内部 `user_id`。

---

## 5. 核心数据模型

以下字段为逻辑模型，实施时可按技术栈调整类型。金额统一使用最小货币单位整数，积分统一使用整数，时间统一存 UTC。

### 5.1 `users`

| 字段 | 说明 |
|---|---|
| `id` | UUID，内部用户主键 |
| `auth_subject` | 外部身份系统唯一标识，可空但需唯一 |
| `email` | 规范化邮箱，可空 |
| `status` | `ACTIVE / SUSPENDED / DELETED` |
| `risk_level` | `LOW / MEDIUM / HIGH / BLOCKED` |
| `country_code` | 注册/最近识别国家，供税务和风控使用 |
| `created_at` / `updated_at` | 时间 |
| `deleted_at` | 软删除时间 |

### 5.2 `anonymous_visitors`

| 字段 | 说明 |
|---|---|
| `id` | 匿名访客 UUID，写入安全 Cookie |
| `first_ip_hash` | 首次 IP 哈希，不保存明文作为永久标识 |
| `device_hash` | 轻量设备风险指纹 |
| `merged_user_id` | 登录后合并到的用户，可空 |
| `created_at` / `last_seen_at` | 时间 |

### 5.3 `plans` 与 `products`

`plans` 表示会员权益定义；`products` 表示可购买商品及支付供应商价格映射。

关键字段：

- `code`：`CREATOR_MONTHLY / PRO_MONTHLY / CREDIT_400 / CREDIT_900 / CREDIT_2000`；
- `product_type`：`SUBSCRIPTION / CREDIT_PACK`；
- `currency`、`amount_minor`；
- `credits_granted`；
- `billing_interval`；
- `provider_price_id`；
- `active`；
- `config_version`。

订单必须保存商品快照，不能只关联当前商品表。

### 5.4 `subscriptions`

| 字段 | 说明 |
|---|---|
| `id` | UUID |
| `user_id` | 所属用户 |
| `plan_code` | 当前套餐 |
| `provider` | 支付供应商 |
| `provider_customer_id` | 外部客户 ID |
| `provider_subscription_id` | 外部订阅 ID，唯一 |
| `status` | 见下方状态 |
| `current_period_start/end` | 当前付费周期 |
| `cancel_at_period_end` | 是否到期取消 |
| `canceled_at` | 取消时间 |
| `ended_at` | 权益实际结束时间 |
| `last_synced_at` | 最近与供应商同步时间 |

订阅状态：

- `INCOMPLETE`：结账未完成；
- `ACTIVE`：权益有效；
- `PAST_DUE`：扣费失败、处于宽限或重试期；
- `CANCELED`：已取消自动续费但可能仍在有效期内；
- `EXPIRED`：权益已结束；
- `UNPAID`：支付失败且不再重试；
- `REFUNDED`：相关订单已全额退款。

是否具有会员权益不能只判断 `status`，应由服务计算：订阅属于用户、未被撤销，且 `now < current_period_end`，并符合宽限期策略。

### 5.5 `orders`

| 字段 | 说明 |
|---|---|
| `id` | 内部订单 UUID |
| `user_id` | 用户 |
| `order_type` | `SUBSCRIPTION / CREDIT_PACK` |
| `status` | `PENDING / PAID / FAILED / REFUNDED / PARTIALLY_REFUNDED / CHARGEBACK` |
| `product_code` | 商品代码 |
| `product_snapshot` | 下单时价格、积分、币种、套餐信息 JSON |
| `amount_minor` / `currency` | 金额与币种 |
| `provider_checkout_id` | 外部结账 ID |
| `provider_payment_id` | 外部付款 ID，唯一 |
| `idempotency_key` | 创建订单幂等键 |
| `paid_at` / `refunded_at` | 时间 |

### 5.6 `credit_grants`

每一笔积分来源形成一个可追溯批次。

| 字段 | 说明 |
|---|---|
| `id` | UUID |
| `user_id` | 用户 |
| `grant_type` | 积分类型 |
| `original_amount` | 原始发放量 |
| `available_amount` | 当前可用量 |
| `reserved_amount` | 当前冻结量 |
| `consumed_amount` | 已消费量 |
| `expires_at` | 过期时间，可空但 MVP 尽量都有 |
| `source_type` | `ORDER / SUBSCRIPTION_PERIOD / SIGNUP / PROMO / ADMIN / REFUND` |
| `source_id` | 来源实体 ID |
| `idempotency_key` | 发放幂等键，唯一 |
| `status` | `ACTIVE / EXPIRED / REVOKED / EXHAUSTED` |

必须满足：

`original_amount = available_amount + reserved_amount + consumed_amount + revoked_amount`

### 5.7 `credit_transactions`

积分不可变流水表，任何余额变化都必须写流水。

| 字段 | 说明 |
|---|---|
| `id` | UUID |
| `user_id` | 用户 |
| `grant_id` | 对应积分批次 |
| `generation_job_id` | 对应任务，可空 |
| `type` | `GRANT / RESERVE / CAPTURE / RELEASE / EXPIRE / REVOKE / ADJUST` |
| `amount` | 正整数，方向由 `type` 表达 |
| `balance_after` | 该批次操作后的可用/冻结快照 JSON |
| `idempotency_key` | 唯一 |
| `metadata` | 原因、管理员、供应商事件等 |
| `created_at` | 时间 |

禁止更新或删除既有流水；纠错通过新增反向流水完成。

### 5.8 `credit_reservations`

记录一次任务从多个积分批次冻结的明细。

| 字段 | 说明 |
|---|---|
| `id` | UUID |
| `user_id` | 用户 |
| `generation_job_id` | 任务，唯一 |
| `total_amount` | 总冻结积分 |
| `status` | `ACTIVE / CAPTURED / RELEASED / PARTIALLY_RELEASED` |
| `expires_at` | 防止永久冻结的兜底到期时间 |
| `pricing_snapshot` | 创建任务时的计价快照 |

另建 `credit_reservation_items` 保存各 `grant_id` 及冻结量。

### 5.9 `daily_usage_counters`

| 字段 | 说明 |
|---|---|
| `subject_type` | `USER / VISITOR / IP_RISK_BUCKET` |
| `subject_id` | 用户、游客或哈希桶标识 |
| `feature` | `FAST_IMAGE` 等 |
| `usage_date` | UTC 自然日 |
| `used_count` | 已使用次数 |
| `limit_snapshot` | 当次规则限额快照 |

唯一键：`subject_type + subject_id + feature + usage_date`。计数增加必须原子化。

### 5.10 `generation_jobs`

| 字段 | 说明 |
|---|---|
| `id` | UUID |
| `user_id` | 登录用户，可空 |
| `visitor_id` | 游客，可空 |
| `job_type` | `FAST_IMAGE / PRO_IMAGE / DANCE_VIDEO` |
| `status` | 任务状态 |
| `prompt` | 用户原始提示词，敏感数据需控制访问 |
| `normalized_request` | 比例、模板、内部参数等 JSON |
| `input_asset_id` | Dance 输入照片，可空 |
| `template_id` | Dance 模板，可空 |
| `pricing_snapshot` | 免费/积分数、会员价格、规则版本 |
| `credit_reservation_id` | 付费任务冻结记录，可空 |
| `provider` / `provider_model` | 实际调用供应商与模型 |
| `provider_task_id` | 外部任务 ID |
| `provider_cost` | 估算/实际成本，最小货币单位 |
| `attempt_count` | 内部尝试次数 |
| `failure_code` | 规范化失败码 |
| `failure_detail` | 内部错误，前端不可直接展示 |
| `submitted_at` / `started_at` / `completed_at` | 时间 |
| `expires_at` | 结果过期/删除时间 |
| `idempotency_key` | 客户端提交幂等键，按用户唯一 |

### 5.11 `generation_outputs`

- `job_id`；
- `asset_id`；
- `width / height / duration_ms`；
- `mime_type`；
- `safety_status`；
- `is_primary`；
- `created_at`。

### 5.12 `assets`

- `owner_user_id / visitor_id`；
- `asset_type`：`INPUT_IMAGE / OUTPUT_IMAGE / OUTPUT_VIDEO / THUMBNAIL`；
- `storage_key`：仅存对象 Key，不存永久公开 URL；
- `mime_type / size / width / height / duration`；
- `sha256`；
- `status`：`UPLOADING / READY / QUARANTINED / DELETED`；
- `retention_until`；
- `created_at / deleted_at`。

下载时由后端校验权限并签发短时效 URL。

### 5.13 `dance_templates`

- `id / slug / title`；
- `preview_asset_id`；
- `provider_template_ref`；
- `duration_seconds`；
- `required_face_count`，MVP 固定 1；
- `credit_cost_free / credit_cost_member`；
- `status`：`DRAFT / ACTIVE / DISABLED`；
- `sort_order`；
- `safety_tags`；
- `config_version`。

### 5.14 `webhook_events`

- `provider`；
- `provider_event_id`，唯一；
- `event_type`；
- `payload_hash`；
- `payload_encrypted` 或最小必要字段；
- `status`：`RECEIVED / PROCESSING / PROCESSED / FAILED / IGNORED`；
- `attempt_count / next_retry_at / processed_at`。

用于支付及异步模型回调幂等。

---

## 6. 积分账本与并发规则

### 6.1 查询余额

返回至少四个数：

- `available_credits`：可立即消费；
- `reserved_credits`：正在任务中冻结；
- `expiring_soon_credits`：未来 7 天内过期；
- `next_expiration_at`：最近一次过期时间。

余额可通过批次聚合获得，也可维护缓存字段提升性能，但批次与流水是最终事实来源。

### 6.2 冻结积分事务

创建付费任务时，在同一数据库事务内完成：

1. 锁定该用户所有符合条件且未过期的积分批次；
2. 按 FEFO 计算批次组合；
3. 若可用余额不足，整个事务回滚并返回 `INSUFFICIENT_CREDITS`；
4. 从各批次 `available_amount` 转入 `reserved_amount`；
5. 创建 reservation、reservation items 和 `RESERVE` 流水；
6. 创建 generation job；
7. 提交事务；
8. 事务成功后再投递异步队列。

必须防止用户同时点击两次导致超扣。推荐使用数据库行锁或按 `user_id` 的短事务 advisory lock，不依赖 Redis 锁作为唯一正确性保障。

### 6.3 正式扣除

任务成功且结果已可靠保存后：

- reservation 从 `ACTIVE` 变为 `CAPTURED`；
- 对应批次从 `reserved_amount` 转入 `consumed_amount`；
- 写 `CAPTURE` 流水；
- job 变为 `SUCCEEDED`；
- 整个过程单事务、可重复调用且只能生效一次。

### 6.4 释放冻结

以下情况释放全部冻结：

- 内容审核拒绝且未调用付费供应商；
- 系统异常导致任务失败；
- 供应商明确失败且产品规则判定可退款；
- 用户在供应商调用前取消；
- 任务长时间未执行并被 watchdog 判定终止。

释放时将原批次 `reserved_amount` 转回 `available_amount`，写 `RELEASE` 流水。若原批次在冻结期间已到期，释放后立即按规则过期；为了避免因系统长时间故障损害用户，可对系统故障返还设置最短 7 天保护期，此规则必须由配置控制并记录。

### 6.5 已产生供应商成本后的用户取消

- 若任务尚未调用供应商：允许取消并全额释放；
- 若已调用供应商：取消请求只表示“不再等待/隐藏结果”，积分正常结算；
- 若供应商自身支持取消且确认未计费，可全额释放；
- API 必须返回是否可取消及预计退款积分，不能让前端自行判断。

### 6.6 冻结超时清理

每 5 分钟扫描：

- reservation 为 `ACTIVE`；
- 已超过 `expires_at`；
- 任务不处于已知可恢复运行状态。

满足条件则将任务标记 `FAILED`，失败码 `RESERVATION_TIMEOUT`，并释放积分。扫描任务需要抢占锁，防止多个实例重复处理。

---

## 7. 生成任务状态机

### 7.1 状态定义

`generation_jobs.status`：

- `CREATED`：请求已写库；
- `MODERATING`：输入审核中；
- `QUEUED`：已进入执行队列；
- `SUBMITTING`：正在调用供应商；
- `PROCESSING`：供应商已接受、等待结果；
- `SUCCEEDED`：结果存储成功，积分已结算；
- `REJECTED`：输入或输出审核拒绝；
- `FAILED`：系统或供应商失败；
- `CANCEL_REQUESTED`：用户申请取消；
- `CANCELED`：确认取消；
- `EXPIRED`：结果已过保存期。

### 7.2 任务主流程

```text
接收请求
→ 鉴权、限流、参数校验
→ 计算权益与价格快照
→ 免费额度原子占用，或付费积分冻结
→ 创建任务
→ 输入内容审核
→ 进入对应优先级队列
→ 选择供应商路由
→ 调用供应商
→ 轮询或等待回调
→ 下载并校验结果
→ 输出内容审核
→ 写入对象存储及结果表
→ 结算积分
→ 标记成功
```

任一步失败都必须落一个稳定的 `failure_code`，并由统一策略决定：自动重试、切换供应商、退款或人工介入。

### 7.3 失败分类

| 类型 | 示例 | 自动重试 | 积分处理 |
|---|---|---:|---|
| 用户输入错误 | 空 Prompt、图片不合规 | 否 | 不扣/释放 |
| 内容安全拒绝 | 违规文本、违规输入图 | 否 | 不扣/释放 |
| 临时供应商错误 | 429、5xx、超时 | 是 | 保持冻结 |
| 永久供应商错误 | 参数拒绝、模板失效 | 视情况 | 最终失败后释放 |
| 内部系统错误 | 存储失败、队列异常 | 是 | 最终失败后释放 |
| 输出审核拒绝 | 模型产生违规输出 | 可重新生成一次 | 最终无合规结果则释放 |
| 用户主观不满意 | 画面不符合想象 | 否 | 正常扣除 |

### 7.4 重试规则

- 供应商提交请求必须携带内部任务 ID 作为幂等标识（若供应商支持）；
- 单个供应商建议最多 2 次瞬时错误重试，指数退避；
- 是否切换备用供应商由路由配置决定；
- 重试不能再次冻结或扣除积分；
- 在无法确认第一次调用是否成功时，禁止盲目重新调用非幂等生成接口；应先按外部任务 ID 查询；
- 达到最大重试次数进入死信队列，并触发告警和释放/人工处理策略。

---

## 8. 生成服务具体规则

### 8.1 Fast Image

输入：

- `prompt`：建议 1–2,000 字符；
- `aspect_ratio`：`1:1 / 3:4 / 4:3`；
- `client_request_id`。

规则：

- 游客与登录用户均可用；
- 不消耗积分，但原子占用每日次数；
- 默认一次请求输出 1 张；
- 任务因系统错误最终失败时，应返还一次免费额度；
- 内容审核拒绝不应消耗免费额度，若额度已预占则回滚；
- 用户主观不满意、主动重新生成均视为新请求并消耗新额度；
- 供应商和参数由 `FAST_IMAGE` 路由配置决定。

### 8.2 Pro Image

规则：

- 必须登录；
- 首发价 `12 Credits`；
- 一次任务输出 1 张；
- 默认支持 `1:1 / 3:4 / 4:3`；
- 不向用户暴露 GPT Image 或其他模型名；
- 注册赠送积分可以支付；
- 创建任务时保存价格、会员状态、路由版本的快照。

### 8.3 Dance Video

输入：

- `template_id`；
- `input_asset_id`；
- `client_request_id`；
- 用户确认拥有照片使用权及人物已成年（记录确认版本和时间）。

创建前校验：

- 用户必须登录；
- 模板必须为 `ACTIVE`；
- 输入仅允许支持的图片 MIME，校验真实文件头；
- 文件大小、分辨率在配置范围内；
- 只检测到一个主要人脸；
- 人脸尺寸、清晰度、遮挡程度达到最低要求；
- 输入内容通过安全审核；
- 非会员消耗 `120 Credits`，有效会员消耗 `100 Credits`；
- 价格取创建瞬间模板与会员权益快照。

结果规则：

- 输出视频生成缩略图；
- 用户可查看状态、播放、下载；
- 生成成功后正常扣除；
- 重新生成属于新任务，重新计费；
- 供应商失败或输出审核失败且无法自动补生成时，全额释放积分。

MVP 不做人脸身份库，不允许把一次上传自动用于其他模板任务；用户发起新任务时可显式选择复用仍在保留期内的本人素材。

---

## 9. 免费额度、限流与反滥用

### 9.1 多层限流

至少实施：

- API 网关 IP 级短周期限流；
- 用户/游客级生成频率限制；
- 每日 Fast 配额；
- 并发任务限制；
- 注册、登录、上传、支付会话分别限流；
- 高风险来源验证码或拒绝服务。

建议首发并发：

- 游客：同时最多 1 个生成任务；
- 免费用户：同时最多 1 个生成任务；
- Creator：同时最多 2 个；
- Pro：同时最多 3 个。

这些数值均为配置项。

### 9.2 游客识别

首次访问签发不可由前端伪造的匿名标识 Cookie：

- `HttpOnly`、`Secure`、`SameSite=Lax`；
- 服务端存访客 ID；
- 结合 IP 哈希、设备风险信号检测 Cookie 重置；
- 不使用强侵入式指纹作为唯一身份依据；
- 隐私政策需说明反滥用用途。

### 9.3 登录合并

游客登录后：

- 绑定 `anonymous_visitor.merged_user_id`；
- 当天 Fast 使用量取用户计数与游客计数的合理合并值，默认为两者相加后不超过可审计事实；
- 游客生成历史可选择迁移至账户；
- 不迁移任何积分，因为游客没有积分资产；
- 合并操作必须幂等。

### 9.4 风险处置

风险等级行为：

- `LOW`：正常；
- `MEDIUM`：验证码、降低免费频率；
- `HIGH`：禁止注册赠送积分、仅允许付费或人工复核；
- `BLOCKED`：禁止生成和支付新订单，保留申诉入口。

---

## 10. 支付、订阅与退款

### 10.1 创建结账会话

后端必须：

1. 鉴权；
2. 校验商品处于可售状态；
3. 创建 `PENDING` 订单并保存商品快照；
4. 调用支付供应商创建 Checkout；
5. metadata 写入内部 `order_id`、`user_id`、`product_code`；
6. 返回受控的结账 URL 或会话 Token；
7. 使用客户端 `idempotency_key` 防止重复创建。

前端跳转成功页不代表支付成功，权益只能由已验证的服务端回调发放。

### 10.2 Webhook 通用要求

- 验证签名、时间戳和来源；
- 先写 `webhook_events` 再处理；
- `provider_event_id` 唯一；
- 重复回调返回成功但不得重复发积分；
- 乱序事件通过事件时间、订阅版本和供应商状态查询解决；
- 回调处理失败进入重试队列；
- 不在 Webhook HTTP 请求中执行耗时操作。

### 10.3 积分包支付成功

在一个业务事务内：

- 将订单改为 `PAID`；
- 创建 `PURCHASED` 积分批次；
- 写 `GRANT` 流水；
- 发放幂等键：`credit_pack:{provider_payment_id}`；
- 记录 `paid_at`。

### 10.4 会员首次开通与续费

每个成功付款账期：

- 创建或更新订阅；
- 创建本账期会员积分批次；
- 发放时执行 2 倍结转上限；
- 发放幂等键：`subscription_credit:{provider_invoice_id}`；
- 更新当前周期；
- 权益缓存失效。

升级/降级在 MVP 可采用简化规则：

- 用户在当前账期结束后生效；
- 不做账期中按比例补差与补发；
- 若支付供应商默认支持立即升级，后端第一版应关闭或明确实现差额与积分补发规则后再开放。

### 10.5 扣费失败

- 订阅进入 `PAST_DUE`；
- 可配置最多 3 天宽限期；
- 宽限期内保留会员身份，但不提前发放新账期积分；
- 支付最终失败后，状态变为 `UNPAID/EXPIRED`，会员权益结束；
- 已购买积分包不因会员结束而失效，其自身有效期不变。

### 10.6 退款与拒付

#### 积分包退款

- 若所购积分完全未使用：撤销该批次并退款；
- 若部分已使用：MVP 默认不支持自动部分退款，转人工处理；
- 若发生拒付：将相关未使用积分撤销，账户标记风险；若已消费导致负资产，不把余额直接改负，而记录 `credit_debt` 或风险欠款，限制继续生成。

#### 会员退款

- 撤销对应账期未使用的会员积分；
- 会员权益按退款政策立即结束或在账期末结束，需保持配置一致；
- 已消费积分的退款默认人工复核；
- 所有撤销写 `REVOKE` 流水，不删除原发放记录。

---

## 11. API 设计

接口统一前缀建议 `/api/v1`。返回包含 `request_id`，错误采用稳定业务码。所有创建类接口支持 `Idempotency-Key` 请求头。

### 11.1 当前用户与权益

#### `GET /api/v1/me`

返回：基本账户、会员摘要、风险限制（仅返回前端需要的信息）。

#### `GET /api/v1/me/entitlements`

示例：

```json
{
  "plan": "CREATOR",
  "membership_active": true,
  "current_period_end": "2026-08-21T00:00:00Z",
  "fast_image": {
    "daily_limit": 30,
    "used": 4,
    "remaining": 26,
    "resets_at": "2026-07-22T00:00:00Z"
  },
  "credits": {
    "available": 860,
    "reserved": 100,
    "expiring_soon": 20,
    "next_expiration_at": "2026-07-28T10:00:00Z"
  }
}
```

#### `GET /api/v1/me/credit-transactions?cursor=...`

返回用户可理解的积分记录。不得暴露内部供应商或敏感风控信息。

### 11.2 价格预估

#### `POST /api/v1/generations/quote`

请求：

```json
{
  "job_type": "DANCE_VIDEO",
  "template_id": "uuid"
}
```

响应：

```json
{
  "credits_required": 100,
  "membership_discount_applied": true,
  "available_credits": 860,
  "can_generate": true,
  "pricing_version": "2026-07-21.1"
}
```

Quote 只用于展示，最终价格以创建任务时后端重新计算并写入的快照为准。

### 11.3 上传

#### `POST /api/v1/assets/upload-intents`

请求包含用途、文件名、MIME、大小、可选哈希。响应短时效直传凭证和 `asset_id`。

#### `POST /api/v1/assets/{asset_id}/complete`

服务端检查对象实际存在、大小及类型，进入安全扫描，之后状态才可变为 `READY`。

### 11.4 创建生成任务

#### `POST /api/v1/generations`

Fast/Pro 示例：

```json
{
  "job_type": "PRO_IMAGE",
  "prompt": "A cinematic portrait in soft window light",
  "aspect_ratio": "3:4",
  "client_request_id": "uuid"
}
```

Dance 示例：

```json
{
  "job_type": "DANCE_VIDEO",
  "template_id": "uuid",
  "input_asset_id": "uuid",
  "consent": {
    "terms_version": "dance-consent-v1",
    "owns_rights": true,
    "adult_subject_confirmed": true
  },
  "client_request_id": "uuid"
}
```

成功返回 `202 Accepted`：

```json
{
  "job_id": "uuid",
  "status": "MODERATING",
  "credits_reserved": 100,
  "estimated_wait_seconds": 45,
  "created_at": "2026-07-21T08:00:00Z"
}
```

常见错误：

- `AUTH_REQUIRED`；
- `DAILY_LIMIT_REACHED`；
- `INSUFFICIENT_CREDITS`；
- `CONCURRENT_JOB_LIMIT`；
- `INVALID_ASSET`；
- `FACE_NOT_DETECTED`；
- `MULTIPLE_FACES_DETECTED`；
- `TEMPLATE_UNAVAILABLE`；
- `CONTENT_REJECTED`；
- `ACCOUNT_RESTRICTED`。

### 11.5 查询与取消任务

#### `GET /api/v1/generations/{job_id}`

仅任务所有者可访问。返回前端状态、进度、可否取消、结果和友好错误。

#### `GET /api/v1/generations?type=&status=&cursor=`

生成历史，游标分页。

#### `POST /api/v1/generations/{job_id}/cancel`

返回：

```json
{
  "accepted": true,
  "status": "CANCELED",
  "credits_to_release": 100
}
```

若已产生费用：

```json
{
  "accepted": false,
  "status": "PROCESSING",
  "credits_to_release": 0,
  "reason": "PROVIDER_ALREADY_STARTED"
}
```

### 11.6 Dance 模板

#### `GET /api/v1/dance/templates`

仅返回 `ACTIVE` 模板、预览信息、时长和当前用户价格。

#### `GET /api/v1/dance/templates/{slug}`

返回单模板详情和上传要求。

### 11.7 商品与结账

#### `GET /api/v1/billing/products`

按用户地区返回可售商品。价格由服务端提供，前端不得硬编码。

#### `POST /api/v1/billing/checkout-sessions`

```json
{
  "product_code": "CREATOR_MONTHLY",
  "success_url": "https://renderpop.app/billing/success",
  "cancel_url": "https://renderpop.app/pricing"
}
```

后端必须校验回跳域名白名单，防止开放重定向。

#### `POST /api/v1/billing/customer-portal`

为当前用户创建短时效订阅管理入口。

#### `GET /api/v1/billing/orders?cursor=`

返回订单历史。

### 11.8 Webhook

- `POST /api/v1/webhooks/payment/{provider}`；
- `POST /api/v1/webhooks/generation/{provider}`。

Webhook 路由不使用用户登录鉴权，必须使用供应商签名验证、事件幂等和严格限流。

---

## 12. 内容安全与合规

### 12.1 通用审核链路

- Prompt 文本审核；
- 输入图片审核；
- 输出图片/视频审核；
- 命中禁止项时不向用户返回生成资产；
- 保存最小必要审核结果、规则版本和原因代码；
- 不在普通日志中打印完整 Prompt、上传图片 URL 或支付隐私信息。

### 12.2 Dance 特别规则

MVP 至少禁止：

- 未成年人或年龄无法合理确认的色情化内容；
- 非自愿私密内容；
- 明显公众人物滥用；
- 裸露或露骨色情模板及输入；
- 多人照片导致身份不明确；
- 用户没有使用权的照片。

用户每次首次使用或条款升级后需确认：

- 照片中的人物为成年人；
- 用户拥有使用照片和肖像的权利；
- 不用于骚扰、欺诈、诽谤或非自愿内容。

同意记录包括 `user_id`、条款版本、时间、IP 风险摘要。是否加入可见 AI 水印由产品决定，但后端应预留输出后处理和 provenance 元数据能力。

### 12.3 数据保留

建议 MVP 默认值：

- 游客 Fast 结果：24 小时；
- 免费注册用户结果：7 天；
- 会员结果：30 天；
- Dance 输入照片：任务结束后 24 小时删除，除非用户明确选择保存；
- Dance 输出：30 天；
- 订单和积分财务记录：按法律与会计要求长期保留；
- 软删除用户的生成资产按计划清除，财务流水匿名化保留。

保留期由配置决定，前端需明确告知。对象存储删除必须由定时任务执行并可审计。

---

## 13. 后台管理能力

MVP 后台至少包含：

### 13.1 用户查询

- 按 user ID、邮箱、支付客户 ID 查询；
- 查看会员、余额、积分批次、订单和任务；
- 暂停/恢复账户；
- 查看风险等级；
- 禁止直接编辑余额数字。

### 13.2 积分调整

管理员只能通过“发放补偿”或“撤销批次”操作：

- 必填原因；
- 必填工单/备注；
- 记录管理员 ID；
- 使用幂等键；
- 写完整流水；
- 高额调整可预留双人审批。

### 13.3 商业配置

- 商品上下架；
- 任务积分价格；
- 会员折扣；
- 免费日额度；
- 注册赠送数量与有效期；
- 积分批次有效期；
- 并发限制；
- 配置变更保留版本与审计记录。

价格变更只影响变更后新建任务。历史任务必须使用 `pricing_snapshot`。

### 13.4 模型与模板配置

- Fast/Pro/Dance 主供应商和备用供应商；
- 超时、重试次数、熔断开关；
- Dance 模板上下架、排序、预览和价格；
- 紧急关闭某类生成服务；
- 不应通过普通配置界面展示供应商密钥。

### 13.5 任务处置

- 按状态、类型、用户、供应商、错误码查询；
- 对可安全重试的失败任务触发重试；
- 对冻结异常任务释放积分；
- 手工操作必须幂等且保留审计；
- 禁止将失败任务直接改成成功而没有输出及结算记录。

---

## 14. 定时任务与异步任务

| 任务 | 建议频率 | 职责 |
|---|---:|---|
| Reservation Watchdog | 每5分钟 | 释放超时冻结，关闭僵尸任务 |
| Provider Job Poller | 视供应商 | 查询无回调任务状态 |
| Credit Expiration | 每小时 | 过期积分批次并写流水 |
| Subscription Reconciliation | 每日 | 与支付供应商核对订阅状态 |
| Asset Retention Cleanup | 每小时/每日 | 删除过期输入与结果文件 |
| Webhook Retry | 每分钟 | 重试失败回调处理 |
| Cost Aggregation | 每小时 | 聚合模型成本、收入和毛利 |
| Daily Quota Maintenance | 无需清零 | 以日期分区/键自然切换，可清理旧记录 |

所有定时任务都必须支持多实例安全执行，并记录每次执行结果。

---

## 15. 可观测性与核心指标

### 15.1 技术指标

- API P50/P95/P99 延迟与错误率；
- 队列长度和等待时间；
- 各供应商成功率、超时率、429/5xx；
- 生成总耗时；
- 僵尸任务数；
- 积分冻结超过阈值的数量；
- Webhook 失败和积压；
- 文件上传/存储失败率。

### 15.2 业务指标

- 首页首次生成率；
- Fast 生成成功率及每日成本；
- 游客转注册率；
- 注册赠送积分使用率；
- Fast → Pro 点击与生成转化；
- `/dance` 模板查看 → 上传 → 付费 → 生成成功漏斗；
- 积分包/会员购买比例；
- 每种任务平均收入、模型成本、综合成本、毛利率；
- 每 1,000 次免费生成带来的付费收入；
- 退款率、拒付率和滥用率。

事件命名建议统一为：

- `generation_requested`；
- `generation_rejected`；
- `generation_started`；
- `generation_succeeded`；
- `generation_failed`；
- `credits_reserved/captured/released`；
- `checkout_started`；
- `payment_succeeded/failed/refunded`；
- `subscription_started/renewed/canceled/expired`。

事件不得包含完整 Prompt、原始照片 URL 或敏感支付数据。

---

## 16. 安全要求

- 所有用户资源接口执行对象级权限校验，不能只依赖不可猜测 UUID；
- 上传使用短时效签名，限制 Key 前缀、大小和 MIME；
- 下载 URL 短时效，禁止永久公开原图；
- API 密钥及支付密钥存 Secret Manager，不入库、不入日志；
- Webhook 必须验证签名；
- 支付 success URL 不作为权益依据；
- 后台需要管理员鉴权、最小权限和审计日志；
- 对 Prompt、邮箱、IP 等敏感字段设置访问控制和保留期；
- 数据库备份、恢复演练和关键表 Point-in-time Recovery；
- 生产环境禁止通过接口返回堆栈和供应商原始错误；
- 高成本接口必须有预算熔断：按小时/日成本超过阈值自动降级或暂停免费生成。

---

## 17. 一致性与幂等清单

以下操作必须幂等：

1. 用户注册赠送积分；
2. 创建订单/结账会话；
3. 支付成功发放积分包；
4. 每个会员账期发放积分；
5. 创建生成任务；
6. 冻结积分；
7. 成功结算积分；
8. 失败释放积分；
9. 供应商回调处理；
10. 任务取消；
11. 资产删除；
12. 管理员补偿。

数据库至少设置以下唯一约束：

- `credit_grants.idempotency_key`；
- `credit_transactions.idempotency_key`；
- `orders.idempotency_key + user_id`；
- `orders.provider_payment_id`；
- `subscriptions.provider_subscription_id`；
- `webhook_events.provider + provider_event_id`；
- `generation_jobs.user_id/visitor_id + idempotency_key`；
- `credit_reservations.generation_job_id`；
- `daily_usage_counters` 组合键。

---

## 18. 关键验收用例

### 18.1 免费额度

1. 游客当天成功生成 2 张后，第 3 次返回 `DAILY_LIMIT_REACHED`；
2. 游客生成 1 张后登录，不能重新获得完整 5 张之外的不合理额外额度；
3. Fast 因系统失败且未返回结果，免费次数自动返还；
4. 两个并发请求争夺最后一个免费额度，只能有一个成功创建任务；
5. UTC 跨日后额度恢复，旧记录无需手工清零。

### 18.2 积分与任务

1. 用户有 20 注册积分，提交 12 积分 Pro 任务后：可用 8、冻结 12；
2. 任务成功后：可用 8、冻结 0、已消费 12；
3. 任务系统失败后：可用恢复 20、冻结 0；
4. 同一成功回调重复 10 次，只扣一次；
5. 用户同时创建两个 12 积分任务且仅有 20 分，只允许一个成功冻结；
6. 用户拥有多个积分批次时按最早过期顺序冻结；
7. 重新生成创建新任务并再次计费；
8. 任务进入供应商后取消，不自动退款；
9. 供应商调用前取消，全额释放；
10. 历史任务在后台调价后仍按原价格快照结算。

### 18.3 会员

1. Creator 首次付款成功，只发 1,000 积分一次；
2. 重复支付回调不重复发放；
3. 续费成功后按结转上限计算发放；
4. 用户取消订阅后，当前账期内仍享受会员价和 Fast 额度；
5. 账期结束且未续费后，Dance 恢复非会员价格；
6. 会员到期不影响仍有效的充值积分；
7. `PAST_DUE` 不提前发下一期积分。

### 18.4 积分包与退款

1. 支付成功后发放准确积分和有效期；
2. 成功页打开但 Webhook 未到时，不提前发积分；
3. 全额退款撤销未使用积分并写撤销流水；
4. 已部分消费的退款转人工处理；
5. 拒付后账户进入风险限制，不能继续消耗有争议资产。

### 18.5 Dance

1. 非登录用户不能创建任务；
2. 模板下架后不可新建，但历史任务仍可查询；
3. 多人脸、无人脸、文件伪装 MIME 均被拒绝且不扣分；
4. 会员创建时冻结 100，非会员冻结 120；
5. 创建后会员到期不改变已冻结任务价格；
6. 输出审核拒绝且补生成失败时全额释放；
7. 用户只能访问自己的输入图和输出视频。

### 18.6 安全与幂等

1. 修改 job UUID 访问他人任务返回 404/无权限；
2. 伪造 Webhook 签名不产生任何权益；
3. 相同 `Idempotency-Key` 和相同请求返回同一任务；
4. 相同 Key 但不同请求体返回 `IDEMPOTENCY_CONFLICT`；
5. 管理员积分调整有原因、操作者和完整流水。

---

## 19. 实施阶段划分

### Phase 1：账户、积分和配置底座

- 用户与匿名访客；
- 权益计算；
- 积分批次、流水、冻结与结算；
- 每日额度；
- 商品与商业配置；
- 单元测试和并发测试。

完成标准：在无真实模型、无真实支付的情况下，可通过测试接口完整模拟赠送、冻结、成功扣除、失败释放、过期和并发争抢。

### Phase 2：生成任务平台

- `generation_jobs` 状态机；
- 队列、worker、重试、watchdog；
- Provider Adapter 接口；
- 对象存储和上传；
- Mock Provider；
- Fast/Pro 图片真实供应商接入。

完成标准：Fast 和 Pro 可端到端生成；付费任务不发生重复扣费，失败自动返还。

### Phase 3：支付与会员

- 商品列表；
- Checkout；
- Webhook；
- 积分包；
- 会员首次开通、续费、取消、到期；
- 支付对账任务；
- 客户门户。

完成标准：测试环境完成购买、续费、重复回调、取消和退款全链路。

### Phase 4：Dance

- 模板管理；
- 输入图片上传；
- 人脸与安全检测；
- Dance Provider；
- 视频结果、缩略图、下载；
- 会员/非会员差异定价；
- 同意记录与数据清理。

完成标准：从模板选择到视频下载完整跑通，失败释放积分，所有输入输出具备访问控制。

### Phase 5：后台、风控和上线保障

- 管理后台；
- 成本仪表盘；
- 预算熔断；
- 告警；
- 数据删除；
- 压测、安全测试和恢复演练。

---

## 20. 后端开工前只需确定的外部参数

以下内容不阻塞账户、账本和任务框架开发，可先使用 Adapter 与 Mock 实现：

1. 身份认证服务选型；
2. 支付供应商及商户地区；
3. Fast 图片供应商与实际单次成本；
4. Pro 图片供应商的具体 API 与输出规格；
5. Dance 视频供应商、单次成本、回调/轮询方式；
6. 对象存储和 CDN；
7. 内容审核供应商；
8. 生成历史的最终保留期；
9. 业务日是否始终按 UTC，还是未来按用户时区计算；
10. Dance 是否强制添加 AI 标识或水印。

上述选型全部通过接口隔离，不应改变核心数据模型和积分规则。

---

## 21. MVP 明确不做

- 无限生成；
- 周会员、年会员、终身会员；
- 团队账户与共享积分；
- 邀请奖励、返佣、签到；
- 用户间积分转赠；
- 多币种钱包；
- 模型选择器；
- 批量生成；
- 社区发布、点赞、关注；
- 高级工作流和节点编辑器；
- 复杂的按比例升级/降级计费；
- 自动处理所有部分退款争议。

---

## 22. 最终交付标准

后端 MVP 被视为可交付，必须同时满足：

1. Fast、Pro、Dance 三类任务使用同一任务框架；
2. 免费额度无法通过普通并发或重复请求绕过；
3. 所有积分均可追溯到批次、来源和流水；
4. 付费任务不存在重复扣除，系统失败可自动释放；
5. 支付成功、订阅续费和 Webhook 重放均具备幂等性；
6. 历史任务使用价格快照，不受后续调价影响；
7. 用户不能访问他人的任务和资产；
8. 模型供应商可替换，不暴露给前端；
9. 后台能查询用户、订单、积分和失败任务，但不能无痕修改余额；
10. 可观测模型成本、免费获客成本、付费收入及主要转化漏斗。

