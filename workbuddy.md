# workbuddy.md — WorkBuddy 开发过程记录

本项目的全部开发在 WorkBuddy（www.workbuddy.cn）中完成，由参赛者于鹏飞与 WorkBuddy 智能体协作，对话时间 2026-10-10。本文为对话上下文的阶段性整理，用于 WorkBuddy 专项奖励核验。

## 开发时间线（同一会话内完成）

### 阶段 1：参赛方向决策
- 参赛者最初提出两个 Web 系统方案：①点餐+物流实时追踪系统 ②社区美食评价+营养分析工具
- 智能体查证官方规则（github.com/M-China/mcd-developer-innovation-challenge）后指出方向错位：比赛要求的是「基于麦当劳 MCP 的 Skill」，不是 Web 系统；排名以 GitHub Star 数为准
- 发现关键机会点：麦当劳 MCP 自带 `list-nutrition-foods` 工具（官方营养成分，含钠/钙），使「营养分析」方向无需爬取第三方数据

### 阶段 2：Skill 本体开发
- 设计并实现 Skill「麦麦营养顾问」（mcd-nutrition-advisor）：SKILL.md 定义五步工作流 + 硬性约束
- `nutrition_calculator.py`：配餐计算引擎，纯 Python 标准库，无第三方依赖
- `mcd_client.py`：MCP Streamable HTTP 客户端封装（JSON-RPC initialize → tools/call）

### 阶段 3：引擎迭代（全部由真实输出驱动修复）
1. 强制「主食+小食+饮品」导致 500kcal 预算下返回无意义组合 → 小食/饮品改为可选槽位，枚举全部取舍
2. 纯蛋白密度排序导致热量预算大量闲置（485/800）→ 改为「蛋白收益 − 闲置预算×0.05」
3. 零卡饮品霸榜单品推荐 → 正餐候选充足时饮料只保留一杯且排后
4. 分类缺失时用饮品兜底当主食 → 限制为非饮品类最高分

### 阶段 4：热量×优惠券联合优化（value 模式）
- 用户新需求「省钱和热量统统涵盖」→ 引擎新增 `--mode value`，券参与组合选择而非算完再叠
- 凑单反赚检测：加一件小商品过满减门槛后实付更低的机会单独扫描输出
- 修复 `apply_coupons` 三元组解包错位（优惠金额被当作券对象）导致的崩溃
- protein 优先级按克取整分桶再比价，避免「为 0.3g 蛋白多花 10 元」

### 阶段 5：团购跨渠道比价
- 用户新需求「团购的寻找」→ 引擎支持 `--deals` 导入团购数据（抖音/美团），与官方券同台比价
- 语义修正：团购券整套出售不可拆用，套餐未凑齐不生成路径
- 团购路径带整套热量/蛋白/钠 + `needs_confirmation` 强制用户确认（第三方渠道）

### 阶段 6：外送全链路
- 用户新需求「支持外送」→ 接入官方 delivery-* 工具链（地址管理/可配送门店/orderType=2 菜单与算价/下单）
- 实测 `delivery-query-addresses` 通过；写入四条外送硬约束（下单前复述、地址隐私不落文件、外送菜单为准、配送费以官方算价为准）

### 阶段 7：MCP 真实数据联调
- 参赛者在 open.mcd.cn/mcp 申请 Token，配置进 WorkBuddy 连接器（`~/.workbuddy/mcp.json`，streamablehttp）
- `mcd_client.py tools` 实测：35 个官方工具全部可用
- 拉取 `list-nutrition-foods` 真实数据（160 个餐品），适配官方自定义表格格式（`[N]{列名}: + CSV 行`）
- 真实数据三种目标配餐全部通过（减脂 500kcal=烟肉蛋麦满分+麦辣鸡翅+小咖啡 499/500；增肌 900kcal=双层猪柳蛋麦满分+鸡排 53g 蛋白）
- 修复两个真实适配问题：混合文本 JSON 提取、官方数据无分类字段 → 名称启发式分类器

### 阶段 8：投稿准备
- 清理临时文件；发现并删除含云签名（COS AKID）的本地券数据文件，避免敏感信息入库
- 参赛必需四文件齐备：README.md / CONTEST_DECLARATION.md（官方原版未修改）/ MCP_INTEGRATION.md / workbuddy.md

## WorkBuddy 在本项目中的实际作用

1. **规则查证**：WebFetch 拉取活动仓库 README 与 activityGuidelines，确定参赛形态，避免了按错误方向开发
2. **工程实现**：SKILL.md、两个 Python 脚本、网页 Demo、全部文档由会话内生成并本地落盘
3. **质量闭环**：每次引擎修复后回归自测（selftest.py 7 组场景），发现并修复 9 个真实缺陷，全部记录在 README「计算引擎的设计取舍」章节
4. **真实联调**：MCP 客户端调试、官方数据格式适配、Token 配置与敏感信息审查均在会话内完成
5. **本地环境处理**：Windows/PowerShell 编码问题（UTF-8 管道损坏）多次绕行，最终以「脚本自写报告文件」模式稳定验证

## 声明

以上过程真实发生在 2026-10-10 的 WorkBuddy 会话中，参赛者本人提供了需求方向、Token 申请与关键决策确认，代码与文档由 WorkBuddy 辅助生成并经参赛者确认。