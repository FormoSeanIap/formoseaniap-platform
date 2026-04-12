import unittest

from scripts.terraform_validate_strict import (
    DiagnosticLocation,
    TerraformDiagnostic,
    format_diagnostic,
    is_deprecation_diagnostic,
    load_diagnostics_from_payload,
    validate_payload,
)


class TerraformValidateStrictTests(unittest.TestCase):
    def test_load_diagnostics_reads_range_metadata(self) -> None:
        diagnostics = load_diagnostics_from_payload(
            {
                "diagnostics": [
                    {
                        "severity": "warning",
                        "summary": "Argument is deprecated",
                        "detail": "hash_key is deprecated.",
                        "range": {
                            "filename": "analytics.tf",
                            "start": {
                                "line": 46,
                                "column": 3,
                            },
                        },
                    }
                ]
            }
        )

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].location.filename, "analytics.tf")
        self.assertEqual(diagnostics[0].location.line, 46)
        self.assertEqual(diagnostics[0].location.column, 3)

    def test_warning_with_deprecated_text_is_blocking(self) -> None:
        diagnostic = TerraformDiagnostic(
            severity="warning",
            summary="Argument is deprecated",
            detail="hash_key is deprecated. Use key_schema instead.",
            location=DiagnosticLocation(filename="analytics.tf", line=46, column=3),
        )

        self.assertTrue(is_deprecation_diagnostic(diagnostic))

    def test_non_deprecation_warning_is_not_blocking(self) -> None:
        diagnostic = TerraformDiagnostic(
            severity="warning",
            summary="Experimental feature",
            detail="Something informational happened.",
            location=DiagnosticLocation(filename=None, line=None, column=None),
        )

        self.assertFalse(is_deprecation_diagnostic(diagnostic))

    def test_validate_payload_accepts_non_deprecation_warning(self) -> None:
        errors, deprecations = validate_payload(
            {
                "diagnostics": [
                    {
                        "severity": "warning",
                        "summary": "Provider note",
                        "detail": "This is advisory only.",
                    }
                ]
            },
            validate_exit_code=0,
        )

        self.assertEqual(errors, [])
        self.assertEqual(deprecations, [])

    def test_validate_payload_collects_errors(self) -> None:
        errors, deprecations = validate_payload(
            {
                "diagnostics": [
                    {
                        "severity": "error",
                        "summary": "Unsupported argument",
                        "detail": "Blocks of type x are not expected here.",
                        "range": {
                            "filename": "analytics.tf",
                            "start": {"line": 50, "column": 3},
                        },
                    }
                ]
            },
            validate_exit_code=1,
        )

        self.assertEqual(len(errors), 1)
        self.assertEqual(deprecations, [])

    def test_validate_payload_collects_deprecations(self) -> None:
        errors, deprecations = validate_payload(
            {
                "diagnostics": [
                    {
                        "severity": "warning",
                        "summary": "Argument is deprecated",
                        "detail": "range_key is deprecated. Use key_schema instead.",
                        "range": {
                            "filename": "analytics.tf",
                            "start": {"line": 70, "column": 5},
                        },
                    }
                ]
            },
            validate_exit_code=0,
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(deprecations), 1)

    def test_validate_payload_rejects_nonzero_without_error_diagnostics(self) -> None:
        with self.assertRaisesRegex(ValueError, "exited nonzero without returning error diagnostics"):
            validate_payload({"diagnostics": []}, validate_exit_code=1)

    def test_format_diagnostic_includes_location(self) -> None:
        formatted = format_diagnostic(
            TerraformDiagnostic(
                severity="warning",
                summary="Argument is deprecated",
                detail="hash_key is deprecated.",
                location=DiagnosticLocation(filename="analytics.tf", line=46, column=3),
            )
        )

        self.assertEqual(
            formatted,
            "- analytics.tf:46:3: Argument is deprecated - hash_key is deprecated.",
        )
