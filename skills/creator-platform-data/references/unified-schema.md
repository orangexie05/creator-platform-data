# Creator Platform Unified Schema

Use one row per `platform + data_date + content_id`.

| Column | Douyin | Xiaohongshu |
| --- | --- | --- |
| platform | `douyin` | `xiaohongshu` |
| account_name | Creator Center nickname | Creator Center nickname |
| data_date | Snapshot date | Snapshot date |
| content_id | Work ID | Note ID |
| title | Title if available | Note title |
| content | Description | Description if available |
| publish_time | Publish timestamp | Publish timestamp |
| exposure | blank | Exposure |
| views | Play count | Watch/view count |
| cover_ctr | Cover click rate | Cover click rate |
| likes | Likes | Likes |
| comments | Comments | Comments |
| favorites | Favorites | Collects/favorites |
| new_followers | New followers from work | New followers from note |
| shares | Shares | Shares |
| avg_watch_seconds | Average watch seconds | Average watch seconds |
| danmaku | blank | Danmaku/bullet count |
| two_second_exit_rate | blank | 2-second exit rate |
| completion_rate | Completion rate | Completion rate when detail page exposes it |
| completion_rate_5s | 5-second completion rate | blank |
| fan_view_share | Fan-view share | blank |
| *_fan_share | Douyin: blank except fan_view_share | Xiaohongshu detail-page fan ratios |
| collected_at | Collection timestamp | Collection timestamp |

Do not force one platform's metric into the other platform's column. Leave unavailable metrics blank.
