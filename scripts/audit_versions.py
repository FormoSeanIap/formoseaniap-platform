#!/usr/bin/env python3
"""Audit runtime and dependency versions used by this repository.

Default mode is offline and reads only repository files.
Use --network to fetch current upstream releases and emit update warnings.
"""

from __future__ import annotations

import argparse
import ast
import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY_PATH = ROOT / "tooling" / "version-policy.yml"
README_PATH = ROOT / "README.md"
SITE_VALIDATE_ACTION = ROOT / ".github" / "actions" / "site-validate" / "action.yml"
INFRA_MAIN = ROOT / "infra" / "main.tf"
TF_LOCK = ROOT / "infra" / ".terraform.lock.hcl"
WORKFLOW_GLOBS = (
    ROOT / ".github" / "workflows",
    ROOT / ".github" / "actions",
)
USER_AGENT = "formoseaniap-platform-version-audit/1.0"


@dataclass
class Finding:
    severity: str
    item: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit repo runtime and dependency versions.")
    parser.add_argument("--network", action="store_true", help="Fetch latest upstream versions.")
    parser.add_argument(
        "--policy",
        default=str(DEFAULT_POLICY_PATH),
        help="Path to the version policy file.",
    )
    parser.add_argument("--summary-out", help="Write a markdown summary to this path.")
    parser.add_argument("--json-out", help="Write machine-readable results to this path.")
    return parser.parse_args()


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_scalar(raw_value: str) -> Any:
    value = raw_value.strip()
    if not value:
        return ""
    if value in {"true", "false"}:
        return value == "true"
    if value == "null":
        return None
    if value[0] in {'"', "'"} and value[-1] == value[0]:
        return ast.literal_eval(value)
    if value[0] in "[{":
        return json.loads(value)
    return value


def load_policy(path: Path) -> dict[str, Any]:
    lines = load_text(path).splitlines()
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(0, root)]

    for lineno, original_line in enumerate(lines, start=1):
        line = original_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent % 2 != 0:
            raise ValueError(f"{path}:{lineno}: indentation must use multiples of two spaces")

        while len(stack) > 1 and indent < stack[-1][0]:
            stack.pop()

        if indent > stack[-1][0] and indent != stack[-1][0] + 2:
            raise ValueError(f"{path}:{lineno}: indentation jumped unexpectedly")

        stripped = line.strip()
        if ":" not in stripped:
            raise ValueError(f"{path}:{lineno}: expected 'key: value' mapping")

        key, _, raw_value = stripped.partition(":")
        key = key.strip()
        raw_value = raw_value.strip()

        parent = stack[-1][1]
        if not raw_value:
            nested: dict[str, Any] = {}
            parent[key] = nested
            stack.append((indent + 2, nested))
            continue

        parent[key] = parse_scalar(raw_value)

    return root


def find_required(pattern: str, text: str, label: str, flags: int = 0) -> str:
    match = re.search(pattern, text, flags)
    if not match:
        raise ValueError(f"Could not find {label}")
    return match.group(1)


def collect_workflow_files() -> list[Path]:
    files: list[Path] = []
    for base in WORKFLOW_GLOBS:
        if not base.exists():
            continue
        files.extend(sorted(base.rglob("*.yml")))
    return files


def collect_action_versions(paths: list[Path]) -> dict[str, list[str]]:
    versions: dict[str, set[str]] = {}
    pattern = re.compile(r"uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([^\s#]+)")

    for path in paths:
        for (repo, version) in pattern.findall(load_text(path)):
            versions.setdefault(repo, set()).add(version)

    return {repo: sorted(tags) for (repo, tags) in sorted(versions.items())}


def collect_setup_terraform_versions(paths: list[Path]) -> list[str]:
    versions: list[str] = []

    for path in paths:
        lines = load_text(path).splitlines()
        for index, line in enumerate(lines):
            if "uses:" not in line or "hashicorp/setup-terraform@" not in line:
                continue

            indent = len(line) - len(line.lstrip(" "))
            block_lines: list[str] = []
            for next_line in lines[index + 1 :]:
                next_stripped = next_line.lstrip()
                next_indent = len(next_line) - len(next_stripped)
                if next_stripped.startswith("- ") and next_indent == indent:
                    break
                block_lines.append(next_line)

            block_text = "\n".join(block_lines)
            match = re.search(r'terraform_version:\s*"?([^\s"]+)"?', block_text)
            if match:
                versions.append(match.group(1))

    return sorted(set(versions))


def detect_node_configuration() -> str | None:
    for path in (ROOT / ".nvmrc", ROOT / ".node-version"):
        if path.exists():
            return load_text(path).strip()

    package_json = ROOT / "package.json"
    if package_json.exists():
        payload = json.loads(load_text(package_json))
        if isinstance(payload, dict):
            engines = payload.get("engines")
            if isinstance(engines, dict) and isinstance(engines.get("node"), str):
                return engines["node"]

    return None


def collect_repo_state() -> dict[str, Any]:
    workflow_files = collect_workflow_files()
    main_tf = load_text(INFRA_MAIN)
    lock_tf = load_text(TF_LOCK)
    readme = load_text(README_PATH)

    return {
        "python": {
            "ci_version": find_required(r'python-version:\s*"([^"]+)"', load_text(SITE_VALIDATE_ACTION), "CI Python version"),
            "docs_minimum": find_required(r"- Python ([0-9][0-9.+]+)", readme, "README Python prerequisite"),
        },
        "terraform": {
            "required_version": find_required(r'required_version\s*=\s*"([^"]+)"', main_tf, "Terraform required_version"),
            "aws_provider_constraint": find_required(
                r'source\s*=\s*"hashicorp/aws"\s*version\s*=\s*"([^"]+)"',
                main_tf,
                "AWS provider constraint",
                flags=re.S,
            ),
            "aws_provider_lock_version": find_required(
                r'provider "registry\.terraform\.io/hashicorp/aws"\s*\{\s*version\s*=\s*"([^"]+)"',
                lock_tf,
                "AWS provider lock version",
                flags=re.S,
            ),
            "workflow_cli_versions": collect_setup_terraform_versions(workflow_files),
        },
        "github_actions": {
            "versions": collect_action_versions(workflow_files),
        },
        "node": {
            "configured_version": detect_node_configuration(),
        },
    }


def parse_version_numbers(raw: str) -> tuple[int, ...]:
    matches = re.findall(r"\d+", raw)
    return tuple(int(item) for item in matches)


def version_line_prefix(raw: str, width: int) -> tuple[int, ...]:
    numbers = parse_version_numbers(raw)
    return numbers[:width]


def fetch_text(url: str, *, token: str | None = None) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            payload = gzip.decompress(payload)
        return payload.decode("utf-8")


def fetch_json(url: str, *, token: str | None = None) -> Any:
    return json.loads(fetch_text(url, token=token))


def fetch_latest_versions(tracked_actions: list[str]) -> tuple[dict[str, Any], list[Finding]]:
    token = os.environ.get("GITHUB_TOKEN")
    latest: dict[str, Any] = {"github_actions": {}}
    findings: list[Finding] = []

    try:
        payload = fetch_json("https://checkpoint-api.hashicorp.com/v1/check/terraform")
        latest["terraform_cli"] = payload.get("current_version", "")
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        findings.append(Finding("warning", "Terraform CLI", f"Could not fetch latest Terraform CLI version: {exc}"))

    try:
        payload = fetch_json("https://registry.terraform.io/v1/providers/hashicorp/aws")
        latest["terraform_aws_provider"] = payload.get("version", "")
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        findings.append(Finding("warning", "Terraform AWS provider", f"Could not fetch latest provider version: {exc}"))

    try:
        page = fetch_text("https://www.python.org/downloads/")
        match = re.search(r"Download Python ([0-9.]+)", page)
        if not match:
            raise ValueError("latest Python release marker not found")
        latest["python"] = match.group(1)
    except (urllib.error.URLError, ValueError) as exc:
        findings.append(Finding("warning", "Python", f"Could not fetch latest Python version: {exc}"))

    try:
        payload = fetch_json("https://nodejs.org/dist/index.json")
        lts_versions = [entry["version"].lstrip("v") for entry in payload if entry.get("lts")]
        latest["node_lts"] = lts_versions[0] if lts_versions else ""
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as exc:
        findings.append(Finding("warning", "Node.js", f"Could not fetch latest Node.js LTS version: {exc}"))

    for repo in tracked_actions:
        try:
            payload = fetch_json(f"https://api.github.com/repos/{repo}/releases/latest", token=token)
            latest["github_actions"][repo] = payload.get("tag_name", "")
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            findings.append(Finding("warning", repo, f"Could not fetch latest release tag: {exc}"))

    return latest, findings


def append_if(condition: bool, findings: list[Finding], severity: str, item: str, message: str) -> None:
    if condition:
        findings.append(Finding(severity, item, message))


def evaluate(policy: dict[str, Any], state: dict[str, Any], latest: dict[str, Any] | None) -> list[Finding]:
    findings: list[Finding] = []

    python_policy = policy["python"]
    append_if(
        state["python"]["ci_version"] != python_policy["ci_version"],
        findings,
        "error",
        "Python CI",
        f'Expected CI Python {python_policy["ci_version"]}, found {state["python"]["ci_version"]}.',
    )
    append_if(
        state["python"]["docs_minimum"] != python_policy["docs_minimum"],
        findings,
        "error",
        "Python docs",
        f'Expected README Python prerequisite {python_policy["docs_minimum"]}, found {state["python"]["docs_minimum"]}.',
    )

    terraform_policy = policy["terraform"]
    append_if(
        state["terraform"]["required_version"] != terraform_policy["required_version"],
        findings,
        "error",
        "Terraform required_version",
        f'Expected required_version {terraform_policy["required_version"]}, found {state["terraform"]["required_version"]}.',
    )
    append_if(
        state["terraform"]["aws_provider_constraint"] != terraform_policy["aws_provider_constraint"],
        findings,
        "error",
        "Terraform AWS provider",
        f'Expected provider constraint {terraform_policy["aws_provider_constraint"]}, found {state["terraform"]["aws_provider_constraint"]}.',
    )

    if terraform_policy.get("warn_if_workflow_cli_floats") and not state["terraform"]["workflow_cli_versions"]:
        findings.append(
            Finding(
                "warning",
                "Terraform CLI workflows",
                "Terraform CLI is not pinned in workflows; setup-terraform will resolve the latest CLI at run time.",
            )
        )

    tracked_repositories = set(policy["github_actions"]["tracked_repositories"])
    current_repositories = set(state["github_actions"]["versions"])
    missing = sorted(tracked_repositories - current_repositories)
    if missing:
        findings.append(
            Finding(
                "warning",
                "GitHub Actions",
                "Tracked actions not found in workflow files: " + ", ".join(missing),
            )
        )

    if latest:
        python_latest = latest.get("python")
        if python_latest and version_line_prefix(state["python"]["ci_version"], 2) < version_line_prefix(python_latest, 2):
            findings.append(
                Finding(
                    "warning",
                    "Python CI",
                    f'CI Python {state["python"]["ci_version"]} is behind latest stable Python {python_latest}.',
                )
            )

        provider_latest = latest.get("terraform_aws_provider")
        if provider_latest and parse_version_numbers(state["terraform"]["aws_provider_lock_version"]) < parse_version_numbers(provider_latest):
            findings.append(
                Finding(
                    "warning",
                    "Terraform AWS provider",
                    f'AWS provider lockfile {state["terraform"]["aws_provider_lock_version"]} is behind latest {provider_latest}.',
                )
            )

        node_current = state["node"]["configured_version"]
        node_latest = latest.get("node_lts")
        if node_current and node_latest and version_line_prefix(node_current, 1) < version_line_prefix(node_latest, 1):
            findings.append(
                Finding(
                    "warning",
                    "Node.js",
                    f'Configured Node.js {node_current} is behind latest LTS {node_latest}.',
                )
            )

        action_latest = latest.get("github_actions", {})
        for (repo, tags) in state["github_actions"]["versions"].items():
            latest_tag = action_latest.get(repo)
            if not latest_tag:
                continue
            current_major = version_line_prefix(tags[-1], 1)
            latest_major = version_line_prefix(latest_tag, 1)
            if current_major and latest_major and current_major < latest_major:
                findings.append(
                    Finding(
                        "warning",
                        repo,
                        f'Workflow tag {", ".join(tags)} is behind latest release {latest_tag}.',
                    )
                )

    return findings


def render_markdown(policy_path: Path, state: dict[str, Any], latest: dict[str, Any] | None, findings: list[Finding]) -> str:
    lines = [
        "## Version Audit",
        "",
        f"- Policy: `{policy_path.relative_to(ROOT)}`",
        "",
        "### Current Repo State",
        "",
        f'- Python CI: `{state["python"]["ci_version"]}`',
        f'- Python docs minimum: `{state["python"]["docs_minimum"]}`',
        f'- Terraform required_version: `{state["terraform"]["required_version"]}`',
        f'- Terraform AWS provider constraint: `{state["terraform"]["aws_provider_constraint"]}`',
        f'- Terraform AWS provider lock: `{state["terraform"]["aws_provider_lock_version"]}`',
    ]

    if state["terraform"]["workflow_cli_versions"]:
        lines.append(f'- Terraform CLI pins in workflows: `{", ".join(state["terraform"]["workflow_cli_versions"])}`')
    else:
        lines.append("- Terraform CLI pins in workflows: `floating latest`")

    node_version = state["node"]["configured_version"]
    lines.append(f'- Node.js config: `{node_version or "not configured"}`')

    lines.extend(["", "### GitHub Actions Tags", ""])
    for (repo, tags) in state["github_actions"]["versions"].items():
        lines.append(f'- `{repo}`: `{", ".join(tags)}`')

    if latest:
        lines.extend(["", "### Latest Upstream Versions", ""])
        if latest.get("python"):
            lines.append(f'- Python stable: `{latest["python"]}`')
        if latest.get("terraform_cli"):
            lines.append(f'- Terraform CLI stable: `{latest["terraform_cli"]}`')
        if latest.get("terraform_aws_provider"):
            lines.append(f'- Terraform AWS provider: `{latest["terraform_aws_provider"]}`')
        if latest.get("node_lts"):
            lines.append(f'- Node.js LTS: `{latest["node_lts"]}`')
        for (repo, tag) in sorted(latest.get("github_actions", {}).items()):
            if tag:
                lines.append(f'- `{repo}` latest release: `{tag}`')

    lines.extend(["", "### Findings", ""])
    if not findings:
        lines.append("- No issues detected.")
    else:
        for finding in findings:
            lines.append(f"- `{finding.severity}` {finding.item}: {finding.message}")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    policy_path = Path(args.policy).resolve()
    try:
        policy = load_policy(policy_path)
        state = collect_repo_state()
    except Exception as exc:  # pragma: no cover - surfaced directly to CLI
        print(f"version audit failed during local analysis: {exc}", file=sys.stderr)
        return 1

    latest: dict[str, Any] | None = None
    findings: list[Finding] = []
    if args.network:
        latest, network_findings = fetch_latest_versions(policy["github_actions"]["tracked_repositories"])
        findings.extend(network_findings)

    findings.extend(evaluate(policy, state, latest))
    markdown = render_markdown(policy_path, state, latest, findings)
    print(markdown, end="")

    if args.summary_out:
        summary_path = Path(args.summary_out)
        summary_path.write_text(markdown, encoding="utf-8")

    if args.json_out:
        payload = {
            "state": state,
            "latest": latest,
            "findings": [asdict(item) for item in findings],
        }
        Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return 1 if any(item.severity == "error" for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
