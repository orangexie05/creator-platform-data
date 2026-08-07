# 创作者平台数据采集

本项目用于从多个中文创作者中心采集创作者数据。GitHub 项目里提供一个统一 Codex Skill：`skills/creator-platform-data`。

## 平台

- 抖音：使用 `scripts/douyin/collect_snapshot.py`。
- 小红书：使用 `scripts/xiaohongshu/collect_xiaohongshu.py`。
- 多账号：复制 `accounts.example.yaml` 为本地 `accounts.yaml`，再使用 `scripts/run_accounts.py`。

## Skill

统一入口是 `skills/creator-platform-data`。它会把抖音和小红书请求路由到对应采集器，并使用 `references/unified-schema.md` 生成合并后的表格字段。

## 统一主键

写入共享 Sheet 时，使用 `platform + account_key + data_date + content_id` 作为主键，避免多个账号之间的数据互相覆盖。

## 安全

不要在项目中保存 cookie、`id_token`、`web_session`、`x-s`、`x-s-common`、原始鉴权 header 或二维码图片。两个采集器都应该使用本地 Playwright profile 和已登录页面上下文请求数据。

## 小红书示例

```bash
/Users/orange/.codex/runtimes/douyin-creator-daily-sheet/bin/python \
  scripts/xiaohongshu/collect_xiaohongshu.py \
  --profile-dir /Users/orange/.codex/state/xiaohongshu-creator-profile \
  --login-image /Users/orange/Documents/Codex/outputs/xiaohongshu-login-$(date +%Y%m%d-%H%M%S).png \
  --start-date 2026-05-01 \
  --end-date 2026-07-03 \
  --output outputs/xiaohongshu-snapshot-$(date +%F).tsv \
  --include-details
```

## 字段表

见 `references/unified-schema.md`。
