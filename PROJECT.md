# Creator Platform Data

Local project for collecting creator analytics from multiple Chinese creator centers.

## Platforms

- Douyin: use `scripts/douyin/collect_snapshot.py`.
- Xiaohongshu: use `scripts/xiaohongshu/collect_xiaohongshu.py`.

## Unified Key

Use `platform + data_date + content_id` when writing to a shared sheet.

## Security

Never store cookies, `id_token`, `web_session`, `x-s`, `x-s-common`, raw auth headers, or QR images in this project. Both collectors should use local Playwright profiles and authenticated in-page requests.

## Xiaohongshu Example

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

## Schema

See `references/unified-schema.md`.
