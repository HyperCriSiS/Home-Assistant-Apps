#!/usr/bin/env python3
"""Build, test and publish the exact MCPHub version consumed by Supervisor.

The version tag is created only after both architectures pass the container
integration test. Existing version tags are verified and never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml

IMAGE = "ghcr.io/hypercrisis/mcphub"
SOURCE_LABEL = "io.mcphub.source-sha256"
PLATFORMS = {"amd64": "amd64", "aarch64": "arm64"}
ACCEPT = ", ".join((
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
))


def run(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, text=True, **kwargs)


def metadata(source: Path) -> tuple[str, str]:
    config = yaml.safe_load((source / "config.yaml").read_text(encoding="utf-8"))
    if config.get("image") != IMAGE or set(config["arch"]) != set(PLATFORMS):
        raise ValueError("Unexpected MCPHub image or architecture configuration")
    version = config["version"]
    if not re.fullmatch(r"v\d{4}\.\d{2}\.\d{2}(?:-[1-9]\d*)?(?:-dev\.\d+)?", version):
        raise ValueError(f"Unexpected MCPHub version: {version}")
    build = yaml.safe_load((source / "build.yaml").read_text(encoding="utf-8"))
    bases = {build["build_from"][arch] for arch in PLATFORMS}
    if len(bases) != 1:
        raise ValueError("Both architectures must use the same pinned MCPHub base")
    return version, bases.pop()


def source_hash(source: Path) -> str:
    """Hash the build inputs, excluding the provenance marker and release notes.

    A candidate can be merged into main without rebuilding its immutable tag:
    commit IDs and release notes can differ while the packaged code is identical.
    Fail closed if COPY starts using an unsupported form instead of silently
    omitting new build inputs.
    """
    files = {"Dockerfile", "build.yaml"}
    for line in (source / "Dockerfile").read_text(encoding="utf-8").splitlines():
        if not line.startswith("COPY "):
            continue
        args = shlex.split(line)[1:]
        if args[0].startswith("--from="):
            continue
        if len(args) != 2 or args[0].startswith("--"):
            raise ValueError(f"Unsupported Dockerfile instruction: {line}")
        name = args[0]
        if name == ".haos-source-revision":
            continue
        path = source / name
        if not path.is_file() or path.resolve().parent != source.resolve():
            raise ValueError(f"Unsupported COPY source: {name}")
        files.add(name)
    digest = hashlib.sha256()
    for name in sorted(files):
        content = (source / name).read_bytes()
        digest.update(name.encode() + b"\0" + str(len(content)).encode() + b"\0" + content)
    return digest.hexdigest()


def existing_manifest(reference: str) -> dict | None:
    result = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", "--raw", reference],
        check=False, capture_output=True, text=True,
    )
    if result.returncode == 0:
        return json.loads(result.stdout)
    if re.search(rf"{re.escape(reference)}: not found\b|manifest unknown\b", result.stderr, re.I):
        return None
    raise RuntimeError(f"Cannot inspect {reference}: {result.stderr.strip()}")


def public_json(url: str, token: str = "") -> dict:
    headers = {"Accept": ACCEPT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


def verify_public(version: str, fingerprint: str) -> None:
    """Check anonymous access, both architectures and the actual image labels."""
    repository = IMAGE.removeprefix("ghcr.io/")
    query = urlencode({"service": "ghcr.io", "scope": f"repository:{repository}:pull"})
    try:
        # No workflow credentials: Home Assistant must be able to pull this way.
        token = public_json(f"https://ghcr.io/token?{query}")["token"]
        base = f"https://ghcr.io/v2/{repository}"
        manifest = public_json(f"{base}/manifests/{version}", token)
        descriptors = manifest.get("manifests", [])
        architectures = [item.get("platform", {}) for item in descriptors]
        expected = [{"os": "linux", "architecture": arch} for arch in PLATFORMS.values()]
        if len(architectures) != 2 or any(
            not any(all(actual.get(k) == v for k, v in wanted.items()) for actual in architectures)
            for wanted in expected
        ):
            raise ValueError("Published MCPHub manifest must contain linux/amd64 and linux/arm64")
        for item in descriptors:
            arch = item["platform"]["architecture"]
            child = public_json(f"{base}/manifests/{item['digest']}", token)
            config = public_json(f"{base}/blobs/{child['config']['digest']}", token)
            labels = config["config"]["Labels"]
            ha_arch = next(name for name, platform in PLATFORMS.items() if platform == arch)
            if (config.get("architecture") != arch or config.get("os") != "linux"
                    or labels.get(SOURCE_LABEL) != fingerprint
                    or labels.get("io.hass.version") != version
                    or labels.get("io.hass.arch") != ha_arch):
                raise ValueError(f"Existing {version}/{arch} differs from the requested build; bump the App version")
    except HTTPError as error:
        error.close()
        raise RuntimeError(
            f"Anonymous pull of {IMAGE}:{version} failed (HTTP {error.code}). "
            "For a new package, set its visibility to Public in GitHub package settings and rerun."
        ) from error


def publish(source: Path, revision: str, integration_script: Path) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("An exact 40-character source commit is required")
    version, base = metadata(source)
    fingerprint = source_hash(source)
    reference = f"{IMAGE}:{version}"
    if existing_manifest(reference) is not None:
        verify_public(version, fingerprint)
        print(f"Verified existing immutable image {reference}", flush=True)
        return

    # Do not modify the checked-out source or accidentally bundle local caches.
    with tempfile.TemporaryDirectory(prefix="mcphub-image-") as temporary:
        context = Path(temporary) / "MCPHub"
        shutil.copytree(source, context, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (context / ".haos-source-revision").write_text(revision + "\n", encoding="utf-8")
        tags = []
        for arch, platform in PLATFORMS.items():
            tag = f"{reference}-{arch}"
            run(
                "docker", "buildx", "build", "--pull", "--load",
                "--platform", f"linux/{platform}",
                "--build-arg", f"BUILD_FROM={base}",
                "--build-arg", f"BUILD_ARCH={arch}",
                "--build-arg", f"BUILD_VERSION={version}",
                "--label", f"{SOURCE_LABEL}={fingerprint}",
                "--label", f"org.opencontainers.image.revision={revision}",
                "--tag", tag, str(context),
            )
            run("docker", "run", "--rm", "--entrypoint", "/usr/local/bin/gh", tag, "--version")
            run("docker", "run", "--rm", "--entrypoint", "/usr/local/bin/tunnel-client", tag, "--version")
            run(
                "docker", "run", "--rm", "--entrypoint", "/opt/gh-cli-mcp/bin/python", tag,
                "-c", "from gh_cli_mcp_server.server import mcp; assert mcp is not None",
            )
            run("bash", str(integration_script.resolve()), tag)
            tags.append(tag)
        # Neither architecture is published until both have passed the same tests.
        for tag in tags:
            run("docker", "push", tag)
        run("docker", "buildx", "imagetools", "create", "--tag", reference, *tags)
    verify_public(version, fingerprint)
    print(f"Published and verified anonymous access to {reference}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("MCPHub"))
    parser.add_argument("--revision", required=True)
    parser.add_argument("--integration-script", type=Path,
                        default=Path(__file__).with_name("integration-test-mcphub.sh"))
    args = parser.parse_args()
    publish(args.source, args.revision, args.integration_script)


if __name__ == "__main__":
    main()
