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

## 多账号配置

如果有多个账号，先复制示例配置：

```bash
cp accounts.example.yaml accounts.yaml
```

然后为每个账号设置独立的 `account_key` 和 `profile_dir`。不要让两个账号共用同一个 profile；不要用账号昵称作为唯一标识。

多账号采集：

```bash
python scripts/run_accounts.py \
  --config accounts.yaml \
  --output-dir outputs \
  --snapshot-date 2026-08-07 \
  --start-date 2026-05-01 \
  --end-date 2026-07-03
```

写入统一表时，使用 `platform + account_key + data_date + content_id` 作为稳定 upsert key。

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
  --account-key douyin_main \
  --login-image "$HOME/.codex/state/douyin-creator-login-$(date +%Y%m%d-%H%M%S).png" \
  --output "outputs/douyin-snapshot-$(date +%F).tsv"
```

如果需要登录，抖音脚本会在二维码登录页等待 3-6 秒，再裁剪二维码，并用 `scripts/qr_vision.py` 做本地视觉检测。只有确认截图里存在二维码时，才会输出包含 `qr_image` 路径的 JSON。展示给用户时必须使用 Markdown 图片语法；不要只用内部图片查看工具，不要展示整页截图、空白图或手机号登录页截图。等待扫码期间不要刷新页面、不要重新导航登录页，也不请求作品接口；只有页面离开二维码登录状态后才确认登录；如果输出 `login_qr_not_found`，需要重新定位二维码登录入口。

扫码确认后如果抖音出现身份验证选项，脚本优先点击“接收短信验证码”（兼容“发送短信验证”），再点击下一步页面的“发送验证码”（也兼容“发送短信”和“获取验证码”），并提示用户提供本次短信验证码。验证码只在当前进程内短暂使用，由 Playwright 填入并提交，不打印、不写文件、不加入命令行参数。只有页面确认登录成功后，脚本才会请求作品数据。

## 采集小红书数据

```bash
python scripts/xiaohongshu/collect_xiaohongshu.py \
  --profile-dir "$HOME/.codex/state/xiaohongshu-creator-profile" \
  --account-key xiaohongshu_main \
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

写入统一表时，使用 `platform + account_key + data_date + content_id` 作为稳定 upsert key。

## 测试

```bash
python -m unittest discover -s tests
```
