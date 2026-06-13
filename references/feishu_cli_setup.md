# 飞书 CLI 环境与目标文档

技术图表写入飞书画板前，按两步检查。

## 第一步：安装、配置和用户授权

推荐安装：

```bash
npx @larksuite/cli@latest install
npx skills add larksuite/cli -y -g
```

首次使用时配置应用并完成用户授权：

```bash
lark-cli config init --new
lark-cli auth login --recommend
lark-cli auth status --verify
```

只有 `auth status --verify` 显示 `identity` 为 `user` 且 `tokenStatus` 为 `valid` 时，才可以向用户有编辑权限的目标文档写入画板。仅有 bot 身份不满足本 Skill 的画板写入要求。

## 第二步：指定目标在线文档

环境检查必须通过 `--feishu-doc` 接收一个用户可编辑的飞书文档 URL 或 token：

```bash
python3 scripts/check_environment.py \
  --out-dir <任务目录> \
  --feishu-doc "https://example.feishu.cn/wiki/<token>"
```

文档用于集中存放本次软著的总图和功能流程分图。后续步骤从 `环境检查.json` 的 `feishu.target_document` 读取目标，不得在 `SKILL.md` 或命令中硬编码其他文档。

如果不使用飞书画板，必须显式选择跳过：

```bash
python3 scripts/check_environment.py \
  --out-dir <任务目录> \
  --skip-feishu
```

跳过后，不记录 `diagrams` 门禁，也不阻塞 Markdown 确认或正式资料生成；可按需保留 Markdown 文本描述。

## 常用调用

验证可读取目标文档：

```bash
lark-cli docs +fetch --api-version v2 --doc "<URL-or-token>" --as user
```

在目标文档末尾创建空白画板：

```bash
lark-cli docs +update --api-version v2 \
  --doc "<URL-or-token>" \
  --command append \
  --content '<whiteboard type="blank"></whiteboard>' \
  --as user
```

如提示权限不足，确认当前用户对目标文档有编辑权限，并按 CLI 提示补充授权后重新登录。

参考：

- 飞书开放平台：<https://open.feishu.cn/document/mcp_open_tools/feishu-cli-let-ai-actually-do-your-work-in-feishu>
- 官方仓库：<https://github.com/larksuite/cli>
- 用户提供的参考文章：<https://mp.weixin.qq.com/s/fvjxT_GgbEgxgsPCUlo-RQ>
