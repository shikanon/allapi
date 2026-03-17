# 页面设计规格（Desktop-first）

## 全局设计（适用于所有页面）

### Layout
- 采用「顶部导航 + 居中内容容器」的结构。
- 内容最大宽度：1200px；左右留白自适应；主体区使用 CSS Grid + Flex 混合。
- 断点建议：
  - Desktop：≥1024px（默认）
  - Tablet：768–1023px（容器缩窄、表格变紧凑、部分字段折叠到详情抽屉）
  - Mobile：<768px（表格改卡片列表、调试表单分段折叠）

### Meta Information
- 默认 Title 模板：`{页面名} - 视频任务控制台`
- 默认 Description：`使用 Token 登录，查看计费/用量记录并调试视频任务 API。`
- Open Graph：
  - og:title 同 Title
  - og:description 同 Description
  - og:type: website

### Global Styles（Design Tokens）
- 背景色：`#0B1220`（深色）/ 内容卡片：`#111B2E`
- 主色（Accent）：`#3B82F6`
- 成功：`#22C55E`；警告：`#F59E0B`；错误：`#EF4444`
- 字体：系统字体栈（中英混排清晰）
- 字号层级：
  - H1 24px / 600
  - H2 18px / 600
  - 正文 14px / 400
  - 辅助 12px / 400
- 按钮：
  - Primary：主色背景 + 白字；hover 加深 8%；disabled 降低透明度
  - Secondary：描边按钮；hover 背景轻微提亮
- 链接：主色，hover 下划线
- 代码/JSON 区域：等宽字体，深色 code block，支持一键复制

### 交互与状态规范
- 全局 Loading：页面级骨架屏 + 按钮内 loading
- 错误提示：表单字段内联 + 页面顶部 Toast（可关闭）
- 空状态：展示“暂无数据/请先创建任务/请输入 task_id”等文案与引导按钮
- 复制：复制成功 Toast

---

## 页面 1：登录页（/login）

### Meta
- Title：`登录 - 视频任务控制台`

### Page Structure
- 单列居中卡片布局（Card 480–560px 宽）。

### Sections & Components
1) 顶部品牌区
- Logo/产品名（左对齐或居中）
- 副标题：说明用途（计费/用量 + 视频任务 API 调试）

2) Token 登录卡片
- 表单字段：
  - Token 输入框（支持粘贴；可选“显示/隐藏”）
- 操作按钮：
  - 「登录」Primary
  - 「清空」Secondary
- 校验与反馈：
  - 基础校验：非空；可选长度/前缀规则（按你的 token 约定）
  - 登录失败：展示接口错误信息（如 401/403）

3) 登录态提示（可选，若本地已有 Token）
- 提示“检测到已保存 Token”
- 按钮：
  - 「进入控制台」
  - 「退出/清除 Token」

### Responsive
- Mobile：卡片宽度自适应；按钮改为纵向堆叠。

---

## 页面 2：控制台页（/console）

### Meta
- Title：`控制台 - 视频任务控制台`

### Page Structure
- 顶部导航（Top Nav）+ 内容区（Content）。
- 内容区使用 Tab 分区：计费概览 / 使用记录 / 视频任务调试。

### Sections & Components

#### A. Top Nav（全局）
- 左侧：产品名 + 环境标识（可选：Prod/Sandbox）
- 右侧：
  - 当前 Token 摘要展示（如前 6 后 4，中间省略）
  - 「退出登录」按钮

#### B. Tab：计费概览
1) KPI 卡片区（Grid 3–4 列）
- 卡片示例（以接口返回为准）：余额/已用额度/当期账单/结算周期
- 右上角：刷新按钮（显示最后更新时间）

2) 明细信息区（描述列表）
- 展示更多计费字段（如计费单位、单价信息等，若接口提供）

状态
- Loading：KPI 骨架屏
- 空/无权限：提示并引导检查 Token

#### C. Tab：使用记录
1) 筛选栏（水平排列）
- 时间范围：起始日期、结束日期
- 「查询」Primary、「重置」Secondary、「刷新」

2) 记录表格（Table）
- 列建议（按接口字段裁剪）：时间、接口/资源类型、消耗、状态、请求 ID
- 行操作：
  - 「查看详情」：右侧抽屉展示完整字段 JSON + 可复制

3) 详情抽屉（Drawer）
- 顶部：记录摘要
- 内容：Key-Value 列表 + 原始 JSON（代码块）+ 复制按钮

#### D. Tab：视频任务调试（创建/查询/取消）
采用「左表单右结果」的双栏布局（Desktop），提升调试效率。

1) 左侧：调试表单区（Stacked Sections）
- 子 Tab 或 Accordion 三段：
  - 创建任务
  - 查询任务
  - 取消任务

A) 创建任务
- 必填/选填字段按你 API 文档生成（占位）：
  - 输入视频源/参数（例如：source_url、callback_url、template 等——以你的接口为准）
- 「发送创建请求」Primary
- 高级选项（折叠）：请求超时、重试次数、是否保存到日志

B) 查询任务
- task_id 输入框
- 操作：
  - 「查询」Primary
  - 「开启轮询」Secondary（间隔输入：2s/5s/10s）
  - 「停止轮询」

C) 取消任务
- task_id 输入框
- 「取消任务」Danger（需二次确认弹窗）

2) 右侧：结果区（Result Panel）
- 分区展示：
  - Request（Headers + Body，JSON 可折叠）
  - Response（Status + Body）
  - 耗时与时间戳
- 按钮：复制 Request / 复制 Response

3) 下方：调试日志（Recent Requests）
- 列表/表格：时间、动作（创建/查询/取消）、task_id（若有）、结果（成功/失败）、耗时
- 点击单条：在结果区回放该次请求/响应
- 控制：清空日志、仅看失败

状态与错误
- 401/403：提示 Token 无效，提供“返回登录”按钮
- 429/5xx：提示可重试，并保留上次请求参数

### Responsive
- Tablet：双栏变上下布局（表单在上，结果在下）。
- Mobile：三段调试表单改 Accordion；结果区与日志改为全宽堆叠；表格改卡片列表。
