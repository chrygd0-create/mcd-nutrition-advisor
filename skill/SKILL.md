---
name: mcd-nutrition-advisor
description: 麦当劳营养顾问。基于麦当劳 MCP 官方营养数据与在售菜单，按用户的减脂/维持/增肌目标和热量预算，自动算出「能吃下的最优套餐」，并叠加当前可领优惠券、进行中活动、积分兑换建议，输出一份可直接下单的组合。当用户提到「麦当劳」「巨无霸热量」「减脂期能吃什么麦」「帮我配一份麦当劳」「麦麦省钱」「今天有什么活动」「积分配什么」「MCP」「麦麦点餐」等关键词时使用本 Skill。
---

# 麦麦营养顾问（McDonald's Nutrition Advisor）

一个把「我想减肥但想吃麦当劳」这个真实矛盾，变成可执行答案的 Skill。

## 核心洞察

麦当劳 MCP 提供了 `list-nutrition-foods`（官方营养成分：能量/蛋白质/脂肪/碳水/钠/钙）。
市面上的「麦当劳热量表」都是过时的第三方爬取数据，而这个 Skill 直接读官方接口 + 当前门店在售菜单，
因此给出的热量与价格永远是**当下真实可点的**，这是它和所有竞品的根本差别。

## 工作流程

### 第1 步：确定目标（信息不足时用默认值，不要反复追问）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `goal` | `lose` | lose 减脂 / keep 维持 / gain 增肌 |
| `daily_kcal` | 2000 | 每日热量预算 |
| `budget_kcal` | 500 | 本餐热量上限（用户常直接给「我今晚只能吃 500 大卡」） |
| `store` | 用户当前门店 | 用 `query-meals` 前需确认，未指定则用默认门店 |

减脂/维持/增肌对应热量系数与蛋白目标：

| goal | 热量系数 | 蛋白系数 | 推荐倾向 |
|------|---------|---------|---------|
| lose | ×0.75 | ×1.6 | 零卡饮品、高蛋白单品、避开高糖高油炸 |
| keep | ×1.0 | ×1.2 | 均衡，控制单餐占比 |
| gain | ×1.15 | ×2.0 | 高热量主食、蛋白优先、避开零卡 |

### 第 2 步：拉取数据（并发调用，一次拿全）

```
list-nutrition-foods   # 官方营养成分，作为唯一热量真值来源
query-meals            # 当前门店在售菜单，用于过滤「有营养数据但门店不卖」
available-coupons      # 可领优惠券
campaign-calendar      # 当月活动，用于叠加「活动期间限定」提示
query-my-account       # 积分余额，用于积分兑换建议（可选）
```

若 `query-meals` 返回的餐品在营养数据中无记录，以营养数据为准并在输出里注明「门店暂无该品」。

### 第 3 步：算配餐（用脚本，不要心算）

调用 `scripts/nutrition_calculator.py`，两种模式按用户意图选择：

**只想知道"能吃什么" → plan 模式**

```bash
python scripts/nutrition_calculator.py \
  --goal lose --budget-kcal 500 \
  --nutrition-json nutrition.json \
  --mode plan
```

**提到省钱 / 券 / 划算 / 性价比 / 团购 → value 模式（热量 + 优惠券 + 团购跨渠道比价）**

```bash
python scripts/nutrition_calculator.py \
  --goal lose --budget-kcal 500 \
  --nutrition-json nutrition.json \
  --coupons coupons.json \
  --deals deals.json \
  --mode value --priority balanced
```

value 模式输出：
- `options`：前 3 个组合，每个组合内枚举「官方券路径」与「团购路径」两条支付方式，取实付最低者
- `payment_paths`：全部支付路径，每条含热量/蛋白/钠与 `needs_confirmation` 标记
- `coupon_tips`：凑单建议 —— 例如「加一份小食过满减门槛，实付反而更低」

团购路径（第三方渠道）有两条硬规则：
1. **套餐没凑齐不生成路径** —— 团购券整套出售不可拆用，组合里必须完整包含团购套餐
2. **`needs_confirmation=true` 的路径必须先向用户复述确认提示**（`confirm_hint` 字段），
   内容含整套清单与总热量，得到确认后才可执行购买

`--priority` 按用户意图选：
- `economy`：就要最便宜（蛋白只作下限约束）
- `balanced`：默认，性价比（每元蛋白含量）优先
- `protein`：蛋白优先，但按克取整分桶后再比价，不为 0.3g 蛋白多花 10 元

输出三段结果：
- `recommended`：满足热量预算 + 蛋白目标的最优单品组合
- `combo`：一份完整套餐（主食 + 小食 + 饮品）的热量构成
- `savings`：可叠加的优惠券与最优组合（满减/套餐价）

### 第 4 步：价格校准（用 `calculate-price`）

本地券估算只是参考。对用户选定的方案调用 `calculate-price` 得到真实应付价，
把「估算 ¥25 → 实付 ¥27」的差异明确告诉用户。**展示给用户的最终价格必须以 calculate-price 为准。**

### 第 5 步：输出格式

固定五段，用表格，不要长篇大论：

1. **一句话结论**：「500 大卡预算下，券后最省的是板烧鸡腿堡 + 无糖可乐，共 482 kcal / 蛋白 28g，实付 ¥16（原价 ¥21）」
2. **营养构成表**（热量、蛋白、脂肪、碳水、钠）
3. **为什么这么配**（1-3 句，绑定用户目标，不要泛泛）
4. **价格对比**（券前/券后、凑单提示，最终以 calculate-price 为准）
5. **下一步**（是否需要 `create-order`，需用户确认）

### 第 6 步：外送流程（用户提到「送上门 / 外卖 / 配送到家」时）

官方 MCP 支持完整外送链路，按顺序走：

```
delivery-query-addresses      # 列出用户已存地址
  ├─ 有地址 → 用户选一个（展示时完整显示联系人/地址/电话，接口要求强制展示）
  └─ 无地址 → delivery-create-address（城市、详细地址、联系人、电话逐项问用户）
        ↓
delivery-query-stores         # 按地址查可外送门店，用户选门店
        ↓
query-meals(orderType=2)      # 外送菜单可能与到店不同，以外送菜单为准重新过滤配餐
        ↓
（回到第 3 步算配餐 → 第 4 步算价，calculate-price 用 orderType=2，自动含配送费）
        ↓
用户明确确认后 → create-order(orderType=2)   # 返回订单详情与支付链接
```

**外送专属硬性约束：**

- **create-order 前必须完整复述**：门店、餐品清单、配送地址、联系人、电话、
  含配送费的总价，得到用户「确认」后才可调用。缺任何一项不得下单。
- **地址隐私**：地址、电话、联系人姓名只允许在当前会话展示，
  禁止写入任何文件、日志、README、Issue 或测试数据。
- **外送菜单以 `query-meals(orderType=2)` 为准**：到店菜单与外送菜单不同，
  配餐结果若在外送菜单中不存在，标注并替换，不硬凑。
- **配送费与起送门槛**：calculate-price(orderType=2) 的返回里已含配送费与优惠，
  以它为准；本地估算的券后价与它冲突时，明确说明差异。

## 硬性约束

- **热量数值必须来自 `list-nutrition-foods` 返回值，禁止自己编。** 若工具未返回某品热量，标注「暂无官方数据」而不是猜。
- **Token 只走环境变量** `MCD_MCP_TOKEN`，任何文件、日志、输出中不得出现真实 Token。
- **下单必须二次确认**。`create-order` / `mall-create-order` / `draw-lottery` 属于不可逆动作，
  在调用前把餐品、价格、支付方式完整复述给用户，得到「确认」再执行。
- **不得承诺医疗/营养效果**。输出附一句：结果仅供参考，餐品信息以官方渠道实时为准。

## 边界

- 不做医疗建议。用户说「糖尿病能不能吃」→ 明确说明非专业建议，建议咨询医师。
- 不代替用户评价优惠券价值判断，只陈述客观折扣金额。
- 单次请求限流保护：MCP 为 600 次/分钟，脚本默认带本地 1s 缓存。

## 文件

- `scripts/nutrition_calculator.py` — 营养预算、套餐、性价比与跨渠道比价引擎（无第三方依赖）
- `scripts/mcd_client.py` — MCP Streamable HTTP 客户端封装，便于脱离 WorkBuddy 独立调试
- `assets/nutrition_fallback.json` — 官方接口不可达时的降级数据（标注为缓存快照）
- `assets/coupons_sample.json` — 优惠券文件格式示例（available-coupons 返回值的简化结构）
- `assets/deals_sample.json` — 团购数据格式示例（抖音/美团渠道，手动维护或未来 API 导入）
- `selftest.py` — 回归自测（无需 Token，跑通 plan/calc/savings/value×团购 七组场景）