---
name: creator-platform-data
description: Use when a user needs Douyin or Xiaohongshu creator analytics, standalone Playwright QR login, daily creator snapshots, publish-time range filtering, unified TSV output, or sheet upserts for Chinese creator-center data.
---

# Creator Platform Data

Use this as the single entrypoint for creator analytics from Douyin and Xiaohongshu. Choose the platform from the user request, run the bundled collector, and map output using the unified schema.

Never print, store, commit, upload, or write to a sheet: cookies, tokens, signed request headers, browser profiles, QR login screenshots, raw auth material, or local exported data files.

## Platform Decision

| User asks for | Run |
| --- | --- |
| 抖音, Douyin, 5秒完播率, 视频播放/完播 | `scripts/collect_douyin.py` |
| 小红书, Xiaohongshu, 笔记数据, 2秒退出率 | `scripts/collect_xiaohongshu.py` |
| 两个平台 / 全部创作者数据 | Run both collectors and combine by `platform + data_date + content_id` |

Before writing to any sheet, read `references/unified-schema.md`. For platform-specific columns, also read `references/douyin-sheet-schema.md` or `references/xiaohongshu-sheet-schema.md`.

## Douyin Collection

Run with a dedicated persistent profile:

```bash
python scripts/collect_douyin.py \
  --profile-dir "$HOME/.codex/state/douyin-creator-profile" \
  --login-image "$HOME/.codex/state/douyin-creator-login-$(date +%Y%m%d-%H%M%S).png" \
  --output "$HOME/.codex/state/creator_platform_snapshots/douyin-$(date +%F).tsv"
```

When the script emits `{"status":"login_required","qr_image":"..."}`, show only the cropped QR image to the user and keep the process alive while they scan. Use a unique QR filename; do not navigate away from the login page while waiting.

Available Douyin fields include current account name, publish time, views, average watch seconds, cover CTR, likes, comments, shares, favorites, completion rate, 5-second completion rate, new followers, and fan-view share.

## Xiaohongshu Collection

Run with a publish-time range:

```bash
python scripts/collect_xiaohongshu.py \
  --profile-dir "$HOME/.codex/state/xiaohongshu-creator-profile" \
  --login-image "$HOME/.codex/state/xiaohongshu-login-$(date +%Y%m%d-%H%M%S).png" \
  --start-date 2026-05-01 \
  --end-date 2026-07-03 \
  --output "$HOME/.codex/state/creator_platform_snapshots/xiaohongshu-$(date +%F).tsv" \
  --include-details
```

`--start-date` and `--end-date` filter note publish time (`笔记首发时间`), not the snapshot date. Set `--snapshot-date` separately for daily collection records when needed.

Important: Xiaohongshu's list API requires frontend-generated signed headers. Do not reuse pasted curl headers and do not make a bare signed-API fetch. The collector must set the visible `开始时间` / `结束时间` inputs, wait for the page's own signed response, and parse that JSON.

Available Xiaohongshu fields include account name, note title, publish time, exposure, views, cover CTR, likes, comments, favorites, new followers, shares, average watch seconds, danmaku, completion rate when exposed, 2-second exit rate, and fan ratios.

## Sheet and Snapshot Rules

- Use TSV for local snapshots.
- Use `platform + data_date + content_id` as the unified upsert key.
- Preserve unrelated sheet rows.
- Leave unavailable metrics blank; do not convert missing values to zero.
- Do not map Xiaohongshu `2秒退出率` into Douyin's `5秒完播率`.
- Do not map Douyin `fan_view_share` into Xiaohongshu's detail-page fan ratio fields.

## Login Troubleshooting

- Generate a fresh, unique QR image path for every login attempt.
- Send the QR image immediately after it is created.
- Keep the browser on the login page while waiting for scan confirmation.
- If the session expires, rerun visibly and let the user scan again.
- If account-name discovery fails, rerun with `--account-name`; never invent an account name.
