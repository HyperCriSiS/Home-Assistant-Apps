# Changelog

## v2026.10.17-1-dev.111

### Commits in this Dev build

- [`1e53b57`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/1e53b5717f62af5a7ed1b54f641dfde10910bd82) Merge pull request #75 from HyperCriSiS/fix/mcphub-standalone-tunnel-console
- [`07c0f82`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/07c0f82202a2fd393f5660910cf0026b7553589c) style(mcphub): use exactly one trailing YAML newline
- [`1ffcf57`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/1ffcf5701de315dd0b9bd0b15360342a7eb03623) style(mcphub): preserve final YAML newline for yamllint
- [`193f47a`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/193f47a7c54db68abd73e46fb829d4c338fe3936) test(mcphub): align English assertions and gateway labels
- [`8b0a441`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/8b0a44196a293902da70965b65a8c23616e8ff97) fix(mcphub): restore YAML trailing newline and English status age
- [`b346e61`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/b346e617080a32db56b8e8690fbb1335179c292b) fix(mcphub): remove remaining German tunnel console copy
- [`e6fb7fa`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/e6fb7fa61202be6586fc46ed8a6143751228db18) fix(mcphub): use English consistently in tunnel console and documentation
- [`9ded304`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/9ded304656137fd8796ee3ee858866f601afd0c5) test(mcphub): validate Tailscale control API and key-rotation boundaries
- [`d2b1930`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/d2b1930ac0615f3775b6786408254f64a4f81f3e) docs(mcphub): use verified Tailscale App binary path for manual Funnel CLI
- [`31c5f90`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/31c5f90bfa5557f69bdc05f3b4b3a047adc8f2ac) ci(mcphub): validate optional Tailscale group and disabled-by-default host port
- [`71af22a`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/71af22ae8b8ac409554b4d620d422e96e71dc3e8) security(mcphub): reject dot-segment traversal in every MCP route validator
- [`623a72d`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/623a72de4684b59809043ccfdaaddd8c727fc4b8) test(mcphub): cover third config group and revise dashboard card assertions
- [`d5474ed`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/d5474edff96a8edaf34065413a21b790ecc0201f) test(ci): exercise actual Tailscale MCP gateway, isolation, stop/start and key revocation
- [`26be422`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/26be422ba4c67a08ec1a963d44793cdf3fad0f8c) test(mcphub): cover Tailscale gateway isolation, key scopes, persistence and HTTPS validation
- [`d7664c2`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/d7664c24607ef0607b5873494cdc9c469b93459f) style(mcphub): preserve terminal newlines across all changed sources
- [`04e3ab3`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/04e3ab3780544b2b096e80cd4a6bb13ff2985b50) docs(test): integrate Tailscale configuration and preserve Store README unchanged
- [`7674771`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/76747719957e851d8ecb357b4a0566bf487f2f64) ui(mcphub): integrate Tailscale into one unified tunnel dashboard card
- [`4d1212c`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/4d1212cc78ed56a0919383a94abb9afe858aaa9c) feat(mcphub): expose ingress-only Tailscale gateway and client-key controls
- [`9dbbe03`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/9dbbe037258e3f76273c301b565b4d0ff090fd0f) feat(mcphub): add optional Tailscale MCP-only host origin with isolated route keys
- [`dd72d7e`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/dd72d7eaa9dce0743d72a1ad21806f968deff649) feat(mcphub): isolated Tailscale MCP gateway state and safe HTTPS checks
- [`ea51bdd`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/ea51bdd2ef9fad7b11856b45a927d2bd2248dfc2) Merge branch 'dev-mcphub' into fix/mcphub-standalone-tunnel-console
- [`665af5d`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/665af5d8907513d4a4643d3dbba860a0fce7b97c) test(mcphub): adapt tunnel UI tests to independent dashboard
- [`12f32db`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/12f32db68b0a8887488eb341f04338a33965256c) chore(mcphub): remove unused injected navigation script
- [`a70ef53`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/a70ef53af6603316995993e1eb07554b61c6d8b7) chore(mcphub): remove unused injected navigation script
- [`6b75ac0`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/6b75ac0cd49dd8373bfd638c6cf2eb12ecae65b1) test(docs): verify standalone console and document HA configuration limitation
- [`c556552`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/c5565520d4be4cdb33efd25f3bc014d5b9288f9d) fix(mcphub): remove injected dashboard menu and isolate tunnel UI
- [`d79c2e4`](https://github.com/HyperCriSiS/Home-Assistant-Apps/commit/d79c2e4624985ae7d9620841193f6414b0d5a5b9) feat(mcphub): add clean standalone tunnel control console
