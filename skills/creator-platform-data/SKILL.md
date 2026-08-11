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
| 多账号 / 两个平台 / 全部创作者数据 | 配置 `accounts.example.yaml` 后运行 `scripts/run_accounts.py`，并按 `platform + account_key + data_date + content_id` 合并 |

写入任何 Sheet 前，先阅读 `references/unified-schema.md`。如果要处理平台专属字段，再阅读 `references/douyin-sheet-schema.md` 或 `references/xiaohongshu-sheet-schema.md`。

## 多账号采集

多账号必须先复制 `accounts.example.yaml` 为本地私有配置，例如 `accounts.yaml`。真实配置不要提交、不要上传、不要放进 SkillHub。每个平台、每个账号必须使用独立 `profile_dir`；不要让两个账号共用同一个浏览器 profile。

每个账号必须配置稳定的 `account_key`。`account_key` 是写 Sheet 和本地快照的长期唯一标识；不要用 `account_name` 作为唯一标识，因为账号昵称可能会改，也可能重复。

运行多账号采集：

```bash
python scripts/run_accounts.py \
  --config accounts.yaml \
  --output-dir "$HOME/.codex/state/creator_platform_snapshots" \
  --snapshot-date 2026-08-07 \
  --start-date 2026-05-01 \
  --end-date 2026-07-03
```

`scripts/run_accounts.py` 会按账号逐个调用平台采集器，并把 `--account-key`、`--account-name`、独立 `--profile-dir` 传给采集器。某个账号失败时继续采集其他账号，最后返回失败状态供自动任务识别。

写入 Sheet 时必须用 `platform + account_key + data_date + content_id` 作为 upsert key，保留无关行，不要重复插入同一账号同一天同一作品。

## 采集抖音数据

使用独立持久化 profile：

```bash
python scripts/collect_douyin.py \
  --profile-dir "$HOME/.codex/state/douyin-creator-profile" \
  --account-key douyin_main \
  --login-image "$HOME/.codex/state/douyin-creator-login-$(date +%Y%m%d-%H%M%S).png" \
  --output "$HOME/.codex/state/creator_platform_snapshots/douyin-$(date +%F).tsv"
```

当脚本输出 `{"status":"login_required","qr_image":"..."}` 时，只把裁剪后的二维码展示给用户，并保持进程运行等待扫码。二维码文件名必须唯一；等待扫码时不要离开登录页。抖音打开二维码登录页后必须等待 3-6 秒再截图，等待期间不要刷新页面、不要重新导航登录页，也不要请求作品接口；只有页面离开二维码登录状态后才确认登录。脚本必须先用视觉检测确认截图里存在二维码，视觉检测失败时不要展示 `qr_image`。

扫码确认后，如果抖音出现“发送短信验证”身份验证页面，采集器先点击这个验证选项，再点击下一步页面的“发送验证码”；如果页面使用“发送短信”或“获取验证码”，也应点击对应发送动作。然后输出“本次登录需要短信验证码，已点击发送验证码，请将本次验证码发给我”，等待用户提供本次验证码，由当前 Playwright 会话填入并提交。验证码只在当前进程内短暂使用，不打印、不保存、不写入快照或命令行参数。只有页面登录状态确认成功后，才请求作品接口。

抖音可获取字段包括：当前账号名称、发布时间、播放数、平均播放时长、封面点击率、点赞数、评论数、分享数、收藏数、完播率、5秒完播率、作品带来的新粉丝数、粉丝观看占比。

## 采集小红书数据

必须运行 `scripts/collect_xiaohongshu.py`，让脚本负责打开独立 Playwright 浏览器 profile、检测登录态、切换二维码登录、裁剪二维码、等待扫码、按页面签名响应采集数据。不要手工停在网页里让用户自己处理登录，也不要绕过脚本直接请求小红书签名接口。

使用发布时间范围：

```bash
python scripts/collect_xiaohongshu.py \
  --profile-dir "$HOME/.codex/state/xiaohongshu-creator-profile" \
  --account-key xiaohongshu_main \
  --login-image "$HOME/.codex/state/xiaohongshu-login-$(date +%Y%m%d-%H%M%S).png" \
  --start-date 2026-05-01 \
  --end-date 2026-07-03 \
  --output "$HOME/.codex/state/creator_platform_snapshots/xiaohongshu-$(date +%F).tsv" \
  --include-details
```

`--start-date` 和 `--end-date` 筛选的是笔记发布时间（页面里的 `笔记首发时间`），不是快照日期。如果要做每日采集记录，单独设置 `--snapshot-date`。

### 小红书二维码登录强制流程

处理小红书登录时，必须运行 `scripts/collect_xiaohongshu.py`，让脚本完成登录页切换、二维码裁剪和登录等待。不要自己停在登录页面让用户操作。

如果小红书登录页默认显示手机号/验证码登录，必须点击二维码登录入口，切换到 App 扫码登录。不要停在手机号/验证码登录页，不要要求用户自己找二维码。

只有脚本输出 `login_required` 后，才展示 `qr_image` 指向的裁剪后的二维码；如果脚本输出的是 `{"status":"login_required","qr_image":"..."}`，把该图片用 Markdown 图片语法展示给用户，并保持脚本进程继续运行等待扫码。等待期间不要刷新页面、不要重新导航登录页、不要重新生成二维码，除非用户明确说二维码已过期。

展示二维码前，采集器必须调用 `scripts/qr_vision.py` 对裁剪后的 PNG 做本地视觉检测。必须先用视觉检测确认截图里存在二维码；如果输出 `login_qr_not_found`，说明没有找到有效二维码或截图不像二维码，视觉检测失败时不要展示 `qr_image`，不要把整页截图、空白图、手机号登录页截图发给用户。

重点：小红书笔记列表接口需要页面前端生成签名请求头。不要复用用户粘贴的 curl header，也不要裸请求签名接口。采集器必须填写页面可见的 `开始时间` / `结束时间` 输入框，等待页面自己发出的签名响应，并解析该 JSON。

小红书可获取字段包括：账号名称、笔记标题、发布时间、曝光、观看、封面点击率、点赞、评论、收藏、涨粉、分享、人均观看时长、弹幕、可展示时的完播率、2秒退出率、粉丝占比。

## Sheet 和快照规则

- 本地快照使用 TSV。
- 统一表使用 `platform + account_key + data_date + content_id` 作为 upsert key。
- 写 Sheet 时保留无关行。
- 不可用指标留空，不要把缺失值改成 0。
- 不要把小红书 `2秒退出率` 映射到抖音 `5秒完播率`。
- 不要把抖音 `fan_view_share` 映射到小红书详情页粉丝占比字段。

## 登录排障

- 每次登录都生成新的唯一二维码图片路径。
- 二维码生成后先做本地视觉检测；确认是二维码后立即发送给用户。
- 发给用户时必须使用 Markdown 图片语法展示 `qr_image`，不要只用内部图片查看工具。
- 未找到二维码、裁剪失败或视觉检测失败时，报告 `login_qr_not_found`，不要发送截图。
- 等待扫码时保持浏览器停留在登录页。
- 扫码后若出现短信验证，默认只发送一次短信，提示用户提供本次验证码，并由当前 Playwright 会话填入提交。
- 登录态过期时，重新可视化运行并让用户扫码。
- 如果无法识别账号名称，用 `--account-name` 重新运行；不要编造账号名。
