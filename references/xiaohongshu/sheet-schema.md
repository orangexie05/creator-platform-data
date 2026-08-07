# 小红书创作者快照字段表

每一行代表 `account_key + data_date + content_id` 对应的一条小红书笔记快照。若写入统一多平台表，主键使用 `platform + account_key + data_date + content_id`。

| 字段 | 来源 |
| --- | --- |
| platform | 固定为 `xiaohongshu` |
| account_key | 本地配置中的稳定账号标识 |
| account_name | 创作者中心可见账号昵称 |
| data_date | Asia/Shanghai 快照日期 |
| content_id | 笔记 ID |
| title | 笔记标题 |
| content | 接口可用时填写笔记描述 |
| publish_time | 笔记发布时间 |
| exposure | `note/analyze/list` 曝光指标，或详情页 `曝光数` |
| views | `note/analyze/list` 观看/阅读指标，或详情页 `观看数` |
| cover_ctr | 封面点击率 / `封面点击率` |
| likes | 点赞数 / `点赞数` |
| comments | 评论数 / `评论数` |
| favorites | 收藏数 / `收藏数` |
| new_followers | `涨粉` / `涨粉数` |
| shares | 分享数 / `分享数` |
| avg_watch_seconds | `人均观看时长` 或详情页 `平均观看时长` |
| danmaku | `弹幕` |
| two_second_exit_rate | 详情页 `2秒退出率` |
| completion_rate | 详情页 `完播率` |
| *_fan_share | 详情页粉丝占比，例如 `粉丝占比 75%` |
| collected_at | Asia/Shanghai 采集时间 |

目前观察到的小红书页面不提供抖音式 `5秒完播率`。不要把 `2秒退出率` 映射为抖音的 5 秒完播指标。
