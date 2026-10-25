# CS2 Demo Evidence Lab

离线 CS2 demo 分析与复盘工具，Python / FastAPI 后端和 React / TypeScript 前端。

已实现基础统计、交战与死亡复盘、瞄准变化、停步开枪、连续射击、闪光弹分析，以及 2D 回放、片段笔记和支持多个 SteamID 的个人存档。未知与估计明确标注，不生成没有依据的评分。

## Windows 启动

1. 安装 Python 3.12（64 位）与 Node.js 24。
2. 首次运行 `app/setup.cmd` 安装依赖并构建界面，此步骤需要联网。
3. 运行 `app/start.cmd`，访问 http://127.0.0.1:8765 。依赖准备好后可离线分析。
4. 使用 `app/stop.cmd` 停止服务。

仓库不包含 demo、个人存档、依赖环境或缓存。个人运行数据保存在 `app/data`。

## 协作开发

- [合作伙伴交接与模块契约](app/docs/PARTNER_HANDOFF.md)
- [新增模块交付模板](app/docs/MODULE_HANDOFF_TEMPLATE.md)
- [本次功能与验收说明](app/docs/REVIEW_V3.md)
- [贡献流程](CONTRIBUTING.md)
- [算法及限制](app/docs/ALGORITHMS.md)

测试：`app/.venv/Scripts/python.exe -X utf8 -m pytest app/tests -q`

前端构建：`npm.cmd run build --prefix app/frontend`

离线地图资源的来源及版权见 [NOTICE](app/frontend/public/maps/NOTICE.txt)。其他第三方依赖遵循各自许可证。
