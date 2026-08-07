# 抖音每日快照字段表

每一行代表 `account_key + data_date + work_id` 对应的一条抖音作品快照。如果同一账号同一天再次采集到同一个作品，需要更新原行，不要重复新增。

| 字段 | 来源 |
| --- | --- |
| Platform | 固定为 `douyin` |
| Account key | 本地配置中的稳定账号标识 |
| Current account name | 当前登录抖音创作者中心账号昵称 |
| Data date | Asia/Shanghai 日历日期 |
| Work ID | `id` |
| Publish title | 接口明确返回标题时填写，否则留空 |
| Content | `description` |
| Publish time | `create_time` |
| Views | `metrics.view_count` |
| Avg watch seconds | `metrics.avg_view_second` |
| Cover CTR | `metrics.cover_click_rate` |
| Likes | `metrics.like_count` |
| Comments | `metrics.comment_count` |
| Shares | `metrics.share_count` |
| Favorites | `metrics.favorite_count` |
| Completion rate | `metrics.completion_rate` |
| 5-second completion rate | `metrics.completion_rate_5s` |
| New followers | `metrics.subscribe_count` |
| Fan-view share | `metrics.fan_view_proportion` |
| Collected at | Asia/Shanghai 采集时间 |

比例字段来自抖音接口值。可以展示为百分比，但不要根据四舍五入后的数量重新计算。
