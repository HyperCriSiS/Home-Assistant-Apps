"""Single version/checksum source; stable updates are proposals, never releases."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def version_tuple(version):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Only stable three-component releases are supported")
    return tuple(map(int, version.split(".")))


def automatic_update_allowed(old, new):
    a, b = version_tuple(old), version_tuple(new)
    return b > a and a[0] == b[0] and (a[0] != 0 or a[1] == b[1])


def generate(manifest):
    version_tuple(manifest["version"])
    if not re.fullmatch(r"[a-f0-9]{64}", manifest["sha256"]):
        raise ValueError("Invalid wheel checksum")
    dockerfile = ROOT / "Dockerfile"
    text = dockerfile.read_text()
    for key, value in (("PTS_VERSION", manifest["version"]), ("PTS_SHA256", manifest["sha256"])):
        text, count = re.subn(rf"^ARG {key}=.*$", f"ARG {key}={value}", text, flags=re.MULTILINE)
        if count != 1:
            raise ValueError(f"Missing Docker build argument {key}")
    build = (ROOT / "build.yaml").read_text()
    build = re.sub(r'^  PTS_VERSION:.*$', f'  PTS_VERSION: "{manifest["version"]}"', build, flags=re.MULTILINE)
    build = re.sub(r'^  PTS_SHA256:.*$', f'  PTS_SHA256: "{manifest["sha256"]}"', build, flags=re.MULTILINE)
    return {dockerfile: text, ROOT / "build.yaml": build}


def update():
    manifest = json.loads((ROOT / "upstream.json").read_text())
    with urlopen("https://pypi.org/pypi/PlexTraktSync/json", timeout=30) as response:
        metadata = json.load(response)
    version = metadata["info"]["version"]
    if not automatic_update_allowed(manifest["version"], version):
        print("No eligible stable update; major/pre-1.0 minor changes require manual review")
        return
    # Require a corresponding upstream tag, then verify the actual PyPI wheel.
    subprocess.run(["git", "ls-remote", "--exit-code", "--tags", "--refs",
                    "https://github.com/Taxel/PlexTraktSync.git", f"refs/tags/{version}"],
                   check=True, capture_output=True)
    wheels = [f for f in metadata["urls"] if f["packagetype"] == "bdist_wheel"
              and f["filename"] == f"plextraktsync-{version}-py3-none-any.whl" and not f.get("yanked")]
    if len(wheels) != 1:
        raise ValueError("Expected exactly one non-yanked universal wheel")
    wheel = wheels[0]
    if not wheel["url"].startswith("https://files.pythonhosted.org/"):
        raise ValueError("Unexpected artifact host")
    with urlopen(wheel["url"], timeout=60) as response:
        digest = hashlib.sha256(response.read()).hexdigest()
    if digest != wheel["digests"]["sha256"]:
        raise ValueError("Wheel checksum mismatch")
    proposed = {"version": version, "wheel": wheel["filename"], "sha256": digest}
    files = generate(proposed)
    config = ROOT / "config.yaml"
    text = config.read_text()
    match = re.search(r'^version: "([0-9.]+)"$', text, re.MULTILINE)
    major, minor, patch = version_tuple(match.group(1))
    revision = f"{major}.{minor}.{patch + 1}"
    files[config] = text.replace(match.group(0), f'version: "{revision}"', 1)
    changelog = ROOT / "CHANGELOG.md"
    files[changelog] = changelog.read_text().replace(
        "# Changelog\n", f"# Changelog\n\n## {revision}\n\n- Propose PlexTraktSync {version}; validation and manual release approval required.\n", 1)
    files[ROOT / "upstream.json"] = json.dumps(proposed, indent=2) + "\n"
    for path, content in files.items():
        path.write_text(content, encoding="utf-8", newline="\n")


def main():
    mode = sys.argv[1]
    manifest = json.loads((ROOT / "upstream.json").read_text())
    if mode == "version":
        print(manifest["version"])
    elif mode == "check":
        for path, expected in generate(manifest).items():
            if path.read_text() != expected:
                raise ValueError(f"Generated version/checksum mismatch in {path.name}")
    elif mode == "update":
        update()
    else:
        raise ValueError("Unknown mode")


if __name__ == "__main__":
    main()
