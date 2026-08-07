from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "creator-platform-data"


class UnifiedSkillPackageTests(unittest.TestCase):
    def test_unified_skill_package_exists_with_platform_collectors(self):
        self.assertTrue((SKILL / "SKILL.md").is_file())
        self.assertTrue((SKILL / "agents" / "openai.yaml").is_file())
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
            "web_session=",
            "id_token=",
            "x-s-common:",
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


if __name__ == "__main__":
    unittest.main()
