# 前端重设计验证记录（2026-10-27）

验证环境：Windows，项目内 Node.js 24 / Python 3.12，真实任务 df77617d2b6e4a09a479f1223e450938（de_anubis，20 个完整正式回合，10 名玩家，六个模块 partial/succeeded）。浏览器截图使用本机 Chrome 无头模式与 CDP 驱动；页面由正在运行的本地 FastAPI 服务提供。

## 1. 构建

在项目根目录执行：

    npm.cmd run build --prefix app/frontend --cache .npm-cache

结果：成功。tsc --noEmit 与 Vite 生产构建均通过，无 TypeScript 错误。以下为最终构建产物：

    dist/index.html                 1.46 kB
    dist/assets/index-PD4lk0_R.css 78.33 kB
    dist/assets/index-CnJLvP41.js  379.95 kB

说明：构建使用项目已有依赖，没有新增运行时依赖，也没有 CDN 资源。

## 2. 后端测试

第一次按交接文档直接运行 pytest 时，19 个测试因 Windows 临时目录 ACL 拒绝访问而在 setup 阶段报错，并非断言失败；同一环境下 141 个测试已通过。将 TEMP/TMP 指向可写目录并禁用 pytest 缓存后重新运行：

    $env:TEMP='D:\dsh\csdemoanalyzer\_pytest-tmp'
    $env:TMP='D:\dsh\csdemoanalyzer\_pytest-tmp'
    app\.venv\Scripts\python.exe -X utf8 -m pytest app/tests -q -p no:cacheprovider

结果：

    160 passed, 1 warning in 3.64s

警告为 Starlette 对 httpx TestClient 的弃用提示，与本次前端改动无关。本轮未修改后端代码。

## 3. 浏览器交互断言

通过 Chrome DevTools Protocol 在真实页面上执行点击、输入、刷新和媒体模拟，读取 DOM 状态验证。全部命中：

| 检查 | 结果 |
| --- | --- |
| 明暗切换立即应用 | html data-theme = dark |
| 五套预设切换 | 紫黄暗色主色读取为 #a78bff |
| 自定义主色实时预览 | --accent = #0a8577 |
| 非法十六进制不应用 | 仍为 #0a8577，并出现格式错误提示 |
| 自定义保存 | localStorage 中 custom.dark.accent = #0a8577 |
| 刷新后保留 | theme=dark，palette=custom，glass=off，motion=reduce，--accent=#0a8577 |
| 液态玻璃开关 | html data-glass = off，侧栏/顶栏改为不透明 |
| 减少动效 | html data-motion = reduce |
| 跟随系统 | 媒体模拟 dark → data-theme=dark；模拟 light → data-theme=light |
| 100% 覆盖率默认隐藏 | 页面不包含“覆盖 100%” |
| 开启显示全部覆盖率 | 页面出现“覆盖 100%” |
| 技术信息开关 | 模块版本与技术字段出现 |
| 解释浮层键盘焦点 | 焦点进入问号后打开，包含“举例”“不能说明什么”“计算细节” |
| Esc 关闭解释 | 浮层移除 |
| 单回合数据 | 表格 10 行，单回合卡片 12 张，KAST 显示是/否 |
| 单回合不冒充全场 | 页面不包含 round_stats 裸词 |
| 尚无单回合聚合的模块 | 显示提示，指标卡数量 0，单回合标签禁用 |
| 旧结果 409 | 显示“这份结果没有单回合统计”和旧版本警告 |
| 上传非法文件 | 显示“魔数不是 PBDEMS2”，不创建任务 |
| 失败任务 | 显示失败原因与“重试 / 复用缓存” |
| 390px 页面 | 无横向溢出；比赛选择器宽 366px；主题按钮与最后导航项可见 |

补充：无头 Chrome 默认页面不持有焦点，直接调用 element.focus() 不会触发 focus 事件；开启 CDP 焦点模拟后验证通过。这不是页面逻辑变更。

## 4. 截图与视口

| 文件 | 视口 | 内容 |
| --- | --- | --- |
| ui-redesign-palettes.png | 2184×704 拼图 | 五套配色 × 明亮/暗黑 |
| ui-redesign-overview-light.png | 1440×1100 | 概览明亮 |
| ui-redesign-overview-dark.png | 1440×1100 | 概览暗黑 |
| ui-redesign-overview-light-full.png | 1280×2352 | 完整概览（明亮） |
| ui-redesign-overview-dark-full.png | 1280×2352 | 完整概览（暗黑） |
| ui-redesign-analysis-light.png | 1440×1200 | 基础统计明亮 |
| ui-redesign-analysis-dark.png | 1440×1200 | 基础统计暗黑（蓝橙） |
| ui-redesign-appearance.png | 1440×1100 | 主题与显示面板 |
| ui-redesign-custom.png | 1440×1100 | 自定义颜色与对比度检查 |
| ui-redesign-explanation.png | 1440×1000 | K/D 三层解释 |
| ui-redesign-round.png | 1440×1300 | 单回合统计 |
| ui-redesign-evidence.png | 1440×1000 | 证据图表与时间步 |
| ui-redesign-flash.png | 1440×1100 | 闪光分析与估计值说明 |
| ui-redesign-replay.png | 1440×1000 | 2D 回放 |
| ui-redesign-profiles.png | 1440×1000 | 个人存档与趋势 |
| ui-redesign-jobs.png | 1440×1000 | 任务队列 |
| ui-redesign-stale.png | 1440×1000 | 旧结果与 409 提示 |
| ui-redesign-mobile.png | 390×844 | 手机概览 |
| ui-redesign-mobile-table.png | 390×844 | 手机宽表格容器滚动 |

## 5. 已验证与未验证

已验证：

- 五套配色的明亮与暗黑页面、跟随系统、自定义颜色保存与刷新保留。
- 全部六个已实现模块页面加载，无 console exception。
- 单回合统计真实读取 round-stats；409、旧版本、无聚合、失败、取消、上传拒绝状态。
- 1440、1280、390 三个宽度；宽表格容器滚动；键盘焦点与解释浮层。
- 顶栏比赛选择与地图筛选已恢复；当前数据集只有 de_anubis，地图下拉按设计隐藏，因此多地图筛选分支未实际触发。
- 玻璃关闭、减少动效、系统主题。

未验证 / 已知限制：

- 仅测试 Chrome/Edge 系 Chromium；未在 Firefox、Safari 和真实手机触摸屏上实测。
- 未执行屏幕阅读器（NVDA/VoiceOver）完整朗读测试，也未运行 axe 等自动化无障碍扫描。
- 自定义颜色的对比度检查覆盖主要组合，未穷举所有文字/背景组合；“自动修正”为启发式，不保证通过所有 WCAG 级别。
- 只有一个真实 demo；跨地图、跨分辨率、旧浏览器和极长列表的性能未单独压测。
- 未新增后端接口，也未实现 HLTV Rating、自定义 Rating、职业基线或 planned 模块。
- 未测试浏览器打印和 PDF 导出；现有 JSON/CSV/HTML 导出入口保留并可直接调用。
- 上传成功路径仅用真实 295 MB demo 的既有数据间接验证；本轮自动化只验证了非法文件拒绝，未重复上传大文件以节省本机空间。
