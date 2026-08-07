# Xiaohongshu Creator Snapshot Schema

Use one row per `data_date + content_id`.

| Column | Source |
| --- | --- |
| platform | Always `xiaohongshu` |
| account_name | Creator Center visible nickname |
| data_date | Asia/Shanghai snapshot date |
| content_id | Note ID |
| title | Note title |
| content | Note description when available |
| publish_time | Note publish time |
| exposure | `note/analyze/list` exposure metric or detail page `曝光数` |
| views | `note/analyze/list` view/watch metric or detail page `观看数` |
| cover_ctr | Cover click rate / `封面点击率` |
| likes | Likes / `点赞数` |
| comments | Comments / `评论数` |
| favorites | Collects/favorites / `收藏数` |
| new_followers | `涨粉` / `涨粉数` |
| shares | Shares / `分享数` |
| avg_watch_seconds | `人均观看时长` or detail `平均观看时长` |
| danmaku | `弹幕` |
| two_second_exit_rate | Detail page `2秒退出率` |
| completion_rate | Detail page `完播率` |
| *_fan_share | Detail-page fan ratios such as `粉丝占比 75%` |
| collected_at | Asia/Shanghai collection timestamp |

Xiaohongshu does not expose Douyin's `5秒完播率` in the observed pages. Do not map `2秒退出率` to Douyin's 5-second completion metric.
