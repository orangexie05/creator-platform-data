---
name: creator-platform-data
description: 用于获取抖音或小红书创作者数据、独立 Playwright 二维码登录、每日创作者快照、按发布时间筛选、统一 TSV 输出，或把中文创作者中心数据写入 Sheet。
---

# 创作者平台数据采集

把这个 Skill 作为抖音和小红书创作者数据的统一入口。先根据用户请求判断平台，再运行内置采集器，并用统一字段表映射输出。

严禁打印、保存、提交、上传或写入 Sheet：cookie、token、签名请求头、浏览器 profile、二维码登录截图、原始鉴权信息、本地导出的数据文件。

## 平台选择

| 用户需求 | 运行 |
| --- | --- |
| 抖音、Douyin、5秒完播率、视频播放/完播 | `scripts/collect_douyin.py` |
| 小红书、Xiaohongshu、笔记数据、2秒退出率 | `scripts/collect_xiaohongshu.py` |
| 两个平台 / 全部创作者数据 | 两个采集器都运行，并按 `platform + data_date + content_id` 合并 |

写入任何 Sheet 前，先阅读 `references/unified-schema.md`。如果要处理平台专属字段，再阅读 `references/douyin-sheet-schema.md` 或 `references/xiaohongshu-sheet-schema.md`。

## 采集抖音数据

使用独立持久化 profile：

```bash
python scripts/collect_douyin.py \
  --profile-dir "$HOME/.codex/state/douyin-creator-profile" \
  --login-image "$HOME/.codex/state/douyin-creator-login-$(date +%Y%m%d-%H%M%S).png" \
  --output "$HOME/.codex/state/creator_platform_snapshots/douyin-$(date +%F).tsv"
```

当脚本输出 `{"status":"login_required","qr_image":"..."}` 时，只把裁剪后的二维码展示给用户，并保持进程运行等待扫码。二维码文件名必须唯一；等待扫码时不要离开登录页。

抖音可获取字段包括：当前账号名称、发布时间、播放数、平均播放时长、封面点击率、点赞数、评论数、分享数、收藏数、完播率、5秒完播率、作品带来的新粉丝数、粉丝观看占比。

## 采集小红书数据

使用发布时间范围：

```bash
python scripts/collect_xiaohongshu.py \
  --profile-dir "$HOME/.codex/state/xiaohongshu-creator-profile" \
  --login-image "$HOME/.codex/state/xiaohongshu-login-$(date +%Y%m%d-%H%M%S).png" \
  --start-date 2026-05-01 \
  --end-date 2026-07-03 \
  --output "$HOME/.codex/state/creator_platform_snapshots/xiaohongshu-$(date +%F).tsv" \
  --include-details
```

`--start-date` 和 `--end-date` 筛选的是笔记发布时间（页面里的 `笔记首发时间`），不是快照日期。如果要做每日采集记录，单独设置 `--snapshot-date`。

重点：小红书笔记列表接口需要页面前端生成签名请求头。不要复用用户粘贴的 curl header，也不要裸请求签名接口。采集器必须填写页面可见的 `开始时间` / `结束时间` 输入框，等待页面自己发出的签名响应，并解析该 JSON。

小红书可获取字段包括：账号名称、笔记标题、发布时间、曝光、观看、封面点击率、点赞、评论、收藏、涨粉、分享、人均观看时长、弹幕、可展示时的完播率、2秒退出率、粉丝占比。

## Sheet 和快照规则

- 本地快照使用 TSV。
- 统一表使用 `platform + data_date + content_id` 作为 upsert key。
- 写 Sheet 时保留无关行。
- 不可用指标留空，不要把缺失值改成 0。
- 不要把小红书 `2秒退出率` 映射到抖音 `5秒完播率`。
- 不要把抖音 `fan_view_share` 映射到小红书详情页粉丝占比字段。

## 登录排障

- 每次登录都生成新的唯一二维码图片路径。
- 二维码生成后立即发送给用户。
- 等待扫码时保持浏览器停留在登录页。
- 登录态过期时，重新可视化运行并让用户扫码。
- 如果无法识别账号名称，用 `--account-name` 重新运行；不要编造账号名。
