"""A version-only rebuild must reuse every filesystem layer of the tested image."""
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
arch = sys.argv[1]
if arch not in ('amd64', 'aarch64'):
    raise ValueError('Unsupported test architecture')
base = re.search(r'^  ' + arch + r': (\S+)$', (root / 'build.yaml').read_text(), re.M)[1]
arguments = subprocess.check_output(
    [sys.executable, str(root / 'scripts/upstreams.py'), 'args'], text=True).splitlines()
command = ['docker', 'buildx', 'build', '--load', '--tag', 'calibre-layer-check:test',
           '--build-arg', 'BUILD_FROM=' + base]
for argument in arguments:
    if not argument.startswith('BUILD_VERSION='):
        command.extend(['--build-arg', argument])
command.extend(['--build-arg', 'BUILD_VERSION=layer-check', str(root)])
subprocess.run(command, check=True)


def inspect(image):
    return json.loads(subprocess.check_output(['docker', 'image', 'inspect', image], text=True))[0]


original = inspect('calibre-aio:test')
changed = inspect('calibre-layer-check:test')
assert original['RootFS']['Layers'] == changed['RootFS']['Layers'], 'Version change rebuilt filesystem layers'
assert original['Config']['Labels']['io.hass.version'] != changed['Config']['Labels']['io.hass.version']
print('Version-only rebuild reused every filesystem layer; only image metadata changed')
