from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKING_DIR = REPO_ROOT / "infra"
DEFAULT_TF_DATA_DIR = DEFAULT_WORKING_DIR / ".terraform-validate-local"
DEPRECATION_PATTERN = re.compile(r"\bdeprecat(?:ed|ion)\b", re.IGNORECASE)


@dataclass(frozen=True)
class DiagnosticLocation:
    filename: str | None
    line: int | None
    column: int | None


@dataclass(frozen=True)
class TerraformDiagnostic:
    severity: str
    summary: str
    detail: str
    location: DiagnosticLocation


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Terraform fmt/init/validate and fail on deprecation diagnostics."
    )
    parser.add_argument(
        "--working-dir",
        default=str(DEFAULT_WORKING_DIR),
        help="Terraform root directory to validate. Defaults to infra/.",
    )
    parser.add_argument(
        "--tf-data-dir",
        default=str(DEFAULT_TF_DATA_DIR),
        help="TF_DATA_DIR path used for backendless init and validate cache.",
    )
    return parser.parse_args(argv)


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else Path.cwd() / path


def make_env(*, tf_data_dir: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if tf_data_dir is not None:
        env["TF_DATA_DIR"] = str(tf_data_dir)
    return env


def run_command(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=str(cwd),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required command not found: {args[0]}") from exc


def load_diagnostics_from_payload(payload: dict[str, Any]) -> list[TerraformDiagnostic]:
    diagnostics: list[TerraformDiagnostic] = []
    for item in payload.get("diagnostics", []):
        diagnostic_range = item.get("range") or {}
        start = diagnostic_range.get("start") or {}
        diagnostics.append(
            TerraformDiagnostic(
                severity=str(item.get("severity") or ""),
                summary=str(item.get("summary") or "").strip(),
                detail=str(item.get("detail") or "").strip(),
                location=DiagnosticLocation(
                    filename=str(diagnostic_range.get("filename")) if diagnostic_range.get("filename") else None,
                    line=int(start["line"]) if isinstance(start.get("line"), int) else None,
                    column=int(start["column"]) if isinstance(start.get("column"), int) else None,
                ),
            )
        )
    return diagnostics


def is_deprecation_diagnostic(diagnostic: TerraformDiagnostic) -> bool:
    if diagnostic.severity.lower() != "warning":
        return False
    return bool(
        DEPRECATION_PATTERN.search(diagnostic.summary)
        or DEPRECATION_PATTERN.search(diagnostic.detail)
    )


def format_diagnostic(diagnostic: TerraformDiagnostic) -> str:
    location_parts = []
    if diagnostic.location.filename:
        location_parts.append(diagnostic.location.filename)
    if diagnostic.location.line is not None:
        location_parts.append(str(diagnostic.location.line))
    if diagnostic.location.column is not None:
        location_parts.append(str(diagnostic.location.column))
    location = ":".join(location_parts)

    if diagnostic.detail:
        if location:
            return f"- {location}: {diagnostic.summary} - {diagnostic.detail}"
        return f"- {diagnostic.summary} - {diagnostic.detail}"

    if location:
        return f"- {location}: {diagnostic.summary}"
    return f"- {diagnostic.summary}"


def print_process_failure(
    result: subprocess.CompletedProcess[str],
    *,
    command_label: str,
) -> None:
    print(f"{command_label} failed with exit code {result.returncode}.", file=sys.stderr)
    if result.stdout.strip():
        print(result.stdout.rstrip(), file=sys.stderr)
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)


def validate_payload(
    payload: dict[str, Any],
    *,
    validate_exit_code: int,
) -> tuple[list[TerraformDiagnostic], list[TerraformDiagnostic]]:
    diagnostics = load_diagnostics_from_payload(payload)
    errors = [diagnostic for diagnostic in diagnostics if diagnostic.severity.lower() == "error"]
    deprecations = [diagnostic for diagnostic in diagnostics if is_deprecation_diagnostic(diagnostic)]

    if validate_exit_code != 0 and not errors:
        raise ValueError("terraform validate exited nonzero without returning error diagnostics.")

    return (errors, deprecations)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    working_dir = _resolve_path(args.working_dir)
    tf_data_dir = _resolve_path(args.tf_data_dir)

    if not working_dir.exists():
        print(f"Terraform working directory does not exist: {working_dir}", file=sys.stderr)
        return 1

    tf_data_dir.mkdir(parents=True, exist_ok=True)
    terraform_env = make_env(tf_data_dir=tf_data_dir)
    shell_env = make_env()

    fmt_result = run_command(
        ["terraform", "fmt", "-check", "-recursive"],
        cwd=working_dir,
        env=shell_env,
    )
    if fmt_result.returncode != 0:
        print_process_failure(fmt_result, command_label="terraform fmt -check -recursive")
        return 1

    init_result = run_command(
        ["terraform", "init", "-backend=false", "-reconfigure", "-input=false"],
        cwd=working_dir,
        env=terraform_env,
    )
    if init_result.returncode != 0:
        print_process_failure(init_result, command_label="terraform init -backend=false -reconfigure -input=false")
        return 1

    validate_result = run_command(
        ["terraform", "validate", "-json"],
        cwd=working_dir,
        env=terraform_env,
    )

    try:
        payload = json.loads(validate_result.stdout)
    except json.JSONDecodeError:
        print_process_failure(validate_result, command_label="terraform validate -json")
        return 1

    try:
        errors, deprecations = validate_payload(payload, validate_exit_code=validate_result.returncode)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        print_process_failure(validate_result, command_label="terraform validate -json")
        return 1

    if errors or deprecations:
        if errors:
            print("Terraform validation reported errors:", file=sys.stderr)
            for diagnostic in errors:
                print(format_diagnostic(diagnostic), file=sys.stderr)

        if deprecations:
            print("Terraform validation reported deprecated settings:", file=sys.stderr)
            for diagnostic in deprecations:
                print(format_diagnostic(diagnostic), file=sys.stderr)
        return 1

    if validate_result.returncode != 0:
        print_process_failure(validate_result, command_label="terraform validate -json")
        return 1

    print(f"Terraform validation passed with no deprecation diagnostics in {working_dir}.")
    return 0


def entrypoint(argv: list[str] | None = None) -> int:
    try:
        return main(argv)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(entrypoint())
