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
        self.assertIn("Use when", text.split("---", 2)[1])

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


if __name__ == "__main__":
    unittest.main()
