# Daily Snapshot Schema

Use one row per `data_date + work_id`. Update the existing row when the same work is collected again on the same Asia/Shanghai date.

| Column | Source |
| --- | --- |
| Current account name | Nickname shown by the currently logged-in Creator Center account |
| Data date | Asia/Shanghai calendar date |
| Work ID | `id` |
| Publish title | Empty unless the API returns an explicit title |
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
| Collected at | Asia/Shanghai timestamp |

The ratios above are API values. Render them as percentages, but do not recompute them from rounded counts.
