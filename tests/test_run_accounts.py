import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "run_accounts.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("run_accounts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AccountConfigTests(unittest.TestCase):
    def test_loads_accounts_and_rejects_shared_profiles(self):
        runner = load_runner()

        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "accounts.yaml"
            config.write_text(
                """
accounts:
  - platform: douyin
    account_key: douyin_main
    account_name: 抖音主账号
    profile_dir: ~/.codex/state/creator-platform-profiles/douyin/main
  - platform: xiaohongshu
    account_key: xiaohongshu_main
    account_name: 小红书主账号
    profile_dir: ~/.codex/state/creator-platform-profiles/douyin/main
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(runner.ConfigError, "profile_dir"):
                runner.load_accounts(config)

    def test_builds_platform_commands_with_account_key_and_unique_outputs(self):
        runner = load_runner()

        with tempfile.TemporaryDirectory() as tmp:
            script_root = Path(tmp) / "scripts"
            collector = script_root / "xiaohongshu" / "collect_xiaohongshu.py"
            collector.parent.mkdir(parents=True)
            collector.write_text("# placeholder\n", encoding="utf-8")

            account = runner.Account(
                platform="xiaohongshu",
                account_key="xiaohongshu_main",
                account_name="小红书主账号",
                profile_dir=Path("/tmp/xhs-main"),
                start_date="2026-05-01",
                end_date="2026-07-03",
                include_details=True,
                browser_channel="chrome",
            )
            command = runner.build_command(
                account=account,
                python_executable="/usr/bin/python3",
                output_dir=Path("/tmp/out"),
                snapshot_date="2026-08-07",
                login_stamp="20260807-130000",
                script_root=script_root,
            )

        joined = " ".join(map(str, command))
        self.assertIn("--account-key xiaohongshu_main", joined)
        self.assertIn("--account-name 小红书主账号", joined)
        self.assertIn("/tmp/out/xiaohongshu-xiaohongshu_main-2026-08-07.tsv", joined)
        self.assertIn("/tmp/out/xiaohongshu-xiaohongshu_main-login-20260807-130000.png", joined)
        self.assertIn("--include-details", joined)
        self.assertIn("--browser-channel chrome", joined)


class CommandLineTests(unittest.TestCase):
    def test_accepts_config_output_dir_and_date_range(self):
        runner = load_runner()
        old_argv = sys.argv
        try:
            sys.argv = [
                "run_accounts.py",
                "--config", "/tmp/accounts.yaml",
                "--output-dir", "/tmp/out",
                "--start-date", "2026-05-01",
                "--end-date", "2026-07-03",
                "--dry-run",
            ]
            args = runner.parse_args()
        finally:
            sys.argv = old_argv

        self.assertEqual(args.config, Path("/tmp/accounts.yaml"))
        self.assertEqual(args.output_dir, Path("/tmp/out"))
        self.assertEqual(args.start_date, "2026-05-01")
        self.assertEqual(args.end_date, "2026-07-03")
        self.assertTrue(args.dry_run)


if __name__ == "__main__":
    unittest.main()
