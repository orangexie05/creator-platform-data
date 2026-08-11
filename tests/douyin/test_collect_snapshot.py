import importlib.util
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "douyin" / "collect_snapshot.py"


def load_collector():
    spec = importlib.util.spec_from_file_location("collect_snapshot", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_blank_png(path: Path, width: int = 120, height: int = 120) -> None:
    raw = b"".join(b"\x00" + (b"\xff\xff\xff" * width) for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class WorkListUrlTests(unittest.TestCase):
    def test_builds_page_url_without_external_account_state(self):
        collector = load_collector()

        self.assertEqual(
            collector.work_list_url(cursor="123", page_size=12),
            "https://creator.douyin.com/janus/douyin/creator/pc/work_list?"
            "status=0&count=12&max_cursor=123&scene=star_atlas&"
            "device_platform=android&aid=1128",
        )


class SnapshotRowsTests(unittest.TestCase):
    def test_builds_rows_from_work_items_without_saved_account_data(self):
        collector = load_collector()
        items = [{
            "id": "work-1",
            "description": "A post\nwith a newline",
            "create_time": 1_754_476_800,
            "metrics": {
                "view_count": 42,
                "avg_view_second": 7.5,
                "cover_click_rate": 0.125,
                "like_count": 3,
                "comment_count": 2,
                "share_count": 1,
                "favorite_count": 4,
                "completion_rate": 0.5,
                "completion_rate_5s": 0.75,
                "subscribe_count": 6,
                "fan_view_proportion": 0.25,
            },
        }]

        rows = collector.rows_from_items(
            account_key="douyin_main",
            account_name="测试账号",
            items=items,
            snapshot_date="2026-08-06",
            collected_at="2026-08-06 13:00:00",
        )

        self.assertEqual(rows[0]["account_key"], "douyin_main")
        self.assertEqual(rows[0]["work_id"], "work-1")
        self.assertEqual(rows[0]["content"], "A post with a newline")
        self.assertEqual(rows[0]["cover_ctr"], "12.50%")
        self.assertEqual(rows[0]["completion_rate_5s"], "75.00%")
        self.assertEqual(rows[0]["new_followers"], 6)


class CommandLineTests(unittest.TestCase):
    def test_accepts_a_profile_directory_without_project_arguments(self):
        collector = load_collector()
        old_argv = sys.argv
        try:
            sys.argv = [
                "collect_snapshot.py",
                "--profile-dir", "/tmp/douyin-profile",
                "--output", "/tmp/snapshot.tsv",
                "--account-key", "douyin_main",
            ]
            args = collector.parse_args()
        finally:
            sys.argv = old_argv

        self.assertEqual(args.profile_dir, Path("/tmp/douyin-profile"))
        self.assertEqual(args.output, Path("/tmp/snapshot.tsv"))
        self.assertEqual(args.account_key, "douyin_main")


class LoginRenderTests(unittest.IsolatedAsyncioTestCase):
    async def test_waits_three_to_six_seconds_before_capturing_douyin_qr(self):
        collector = load_collector()

        self.assertGreaterEqual(collector.QR_RENDER_DELAY_MS, 3000)
        self.assertLessEqual(collector.QR_RENDER_DELAY_MS, 6000)

    async def test_detects_current_content_management_page_as_logged_in(self):
        collector = load_collector()

        class Locator:
            def __init__(self, count):
                self._count = count

            async def count(self):
                return self._count

        class Page:
            def get_by_text(self, text, exact):
                return Locator(1 if text == "内容管理" else 0)

        self.assertTrue(await collector.page_is_logged_in(Page()))

    async def test_waits_for_qr_login_element_before_capturing(self):
        collector = load_collector()

        class Locator:
            def __init__(self):
                self.waited_for = None

            async def wait_for(self, state, timeout):
                self.waited_for = (state, timeout)

        class Page:
            def __init__(self):
                self.locator = Locator()
                self.waited_for_ms = None

            def get_by_text(self, text, exact):
                self.text = (text, exact)
                return self.locator

            async def wait_for_timeout(self, milliseconds):
                self.waited_for_ms = milliseconds

        page = Page()
        await collector.wait_for_qr_login(page)

        self.assertEqual(page.text, ("扫码登录", True))
        self.assertEqual(page.locator.waited_for[0], "visible")
        self.assertEqual(page.waited_for_ms, collector.QR_RENDER_DELAY_MS)

    async def test_clicks_send_sms_once_when_sms_verification_appears(self):
        collector = load_collector()

        class Locator:
            def __init__(self, count):
                self._count = count
                self.clicks = 0

            @property
            def first(self):
                return self

            async def count(self):
                return self._count

            async def click(self):
                self.clicks += 1

        class Page:
            def __init__(self):
                self.marker = Locator(1)
                self.sender = Locator(1)

            def get_by_text(self, text, exact):
                if text == "短信验证码":
                    return self.marker
                if text == "发送短信":
                    return self.sender
                return Locator(0)

        page = Page()
        sent = await collector.handle_sms_challenge(page, already_sent=False)
        sent_again = await collector.handle_sms_challenge(page, already_sent=sent)

        self.assertTrue(sent)
        self.assertTrue(sent_again)
        self.assertEqual(page.sender.clicks, 1)

    async def test_prefers_receive_sms_verification_option(self):
        collector = load_collector()

        class Locator:
            def __init__(self, count):
                self._count = count
                self.clicks = 0

            @property
            def first(self):
                return self

            async def count(self):
                return self._count

            async def click(self):
                self.clicks += 1

        class Page:
            def __init__(self):
                self.option = Locator(1)
                self.sender = Locator(1)

            def get_by_text(self, text, exact):
                if text == "接收短信验证码":
                    return self.option
                if text == "发送验证码":
                    return self.sender
                return Locator(0)

        page = Page()
        option_selected = await collector.select_sms_verification_option(page, already_selected=False)
        sent = await collector.handle_sms_challenge(page, already_sent=False)

        self.assertTrue(option_selected)
        self.assertTrue(sent)
        self.assertEqual(page.option.clicks, 1)
        self.assertEqual(page.sender.clicks, 1)

    async def test_fills_sms_code_and_submits_in_the_open_browser(self):
        collector = load_collector()

        class Locator:
            def __init__(self):
                self.filled = None
                self.pressed = None

            @property
            def first(self):
                return self

            async def count(self):
                return 1

            async def fill(self, value):
                self.filled = value

            async def press(self, key):
                self.pressed = key

        class Page:
            def __init__(self):
                self.field = Locator()
                self.selector = None

            def locator(self, selector):
                self.selector = selector
                return self.field

        page = Page()
        await collector.enter_sms_code(page, "123456")

        self.assertIn("验证码", page.selector)
        self.assertEqual(page.field.filled, "123456")
        self.assertEqual(page.field.pressed, "Enter")

    async def test_detects_sms_code_form_after_receive_option(self):
        collector = load_collector()

        class Fields:
            async def count(self):
                return 1

        class Page:
            def locator(self, selector):
                self.selector = selector
                return Fields()

        self.assertTrue(await collector.sms_code_form_visible(Page()))

    async def test_does_not_probe_work_list_while_qr_login_text_is_visible(self):
        collector = load_collector()

        class Locator:
            async def count(self):
                return 1

        class Page:
            def get_by_text(self, text, exact):
                return Locator()

        self.assertFalse(await collector.can_probe_login_api(Page()))


class LoginQrClipTests(unittest.TestCase):
    def test_padded_clip_stays_inside_viewport(self):
        collector = load_collector()

        clip = collector.padded_clip(
            rect={"x": 5, "y": 10, "width": 200, "height": 220},
            viewport={"width": 300, "height": 260},
            padding=20,
        )

        self.assertEqual(clip["x"], 0)
        self.assertEqual(clip["y"], 0)
        self.assertEqual(clip["width"], 225)
        self.assertEqual(clip["height"], 250)


class LoginQrVisionTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_login_image_when_vision_does_not_find_qr(self):
        collector = load_collector()

        class Page:
            async def screenshot(self, path, clip):
                write_blank_png(Path(path))

        async def fake_login_qr_clip(page):
            return {"x": 0, "y": 0, "width": 240, "height": 240}

        original_login_qr_clip = collector.login_qr_clip
        try:
            collector.login_qr_clip = fake_login_qr_clip
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(collector.CollectionError, "login_qr_not_found"):
                    await collector.save_login_image(Page(), Path(tmp) / "login.png")
        finally:
            collector.login_qr_clip = original_login_qr_clip


if __name__ == "__main__":
    unittest.main()
