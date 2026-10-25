# 合作开发

仓库管理员在 Settings → Collaborators → Add people 中按 GitHub 用户名邀请伙伴。接受邀请后即可克隆私有仓库并提交分支。

请从 main 创建功能分支，通过 Pull Request 合并。新增分析模块先阅读 app/docs/PARTNER_HANDOFF.md，按 MODULE_HANDOFF_TEMPLATE.md 填写数据来源、算法版本、分母、未知/排除条件、证据结构与验证结果。人物定位和选位目前仍为 planned 接口。

提交前运行相关后端测试和前端构建。修改算法时更新算法版本，保留证据、未知状态和参数快照，避免不同口径静默混入趋势。

不要提交原始 demo、个人存档、令牌、密码、.env、缓存、虚拟环境或 node_modules。首次安装运行 app/setup.cmd。
