# 创作者平台数据采集

这是一个不依赖 CreatorHub 的独立采集项目，用于从抖音创作者中心和小红书创作者中心获取创作者数据，并通过一个统一 Codex Skill 作为入口。

支持的平台：

- 抖音创作者中心：按天获取作品累计数据，例如播放、完播、5 秒完播、涨粉等。
- 小红书创作者中心：按笔记发布时间筛选，获取笔记数据，例如曝光、观看、2 秒退出率、完播率等。

项目使用独立 Playwright 持久化浏览器 profile。用户扫码登录一次后，后续可复用本地登录态；登录过期时重新生成二维码给用户扫码。

## 统一 Skill

项目主入口是一个统一 Skill：

```text
skills/creator-platform-data/
```

以后用户要抖音、小红书或两个平台的创作者数据时，都走这个 Skill。它会判断平台、调用对应采集器、处理二维码登录提示，并按统一字段表输出数据。

项目根目录下的 `scripts/` 保留给命令行直接运行和测试使用；Skill 自己也在 `skills/creator-platform-data/scripts/` 中打包了采集脚本。

## 安全规则

不要提交或发布以下内容：

- 浏览器 profile 或 storage state；
- cookie、token、`id_token`、`web_session`、`x-s`、`x-s-common`、原始鉴权 header；
- 二维码登录截图；
- 导出的 TSV/CSV/XLSX 创作者数据。

`.gitignore` 已经默认排除这些内容。

## 安装依赖

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## 采集抖音数据

```bash
python scripts/douyin/collect_snapshot.py \
  --profile-dir "$HOME/.codex/state/douyin-creator-profile" \
  --login-image "$HOME/.codex/state/douyin-creator-login-$(date +%Y%m%d-%H%M%S).png" \
  --output "outputs/douyin-snapshot-$(date +%F).tsv"
```

如果需要登录，脚本会输出包含 `qr_image` 路径的 JSON。只把裁剪后的二维码展示给用户，并保持进程运行等待用户扫码确认。

## 采集小红书数据

```bash
python scripts/xiaohongshu/collect_xiaohongshu.py \
  --profile-dir "$HOME/.codex/state/xiaohongshu-creator-profile" \
  --login-image "$HOME/.codex/state/xiaohongshu-login-$(date +%Y%m%d-%H%M%S).png" \
  --start-date 2026-05-01 \
  --end-date 2026-07-03 \
  --output "outputs/xiaohongshu-snapshot-$(date +%F).tsv" \
  --include-details
```

`--start-date` 和 `--end-date` 是按小红书笔记的发布时间筛选，也就是页面里的 `笔记首发时间`。

小红书有一个关键点：笔记列表接口需要页面前端生成签名请求头。采集器不能复用用户粘贴的 curl header，也不能裸请求签名接口；它会填写页面上的开始/结束时间输入框，然后监听页面自己发出的签名接口响应。

## 字段说明

- 统一字段表：`references/unified-schema.md`
- 抖音字段表：`references/douyin/sheet-schema.md`
- 小红书字段表：`references/xiaohongshu/sheet-schema.md`

写入统一表时，使用 `platform + data_date + content_id` 作为稳定 upsert key。

## 测试

```bash
python -m unittest discover -s tests
```
