# Creator Platform Data

Standalone collectors for creator analytics from Chinese creator centers.

Supported platforms:

- Douyin Creator Center: daily cumulative work metrics.
- Xiaohongshu Creator Center: note analytics filtered by publish-time range.

This project intentionally does not depend on CreatorHub. It uses isolated Playwright persistent browser profiles so a user can scan a platform QR code once and later reuse the local browser session.

## Security Rules

Never commit or publish:

- browser profiles or storage state;
- cookies, tokens, `id_token`, `web_session`, `x-s`, `x-s-common`, raw auth headers;
- QR login screenshots;
- exported TSV/CSV/XLSX creator data.

The `.gitignore` is set up to exclude those by default.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Douyin Snapshot

```bash
python scripts/douyin/collect_snapshot.py \
  --profile-dir "$HOME/.codex/state/douyin-creator-profile" \
  --login-image "$HOME/.codex/state/douyin-creator-login-$(date +%Y%m%d-%H%M%S).png" \
  --output "outputs/douyin-snapshot-$(date +%F).tsv"
```

When login is required, the script prints JSON containing a local `qr_image` path. Show only that cropped QR image to the user and keep the process alive while they scan.

## Xiaohongshu Snapshot

```bash
python scripts/xiaohongshu/collect_xiaohongshu.py \
  --profile-dir "$HOME/.codex/state/xiaohongshu-creator-profile" \
  --login-image "$HOME/.codex/state/xiaohongshu-login-$(date +%Y%m%d-%H%M%S).png" \
  --start-date 2026-05-01 \
  --end-date 2026-07-03 \
  --output "outputs/xiaohongshu-snapshot-$(date +%F).tsv" \
  --include-details
```

`--start-date` and `--end-date` filter by Xiaohongshu note publish time (`笔记首发时间`).

Important Xiaohongshu behavior: the note list API requires frontend-generated signed request headers. The collector sets the visible date inputs and listens to the page's own signed API response instead of reusing pasted curl headers or making a bare signed-API fetch.

## Schema

- Unified schema: `references/unified-schema.md`
- Douyin sheet schema: `references/douyin/sheet-schema.md`
- Xiaohongshu sheet schema: `references/xiaohongshu/sheet-schema.md`

Use `platform + data_date + content_id` as the stable upsert key for a unified multi-platform sheet.

## Tests

```bash
python -m unittest discover -s tests
```
