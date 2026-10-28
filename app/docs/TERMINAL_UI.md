# 工业战术风格 UI — 2026-10-28

参考 https://endfield.hypergryph.com/ 实际官网页面的窄导航、黑白标题、工业标记与留白，重新组织本地分析界面的视觉层级。未复制官网角色、商标或宣传图。

- 新增默认“战术终端”黑白黄配色，完整亮/暗模式；保留五种原有配色及自定义和旧偏好。
- 编号导航、档案式比赛头部、细线分区、小圆角与高对比按钮。
- 空状态原创 SVG 战术示意图明确标注非比赛数据。
- 原有分析、证据、回放、存档和解释逻辑不变。
- 修复窄屏队伍表格撑开整页的问题。

主要变更：frontend/src/styles/terminal.css、theme/appearance.tsx、app/chrome.tsx、views/Overview.tsx、main.tsx、frontend/index.html。

验证：TypeScript + Vite build 通过。真实既有 demo 检查比赛概览、分析页；亮/暗视觉检查；390px 视口下文档宽380px、视口390px，无页面横向溢出。浏览器错误日志为空。未重新执行所有上传、存档写入、导出等操作，也未重跑 demo 解析；本轮未修改后端。

新版服务使用本工作区 app，不是 D 盘历史解压副本。预览 http://127.0.0.1:8765/?palette=terminal&theme=light 。如果保存了旧配色，可以在“主题与显示”切换到“战术终端”。

后端回归：160 passed，1 条既有 Starlette 弃用警告。
