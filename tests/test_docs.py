#!/usr/bin/env python3
"""Keep user/developer documentation aligned with the release artifacts."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DEVELOPMENT = ROOT / "docs/DEVELOPMENT.md"
ACCEPTANCE = ROOT / "docs/RELEASE_ACCEPTANCE.md"
COMPARISON = ROOT / "docs/INPUT_METHOD_COMPARISON.md"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
RELEASE_NOTES = ROOT / f"RELEASE_NOTES_{VERSION}.md"
RELEASE_EVIDENCE = ROOT / "docs" / f"RELEASE_EVIDENCE_{VERSION}.md"
MARKDOWN = (
    README, DEVELOPMENT, ACCEPTANCE, COMPARISON, ROOT / "data/SOURCES.md",
    ROOT / "CHANGELOG.md", RELEASE_NOTES, RELEASE_EVIDENCE,
)


class DocumentationTest(unittest.TestCase):
    def test_release_version_is_synchronized(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        readme = README.read_text(encoding="utf-8")
        binary_control = (ROOT / "debian/binary-control").read_text(encoding="utf-8")
        changelog = (ROOT / "debian/changelog").read_text(encoding="utf-8")
        package = f"xiapin-input-method_{version}_amd64.deb"
        self.assertIn(f"当前版本：**{version}**", readme)
        self.assertIn(package, readme)
        documented_versions = set(re.findall(
            r"xiapin-input-method_(\d+\.\d+\.\d+)_amd64\.deb", readme
        ))
        self.assertEqual(documented_versions, {version})
        self.assertRegex(binary_control, rf"(?m)^Version: {re.escape(version)}$")
        self.assertTrue(changelog.startswith(f"xiapin-input-method ({version}) "))

    def test_readme_has_required_user_and_developer_sections(self) -> None:
        text = README.read_text(encoding="utf-8")
        headings = {
            "功能与隐私原则", "支持范围与验证状态", "快速安装 `.deb`",
            "桌面验收", "升级", "卸载、清理和恢复", "本地学习与跨电脑迁移",
            "词典来源和许可证", "技术架构与语言", "源码目录", "从源码构建",
            "测试覆盖", "故障排查", "版本和安装包校验", "已知限制",
        }
        found = set(re.findall(r"^## (.+)$", text, re.MULTILINE))
        self.assertFalse(headings - found, f"missing README headings: {headings - found}")
        self.assertNotIn("xp 缩写", text)

    def test_local_markdown_links_exist(self) -> None:
        link = re.compile(r"\[[^]]+\]\(([^)]+)\)")
        for document in MARKDOWN:
            text = document.read_text(encoding="utf-8")
            for raw in link.findall(text):
                target = unquote(raw.split("#", 1)[0])
                if not target or re.match(r"^[a-z]+://", target):
                    continue
                path = (document.parent / target).resolve()
                self.assertTrue(path.exists(), f"broken link in {document}: {raw}")
                self.assertTrue(path.is_relative_to(ROOT.resolve()),
                                f"link escapes project in {document}: {raw}")

    def test_documented_commands_have_project_entries(self) -> None:
        text = README.read_text(encoding="utf-8")
        for command in (
            "ubuntu-cn-input-doctor", "ubuntu-cn-input-memory",
        ):
            self.assertIn(command, text)
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        for target in ("check", "test", "deb"):
            self.assertRegex(makefile, rf"(?m)^{target}:")
            self.assertIn(f"make {target}", text)

    def test_development_doc_is_packaged(self) -> None:
        rules = (ROOT / "debian/rules").read_text(encoding="utf-8")
        fallback = (ROOT / "scripts/build-deb.sh").read_text(encoding="utf-8")
        self.assertIn("docs/DEVELOPMENT.md", rules)
        self.assertIn("docs/DEVELOPMENT.md", fallback)

    def test_release_acceptance_contract_is_linked_and_packaged(self) -> None:
        readme = README.read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        rules = (ROOT / "debian/rules").read_text(encoding="utf-8")
        fallback = (ROOT / "scripts/build-deb.sh").read_text(encoding="utf-8")
        contract = ACCEPTANCE.read_text(encoding="utf-8")
        self.assertIn("docs/RELEASE_ACCEPTANCE.md", readme)
        self.assertIn("docs/RELEASE_ACCEPTANCE.md", agents)
        self.assertIn("docs/RELEASE_ACCEPTANCE.md", rules)
        self.assertIn("docs/RELEASE_ACCEPTANCE.md", fallback)
        for requirement in (
            "冷缓存直接安装", "不要写死 doctor 的 OK 数量",
            "真实 IBus 按键验收", "重启后复验", "隐私检查",
        ):
            self.assertIn(requirement, contract)

    def test_release_docs_are_packaged_and_generic(self) -> None:
        rules = (ROOT / "debian/rules").read_text(encoding="utf-8")
        fallback = (ROOT / "scripts/build-deb.sh").read_text(encoding="utf-8")
        self.assertIn("CHANGELOG.md", rules)
        self.assertIn("CHANGELOG.md", fallback)
        self.assertIn("RELEASE_NOTES_$(shell cat VERSION).md", rules)
        self.assertIn('RELEASE_NOTES_${version}.md', fallback)
        self.assertNotIn("docs/RELEASE_EVIDENCE_$(shell cat VERSION).md", rules)
        self.assertNotIn('docs/RELEASE_EVIDENCE_${version}.md', fallback)
        release_text = "\n".join(path.read_text(encoding="utf-8") for path in MARKDOWN)
        self.assertNotRegex(release_text, r"(?m)(?:^|[\s`(])/home/[^ /`)]")
        workspace_marker = ".codync/" + "bots/"
        self.assertNotIn(workspace_marker, release_text)

    def test_normal_install_needs_no_setup_command(self) -> None:
        readme = README.read_text(encoding="utf-8")
        quick_install = readme.split("## 快速安装 `.deb`", 1)[1].split(
            "## 桌面验收", 1
        )[0]
        self.assertNotIn("ubuntu-cn-input-setup --default", quick_install)
        self.assertIn("不需要另开终端执行 setup", quick_install)

    def test_watchdog_is_not_documented_as_a_current_feature(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertNotIn("ubuntu-cn-input-watchdog.timer", readme)
        self.assertNotIn("--enable-watchdog", readme)

    def test_doctor_version_is_synchronized(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        doctor = (ROOT / "scripts/doctor.sh").read_text(encoding="utf-8")
        self.assertRegex(doctor, rf'(?m)^readonly release_version="{re.escape(version)}"$')
        self.assertNotRegex(doctor, r"xiapin-input-method \d+\.\d+\.\d+ amd64")

    def test_test_dependencies_are_declared_and_documented(self) -> None:
        control = (ROOT / "debian/control").read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        for dependency in ("g++", "pkg-config", "python3-pil", "ffmpeg"):
            self.assertIn(dependency, control)
            self.assertIn(dependency, readme)


if __name__ == "__main__":
    unittest.main()
