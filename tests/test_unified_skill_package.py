from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "creator-platform-data"


class UnifiedSkillPackageTests(unittest.TestCase):
    def test_unified_skill_package_exists_with_platform_collectors(self):
        self.assertTrue((SKILL / "SKILL.md").is_file())
        self.assertTrue((SKILL / "agents" / "openai.yaml").is_file())
        self.assertTrue((SKILL / "accounts.example.yaml").is_file())
        self.assertTrue((ROOT / "accounts.example.yaml").is_file())
        self.assertTrue((ROOT / "scripts" / "run_accounts.py").is_file())
        self.assertTrue((SKILL / "scripts" / "run_accounts.py").is_file())
        self.assertTrue((SKILL / "scripts" / "collect_douyin.py").is_file())
        self.assertTrue((SKILL / "scripts" / "collect_xiaohongshu.py").is_file())
        self.assertTrue((SKILL / "references" / "unified-schema.md").is_file())
        self.assertTrue((SKILL / "references" / "douyin-sheet-schema.md").is_file())
        self.assertTrue((SKILL / "references" / "xiaohongshu-sheet-schema.md").is_file())

    def test_unified_skill_metadata_names_one_skill_not_two(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: creator-platform-data", text)
        self.assertNotIn("douyin-creator-daily-sheet", text)
        self.assertNotIn("xiaohongshu-creator-data", text)
        self.assertIn("用于", text.split("---", 2)[1])

    def test_unified_skill_does_not_package_local_outputs_or_auth_material(self):
        packaged_files = [path.relative_to(SKILL).as_posix() for path in SKILL.rglob("*") if path.is_file()]
        self.assertTrue(all(not name.startswith("outputs/") for name in packaged_files))
        self.assertTrue(all("__pycache__" not in name for name in packaged_files))

        raw_auth_markers = [
            "author" + "ization;",
            "Cook" + "ie:",
            "cook" + "ie:",
            "web_" + "session=",
            "id_" + "token=",
            "x-s-" + "common:",
        ]
        combined = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in SKILL.rglob("*")
            if path.is_file()
        )
        for marker in raw_auth_markers:
            self.assertNotIn(marker, combined)

    def test_project_and_skill_documentation_are_chinese(self):
        paths = [
            ROOT / "README.md",
            ROOT / "PROJECT.md",
            SKILL / "SKILL.md",
            SKILL / "agents" / "openai.yaml",
            SKILL / "references" / "unified-schema.md",
            SKILL / "references" / "douyin-sheet-schema.md",
            SKILL / "references" / "xiaohongshu-sheet-schema.md",
        ]
        required_terms = ["创作者", "抖音", "小红书", "二维码", "统一"]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertTrue(any("\u4e00" <= char <= "\u9fff" for char in text))
                self.assertTrue(any(term in text for term in required_terms))

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## 统一 Skill", readme)
        self.assertIn("## 平台选择", skill)
        self.assertNotIn("## Unified Skill", readme)
        self.assertNotIn("## Platform Decision", skill)

    def test_xiaohongshu_qr_login_step_is_mandatory_and_script_driven(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        required_phrases = [
            "必须运行 `scripts/collect_xiaohongshu.py`",
            "必须点击二维码登录入口",
            "不要停在手机号/验证码登录页",
            "login_required",
            "qr_image",
            "只有脚本输出 `login_required` 后，才展示 `qr_image`",
            "不要要求用户自己找二维码",
            "裁剪后的二维码",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_multi_account_rules_are_explicit(self):
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        unified_schema = (SKILL / "references" / "unified-schema.md").read_text(encoding="utf-8")
        example = (ROOT / "accounts.example.yaml").read_text(encoding="utf-8")

        required_phrases = [
            "accounts.example.yaml",
            "scripts/run_accounts.py",
            "每个平台、每个账号必须使用独立 `profile_dir`",
            "不要用 `account_name` 作为唯一标识",
            "`account_key`",
            "`platform + account_key + data_date + content_id`",
            "某个账号失败时继续采集其他账号",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, skill)

        self.assertIn("account_key", unified_schema)
        self.assertIn("platform + account_key + data_date + content_id", unified_schema)
        self.assertIn("account_key: douyin_main", example)
        self.assertIn("account_key: xiaohongshu_main", example)


if __name__ == "__main__":
    unittest.main()
