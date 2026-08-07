# 创作者平台统一字段表

统一表每一行代表一个平台、一个账号在某一天采集到的一条作品/笔记数据，主键使用 `platform + account_key + data_date + content_id`。

字段名保持英文，方便脚本、Sheet 和后续自动任务稳定使用；字段说明使用中文。

| 字段 | 抖音来源 | 小红书来源 |
| --- | --- | --- |
| platform | 固定为 `douyin` | 固定为 `xiaohongshu` |
| account_key | 本地配置中的稳定账号标识 | 本地配置中的稳定账号标识 |
| account_name | 创作者中心当前账号昵称 | 创作者中心当前账号昵称 |
| data_date | 快照日期 | 快照日期 |
| content_id | 作品 ID | 笔记 ID |
| title | 如接口提供标题则填写 | 笔记标题 |
| content | 作品描述 | 笔记正文/描述，接口可用时填写 |
| publish_time | 作品发布时间 | 笔记发布时间 |
| exposure | 留空 | 曝光数 |
| views | 播放数 | 观看数 |
| cover_ctr | 封面点击率 | 封面点击率 |
| likes | 点赞数 | 点赞数 |
| comments | 评论数 | 评论数 |
| favorites | 收藏数 | 收藏数 |
| new_followers | 作品带来的新粉丝数 | 笔记带来的涨粉数 |
| shares | 分享数 | 分享数 |
| avg_watch_seconds | 平均播放时长 | 人均观看时长 |
| danmaku | 留空 | 弹幕数 |
| two_second_exit_rate | 留空 | 2秒退出率 |
| completion_rate | 完播率 | 详情页展示时的完播率 |
| completion_rate_5s | 5秒完播率 | 留空 |
| fan_view_share | 粉丝观看占比 | 留空 |
| *_fan_share | 抖音除 `fan_view_share` 外留空 | 小红书详情页中的粉丝占比 |
| collected_at | 采集时间 | 采集时间 |

不要把一个平台独有的指标强行映射到另一个平台字段中。平台没有提供的指标保持空值。

多账号场景不要用 `account_name` 去重。账号昵称可能变化，也可能重复；写入 Sheet 时必须以 `account_key` 为账号维度。
