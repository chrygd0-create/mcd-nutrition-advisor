# MCP 接入说明

本项目使用**麦当劳中国 MCP Server**（远程托管），未自建任何后端服务。

- 接入地址：`https://mcp.mcd.cn`
- 传输协议：Streamable HTTP
- 协议版本：`2025-06-18`
- 认证方式：请求头 `Authorization: Bearer <MCP_TOKEN>`
- 限流：每 Token 每分钟最多 600 次请求，超限返回 `429`
- Token 申请：https://open.mcd.cn/mcp → 登录 → 控制台 → 激活

配置示例（Token 仅通过环境变量占位符注入）：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer ${MCD_MCP_TOKEN}"
      }
    }
  }
}
```

---

## 使用的 MCP Tools

| Tool 名称 | 用途 | 在本Skill 中的作用 | 必要性 |
|-----------|------|------------------|-------|
| `list-nutrition-foods` | 餐品营养信息列表 | **核心数据源。** 提供能量、蛋白质、脂肪、碳水、钠、钙；所有热量数值的唯一出处 | 必需 |
| `query-meals` | 当前门店可售餐品 | 过滤营养数据中存在但门店实际不售的品项，避免推荐买不到 | 必需 |
| `available-coupons` | 麦麦省可领券 | 为配餐方案叠加可领优惠 | 推荐 |
| `query-store-coupons` | 当前门店可用券 | 精准匹配用户所在门店的券（跨门店券不可用） | 推荐 |
| `calculate-price` | 商品价格计算 | 含优惠券的真实金额计算，输出「省了¥X」 | 推荐 |
| `campaign-calendar` | 当月营销活动日历 | 提示当前进行中的活动（活动期菜品/优惠联动） | 可选 |
| `query-my-account` | 积分账户查询 | 积分兑换建议（麦麦商城商品换算） | 可选 |
| `query-my-coupons` | 我的优惠券 | 核对用户实际持有的券，避免推荐无法使用的优惠 | 可选 |
| `delivery-query-addresses` | 获取用户可配送地址列表 | 外送流程入口：列出用户已存地址（实测已通，返回 contactName/fullAddress/phone 强制展示） | 外送必需 |
| `delivery-create-address` | 新增配送地址 | 用户无历史地址时逐项询问创建 | 外送必需 |
| `delivery-query-stores` | 查询可配送门店 | 按地址筛选能外送的门店 | 外送必需 |
| `query-meals`（orderType=2） | 外送菜单 | 外送菜单与到店不同，配餐前必须按外送菜单重新过滤 | 外送必需 |
| `calculate-price`（orderType=2） | 外送算价 | 自动含配送费与优惠，外送价格唯一依据 | 外送必需 |
| `create-order`（orderType=2） | 创建外送订单 | 复述确认后下单，返回订单与支付链接 | 外送可选 |
| `create-order` | 创建订单 | 配餐确认后的下单闭环（到店场景） | 可选 |

### 团购数据的来源说明（重要）

麦当劳 MCP **没有团购工具**。抖音/美团团购价不在官方接口覆盖范围内，接入第三方平台
（美团开放平台、抖音开放平台）需要企业资质，个人参赛者无法申请。因此本项目：

- **引擎已支持团购数据**：`value` 模式的 `--deals` 参数接受团购 JSON（格式见
  `skill/assets/deals_sample.json`），与官方券同台比价，全部自测通过；
- **数据短期手动维护**：用户把看到的团购价填进 JSON 即可参与比价；
- **长期预留接口**：`load_deals()` 是独立的加载函数，未来接第三方 API 只需替换数据来源，
  引擎与 Skill 定义无需改动；
- **诚实标注**：所有团购路径输出均提示「团购价可能与平台实时价有差异，以平台页面为准」，
  且 `needs_confirmation=true` 强制用户确认后才可执行。

## 明确未使用的 Tools

`cancel-order`（下单后取消属用户主动行为，引导用户在官方 App 操作更稳妥）、
`order-list`、`mall-*`（商城）、`query-party-*`（派对活动）、`draw-lottery`、
`query-meal-assistance`（企业团餐）、`query-survey-coupon`（满意度答券）
等均未纳入本 Skill 的主动流程，避免功能发散。

`query-promotions`（门店满减/满折原始规则）已纳入观察清单：外送场景若 MCP 后续
开放门店级促销数据，可直接喂给配餐引擎替代本地券估算，接口形态已预留。

---

## 调用流程

### 主流程 A：目标感知配餐（plan 模式）

```
Step 1  确认目标参数
        goal ∈ {lose, keep, gain}，默认 lose
        budget_kcal 默认 500，daily_kcal 默认 2000
        ↓
Step 2  并发拉取数据
        ├── list-nutrition-foods   → 营养成分（热量真值来源）
        ├── query-meals            → 当前门店在售菜单
        ├── available-coupons      → 可领券
        └── campaign-calendar      → 进行中活动
        ↓
Step 3  本地计算（nutrition_calculator.py --mode plan）
        目标适配打分 → 热量硬约束筛选 → 槽位组合枚举 → 排序
        ↓
Step 4  算价
        calculate-price（传入推荐组合的餐品编码 + 用户持有的券）
        ↓
Step 5  输出五段式结果
        结论 / 营养构成 / 配餐理由 / 价格对比 / 下一步
```

### 调用时序图

```
用户 ──▶ Skill
         │
         ├──▶ mcd-mcp.list-nutrition-foods ──┐
         ├──▶ mcd-mcp.query-meals         ──┤ 并发
         ├──▶ mcd-mcp.available-coupons    ──┤
         └──▶ mcd-mcp.campaign-calendar    ──┘
                    │
                    ▼
        nutrition_calculator.py（纯本地，无网络）
                    │
                    ▼
         calculate-price（若用户需要真实金额）
                    │
                    ▼
         用户确认 ──▶ create-order（可选）
```

### 关键设计：计算全部在本地完成

配餐的枚举与排序完全在 `nutrition_calculator.py` 内本地执行，不依赖模型逐步推理。
原因有三：

1. **准确性**——组合空间的枚举和排序必须精确，不能让模型心算热量。
2. **限流保护**——MCP 为 600 次/分钟。本Skill 单次请求仅调用 4–6 个 Tool，远低于上限。
3. **成本与延迟**——本地计算是毫秒级，不占用模型的推理预算。

模型只负责：理解自然语言意图 → 调用 Tool 取数 → 调用脚本 → 把结构化结果翻译成人话。

### 主流程 B：热量 × 优惠券联合优化（value 模式）

当用户提到省钱 / 券 / 划算 / 性价比时走此流程，与流程 A 的差别是**券参与组合选择**，而不是算完再叠：

```
Step 1  确认目标参数（同流程 A，另确认排序优先级 economy / balanced / protein）
        ↓
Step 2  并发拉取数据
        ├── list-nutrition-foods   → 营养成分
        ├── query-meals            → 当前门店在售菜单
        ├── available-coupons      → 可领券（可先 auto-bind-coupons 再查）
        └── query-my-coupons       → 用户实际持有的券（避免推荐用不了的券）
        ↓
Step 3  本地联合优化（nutrition_calculator.py --mode value）
        枚举候选组合 → 热量硬约束 → 每个组合算券后实付价 → 按优先级排序
        额外输出凑单提示（加一件小商品过满减门槛后实付更低）
        ↓
Step 4  价格校准（对用户选定的方案调用 calculate-price）
        ↓
Step 5  输出：券前/券后对比 + 营养构成 + 凑单提示 + 下一步
```

关键差异：券若只在最后一步叠加，会错过「换个组合刚好过满减门槛」的解；
value 模式对每个候选组合都计算券后价参与排序，凑单机会单独扫描。

---

## 数据字段兼容

`list-nutrition-foods` 的返回结构在版本迭代中可能有差异，
`nutrition_calculator.py` 的 `load_nutrition()` 已做多结构兼容：

| 逻辑字段 | 兼容的键名 |
|---------|-----------|
| 名称 | `name` / `foodName` / `food_name` / `餐品名称` / `名称` / `productName` |
| 热量 | `energy` / `kcal` / `calories` / `热量` / `能量` |
| 蛋白质 | `protein` / `蛋白质` |
| 脂肪 | `fat` / `脂肪` |
| 碳水 | `carbohydrate` / `carbs` / `碳水化合物` / `碳水` |
| 钠 | `sodium` / `钠` |
| 分类 | `category` / `分类` / `cat` |

同时兼容顶层为数组、`{"foods": [...]}`、`{"data": {"foods": [...]}}` 三种包裹形式。
热量值带 `kcal` 单位后缀或为空时分别按 0 处理，并在输出中标注「暂无官方数据」，不做推测填充。

## 降级策略

| 故障场景 | 处理方式 |
|---------|---------|
| Token 无效 / 过期（401） | 提示用户到控制台重新激活，不重试 |
| 触发限流（429） | 停止调用，提示稍后再试；本地计算部分不受影响 |
| `query-meals` 失败 | 仅用营养数据推荐，并声明「未校验门店在售状态」 |
| `list-nutrition-foods` 失败 | 使用 `assets/nutrition_fallback.json` 降级快照，并在输出顶部标注数据来源与时间 |
| 营养数据中无某品 | 输出「暂无官方数据」，禁止用估算值填充 |

## 安全保障

- Token 仅从环境变量 `MCD_MCP_TOKEN` 读取，仓库中不出现任何真实凭证。
- `scripts/mcd_client.py` 在错误提示中只输出状态码，不回显请求头。
- 涉及资金的 `create-order` / `mall-create-order` / `draw-lottery` 均为不可逆动作，
  Skill 定义中强制要求先复述餐品与金额、获得用户明确确认后才可调用。