import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "xiaohongshu" / "collect_xiaohongshu.py"


def load_collector():
    spec = importlib.util.spec_from_file_location("collect_xiaohongshu", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ApiUrlTests(unittest.TestCase):
    def test_builds_note_list_url_from_publish_date_range(self):
        collector = load_collector()

        self.assertEqual(
            collector.note_list_url(
                start_date="2026-05-01",
                end_date="2026-07-03",
                page_num=2,
                page_size=10,
                note_type=0,
            ),
            "https://creator.xiaohongshu.com/api/galaxy/creator/datacenter/note/analyze/list?"
            "post_begin_time=1777564800000&post_end_time=1783094399000&"
            "type=0&page_size=10&page_num=2",
        )

    def test_matches_signed_frontend_list_response_for_requested_range(self):
        collector = load_collector()
        url = (
            "https://creator.xiaohongshu.com/api/galaxy/creator/datacenter/note/analyze/list?"
            "post_begin_time=1777564800000&post_end_time=1783094399000&"
            "type=0&page_size=10&page_num=1"
        )

        self.assertTrue(
            collector.list_url_matches(
                url,
                start_date="2026-05-01",
                end_date="2026-07-03",
                page_num=1,
                page_size=10,
                note_type=0,
            )
        )

    def test_rejects_initial_unfiltered_list_response(self):
        collector = load_collector()
        url = (
            "https://creator.xiaohongshu.com/api/galaxy/creator/datacenter/note/analyze/list?"
            "type=0&page_size=10&page_num=1"
        )

        self.assertFalse(
            collector.list_url_matches(
                url,
                start_date="2026-05-01",
                end_date="2026-07-03",
                page_num=1,
                page_size=10,
                note_type=0,
            )
        )


class ShapeExtractionTests(unittest.TestCase):
    def test_extracts_note_items_from_nested_payload(self):
        collector = load_collector()
        payload = {
            "success": True,
            "data": {
                "list": [{
                    "note_id": "note-1",
                    "title": "测试笔记",
                    "post_time": 1_780_000_000_000,
                    "exposure": 54,
                    "view": 9,
                    "cover_click_rate": 0.132,
                }],
                "total": 1,
            },
        }

        items = collector.note_items(payload)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["note_id"], "note-1")


class VisibleTextDetailTests(unittest.TestCase):
    def test_parses_detail_metrics_and_fan_ratios(self):
        collector = load_collector()
        lines = [
            "核心数据",
            "曝光数", "54", "粉丝占比 5.6%",
            "观看数", "9", "粉丝占比 75%",
            "封面点击率", "13.2%", "粉丝 100%",
            "平均观看时长", "7.3秒", "粉丝 21秒",
            "完播率", "0%", "粉丝 0%",
            "2秒退出率", "40%", "粉丝 33.3%",
            "涨粉数", "0",
            "互动数据",
            "点赞数", "0", "粉丝占比 0%",
            "评论数", "0", "粉丝占比 0%",
            "收藏数", "0", "粉丝占比 0%",
            "分享数", "0", "粉丝占比 0%",
        ]

        metrics = collector.parse_detail_lines(lines)

        self.assertEqual(metrics["exposure"], "54")
        self.assertEqual(metrics["views"], "9")
        self.assertEqual(metrics["cover_ctr"], "13.2%")
        self.assertEqual(metrics["avg_watch_seconds"], "7.3")
        self.assertEqual(metrics["completion_rate"], "0%")
        self.assertEqual(metrics["two_second_exit_rate"], "40%")
        self.assertEqual(metrics["views_fan_share"], "75%")
        self.assertEqual(metrics["two_second_exit_fan_share"], "33.3%")


class QrClipTests(unittest.TestCase):
    def test_prefers_square_near_qr_login_text_over_larger_decoration(self):
        collector = load_collector()
        candidates = [
            {
                "tag": "IMG",
                "x": 40,
                "y": 220,
                "width": 360,
                "height": 360,
                "area": 129600,
                "text": "",
            },
            {
                "tag": "CANVAS",
                "x": 650,
                "y": 355,
                "width": 220,
                "height": 220,
                "area": 48400,
                "text": "",
            },
        ]
        labels = [{"text": "APP扫一扫登录", "x": 690, "y": 310, "width": 120, "height": 24}]

        chosen = collector.choose_qr_rect(candidates, labels, {"width": 1000, "height": 800})

        self.assertEqual(chosen["x"], 650)
        self.assertEqual(chosen["y"], 355)


class RowMappingTests(unittest.TestCase):
    def test_maps_list_item_and_detail_to_unified_row(self):
        collector = load_collector()
        item = {
            "note_id": "note-1",
            "title": "测试笔记",
            "post_time": 1_780_000_000_000,
            "exposure": 54,
            "view": 9,
            "cover_click_rate": 0.132,
            "like": 1,
            "comment": 2,
            "collect": 3,
            "follow": 4,
            "share": 5,
            "avg_watch_duration": 7.3,
            "danmaku": 0,
        }
        detail = {"two_second_exit_rate": "40%", "completion_rate": "0%"}

        row = collector.row_from_note(
            account_name="账号",
            item=item,
            detail=detail,
            snapshot_date="2026-08-07",
            collected_at="2026-08-07 13:00:00",
        )

        self.assertEqual(row["platform"], "xiaohongshu")
        self.assertEqual(row["content_id"], "note-1")
        self.assertEqual(row["exposure"], 54)
        self.assertEqual(row["views"], 9)
        self.assertEqual(row["two_second_exit_rate"], "40%")
        self.assertEqual(row["completion_rate"], "0%")


class CommandLineTests(unittest.TestCase):
    def test_accepts_profile_output_and_publish_range(self):
        collector = load_collector()
        old_argv = sys.argv
        try:
            sys.argv = [
                "collect_xiaohongshu.py",
                "--profile-dir", "/tmp/xhs-profile",
                "--output", "/tmp/xhs.tsv",
                "--start-date", "2026-05-01",
                "--end-date", "2026-07-03",
            ]
            args = collector.parse_args()
        finally:
            sys.argv = old_argv

        self.assertEqual(args.profile_dir, Path("/tmp/xhs-profile"))
        self.assertEqual(args.start_date, "2026-05-01")
        self.assertEqual(args.end_date, "2026-07-03")


if __name__ == "__main__":
    unittest.main()
