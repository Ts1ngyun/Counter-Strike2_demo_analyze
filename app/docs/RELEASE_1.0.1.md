# 1.0.1 封存记录

这是开发源码整合包，包含构建后的前端；不是嵌入 Python 的免安装 EXE。首次需要 64 位 Python 3.12、Node.js 24 和联网安装锁定依赖，之后可离线分析。

ZIP 最外层只有：

```text
START.cmd
STOP.cmd
使用说明.txt
app/
```

`app` 保存后端、前端、测试、文档、锁文件、字体许可、雷达资源及安装脚本。`app/SOURCE_MANIFEST.json` 记录文件 SHA256、版本和生成时间；ZIP 旁边的 `.sha256` 校验文件验证整包。

本版包含静态外观、本地背景柔化、对位、多杀与残局，以及 Impact 移除。

验证：196 项后端测试通过；TypeScript/Vite 构建通过。外层 STOP/START 在现有 Windows 环境执行成功，health 与 OpenAPI 均返回 1.0.1。未声称已经完成无 Python/Node 的干净系统安装测试。

打包通过白名单排除 demo、app/data、个人档案、历史报告、浏览器配置、安装环境、node_modules、缓存和密钥。不要手工压缩整个工作目录来替代此包。

本次清理了 25 个可重建缓存目录，约 558 MiB，包括下载/安装缓存、测试缓存、源码 bytecode 和模块结果缓存。已有上传 demo、分析结果、回放依赖 facts、个人档案、书签与安装好的依赖均保留。服务启动后少量 bytecode 可能正常重建；不是数据泄露或清理失败。

GitHub 提交包含源码及许可资源；构建产物与 ZIP 不纳入 Git 历史。伙伴从 GitHub clone 后运行外层 START.cmd，会在首次安装时构建前端。不要复制别人的虚拟环境。
