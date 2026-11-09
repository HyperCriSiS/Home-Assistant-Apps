"""Manifest, documentation and scheduler checks for the Inbox Zero App.

Run from the repository root:
    python3 -m unittest discover -s "Inbox Zero/tests" -v
"""
import re
import subprocess
import unittest
import urllib.request
from pathlib import Path

import yaml

APP = Path(__file__).resolve().parents[1]


def read(name):
    return (APP / name).read_text(encoding="utf-8")


CONFIG = yaml.safe_load(read("config.yaml"))
COMMIT = re.search(
    r"^FROM ghcr\.io/hypercrisis/inbox-zero-base:([0-9a-f]{40})$", read("Dockerfile"), re.M
).group(1)
BASE = re.match(r"Inbox Zero (v\d+\.\d+\.\d+) ", CONFIG["description"]).group(1)


def leaves(options, prefix=""):
    """Option paths as run.sh reads them with jq, for example ".llm.api_key"."""
    for key, value in options.items():
        if isinstance(value, dict):
            yield from leaves(value, f"{prefix}.{key}")
        else:
            yield f"{prefix}.{key}"


class ManifestTests(unittest.TestCase):
    def test_identity_and_release_keys(self):
        self.assertEqual(list(CONFIG)[:6], ["name", "description", "version", "slug", "url", "image"])
        self.assertEqual(CONFIG["slug"], "inbox_zero")
        self.assertEqual(CONFIG["image"], "ghcr.io/hypercrisis/{arch}-inbox-zero")
        self.assertRegex(CONFIG["version"], r"^v\d{4}\.\d{2}\.\d{2}(\.[1-9]\d*)?$")
        self.assertTrue(CONFIG["description"].startswith(f"Inbox Zero {BASE} (fork {COMMIT[:7]}) - "))
        self.assertEqual(CONFIG["arch"], ["amd64", "aarch64"])
        self.assertIs(CONFIG["init"], False)

    def test_database_is_backed_up_cold_and_nothing_else_is_mapped(self):
        self.assertEqual(CONFIG["backup"], "cold")
        self.assertNotIn("map", CONFIG)
        self.assertEqual(CONFIG["watchdog"], "http://[HOST]:[PORT:3000]/api/health")

    def test_every_option_has_a_schema_and_is_read_at_start(self):
        self.assertEqual(sorted(leaves(CONFIG["options"])), sorted(leaves(CONFIG["schema"])))
        run = read("run.sh")
        for path in leaves(CONFIG["options"]):
            with self.subTest(option=path):
                self.assertIn(path, run)

    def test_translations_cover_every_option_and_port(self):
        for language in ("en", "de"):
            texts = yaml.safe_load(read(f"translations/{language}.yaml"))
            self.assertEqual(set(texts["network"]), set(CONFIG["ports"]))
            self.assertEqual(set(texts["configuration"]), set(CONFIG["options"]))
            for key, value in CONFIG["options"].items():
                entry = texts["configuration"][key]
                fields = entry.get("fields", {})
                self.assertEqual(set(fields), set(value) if isinstance(value, dict) else set())
                for text in (entry, *fields.values()):
                    with self.subTest(language=language, option=key):
                        self.assertTrue(text["name"] and text["description"])


class StartScriptTests(unittest.TestCase):
    def test_option_values_are_escaped_for_the_placeholder_replacement(self):
        escape = re.search(r"sed -e '(s/[^']+)'", read("run.sh")).group(1)
        value = "https://x.test/a?b=1&c=2|d\\e"
        escaped = subprocess.run(["sed", "-e", escape], input=value, capture_output=True,
                                 text=True, check=True).stdout
        result = subprocess.run(["sed", "-e", f"s|PLACEHOLDER|{escaped}|g"], input="PLACEHOLDER",
                                capture_output=True, text=True, check=True).stdout
        self.assertEqual(result, value)

    def test_stop_leaves_time_for_a_clean_database_shutdown(self):
        self.assertEqual(CONFIG["timeout"], 60)


class DocumentationTests(unittest.TestCase):
    def test_changelog_starts_with_the_app_version(self):
        self.assertTrue(read("CHANGELOG.md").startswith(f"# Changelog\n\n## {CONFIG['version']}\n"))

    def test_packaged_commit_is_named_everywhere(self):
        badge = f"badge/Inbox%20Zero-{BASE}%20({COMMIT[:7]})-"
        self.assertIn(badge, read("README.md"))
        self.assertIn(f"https://github.com/HyperCriSiS/inbox-zero/commit/{COMMIT})", read("README.md"))
        self.assertIn(f"{BASE} at fork commit {COMMIT}\n", read("NOTICE.md"))
        self.assertIn("actions/workflows/validate-inbox-zero.yml/badge.svg", read("README.md"))


class SchedulerTests(unittest.TestCase):
    """cron.sh replaces the "cron" service of the packaged docker-compose.yml."""

    def test_job_table_matches_the_packaged_compose_file(self):
        url = f"https://raw.githubusercontent.com/HyperCriSiS/inbox-zero/{COMMIT}/docker-compose.yml"
        with urllib.request.urlopen(url, timeout=30) as response:
            compose = response.read().decode("utf-8")
        cron = compose[compose.index("\n  cron:"):]
        expected = set()
        for match in re.finditer(r"http://web:3000(/api/[A-Za-z0-9/${}-]+)", cron):
            interval = int(re.search(r"sleep (\d+)", cron[match.end():]).group(1))
            names = [""]
            if "${job}" in match.group(1):
                names = re.findall(r"for job in ([^;]+);", cron[:match.start()])[-1].split()
            for name in names:
                expected.add((interval, re.sub(r"\$+\{job\}", name, match.group(1))))
        actual = {
            (int(interval), path)
            for interval, path in re.findall(r"^(\d+) \d+ (/api/\S+)$", read("cron.sh"), re.M)
        }
        self.assertGreater(len(expected), 10)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
