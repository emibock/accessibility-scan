"""verapdf integration for comprehensive PDF/UA validation

verapdf is the industry-standard, open-source PDF/UA validator developed by the PDF Association.
It provides more comprehensive validation than Python-based checks alone.

Installation: https://docs.verapdf.org/install/
"""

import asyncio
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional


class VeraPDFValidator:
    """Wrapper for verapdf command-line validator"""

    @staticmethod
    def is_available() -> bool:
        """Check if verapdf is installed and accessible"""
        try:
            result = subprocess.run(
                ["verapdf", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def get_version() -> Optional[str]:
        """Get verapdf version string"""
        try:
            result = subprocess.run(
                ["verapdf", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse version from output
                for line in result.stdout.split('\n'):
                    if 'verapdf' in line.lower():
                        return line.strip()
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    async def validate(
        self,
        pdf_path: Path,
        profile: str = "PDFUA-1",
        format: str = "json"
    ) -> Dict:
        """Run verapdf validation on a PDF file

        Args:
            pdf_path: Path to PDF file
            profile: Validation profile (PDFUA-1, WCAG-2-1, etc.)
            format: Output format (json or xml)

        Returns:
            Dict with violations in our standard format
        """
        try:
            # Build verapdf command
            # -f <profile> : validation profile
            # --format <format> : output format (json or xml)
            # --maxfailures -1 : report all failures (not just first)
            cmd = [
                "verapdf",
                "-f", profile,
                "--format", format,
                "--maxfailures", "-1",
                str(pdf_path)
            ]

            # Run verapdf
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60.0  # 1 minute timeout
            )

            if process.returncode != 0:
                # verapdf returns non-zero on validation failures, which is expected
                # Only error if we can't parse the output
                pass

            # Parse output
            if format == "json":
                return self._parse_json_output(stdout.decode('utf-8'), pdf_path)
            else:
                return self._parse_xml_output(stdout.decode('utf-8'), pdf_path)

        except asyncio.TimeoutError:
            return {
                "url": f"file://{pdf_path}",
                "file_name": pdf_path.name,
                "error": "verapdf validation timed out (>60s)",
                "violations": [{
                    "id": "verapdf-timeout",
                    "impact": "moderate",
                    "description": "verapdf validation timed out - falling back to basic checks",
                    "help": "This PDF is very large or complex. Consider splitting into smaller documents.",
                    "helpUrl": "",
                    "tags": ["verapdf"],
                    "nodes": [{
                        "html": "verapdf validation",
                        "target": [str(pdf_path)],
                        "failureSummary": "Validation process exceeded 60 second timeout"
                    }]
                }]
            }
        except Exception as e:
            return {
                "url": f"file://{pdf_path}",
                "file_name": pdf_path.name,
                "error": f"verapdf validation failed: {str(e)}",
                "violations": []
            }

    def _parse_json_output(self, json_output: str, pdf_path: Path) -> Dict:
        """Parse verapdf JSON output into our violation format"""
        try:
            data = json.loads(json_output)

            # verapdf JSON structure:
            # {
            #   "report": {
            #     "jobs": [{
            #       "validationReport": {
            #         "isCompliant": bool,
            #         "details": {
            #           "rules": [{
            #             "clause": "...",
            #             "testNumber": int,
            #             "status": "failed"|"passed",
            #             "description": "...",
            #             "object": "...",
            #             "test": "...",
            #             "checks": [...]
            #           }]
            #         }
            #       }
            #     }]
            #   }
            # }

            violations = []
            is_compliant = True
            total_failures = 0

            if "report" in data and "jobs" in data["report"]:
                for job in data["report"]["jobs"]:
                    if "validationReport" in job:
                        val_report = job["validationReport"]
                        is_compliant = val_report.get("isCompliant", False)

                        if "details" in val_report and "rules" in val_report["details"]:
                            rules = val_report["details"]["rules"]

                            for rule in rules:
                                if rule.get("status") == "failed":
                                    total_failures += 1
                                    violation = self._convert_verapdf_rule_to_violation(rule)
                                    violations.append(violation)

            return {
                "url": f"file://{pdf_path}",
                "file_name": pdf_path.name,
                "is_compliant": is_compliant,
                "validator": "verapdf",
                "violations": violations,
                "total_failures": total_failures,
                "passes": 0  # verapdf doesn't report passes, only failures
            }

        except json.JSONDecodeError as e:
            return {
                "url": f"file://{pdf_path}",
                "file_name": pdf_path.name,
                "error": f"Failed to parse verapdf JSON output: {str(e)}",
                "violations": []
            }

    def _parse_xml_output(self, xml_output: str, pdf_path: Path) -> Dict:
        """Parse verapdf XML output into our violation format"""
        try:
            root = ET.fromstring(xml_output)

            violations = []
            is_compliant = True
            total_failures = 0

            # Find validation report
            for job in root.findall(".//job"):
                val_report = job.find("validationReport")
                if val_report is not None:
                    is_compliant = val_report.get("isCompliant", "false").lower() == "true"

                    # Find all failed rules
                    for rule in val_report.findall(".//rule[@status='failed']"):
                        total_failures += 1
                        violation = self._convert_verapdf_rule_to_violation_from_xml(rule)
                        violations.append(violation)

            return {
                "url": f"file://{pdf_path}",
                "file_name": pdf_path.name,
                "is_compliant": is_compliant,
                "validator": "verapdf",
                "violations": violations,
                "total_failures": total_failures,
                "passes": 0
            }

        except ET.ParseError as e:
            return {
                "url": f"file://{pdf_path}",
                "file_name": pdf_path.name,
                "error": f"Failed to parse verapdf XML output: {str(e)}",
                "violations": []
            }

    def _convert_verapdf_rule_to_violation(self, rule: Dict) -> Dict:
        """Convert a verapdf rule to our violation format"""
        clause = rule.get("clause", "")
        description = rule.get("description", "PDF/UA compliance rule failed")
        test = rule.get("test", "")
        object_type = rule.get("object", "")

        # Map verapdf severity to our impact levels
        # verapdf doesn't have severity, so we infer from clause
        impact = "serious"  # Default for PDF/UA violations

        # Build help URL
        help_url = "https://docs.verapdf.org/validation/pdfa-parts-2-and-3/"
        if clause:
            help_url = f"https://docs.verapdf.org/validation/pdfa-part1/#{clause.lower()}"

        # Build comprehensive help text
        help_text = f"""This PDF fails PDF/UA compliance rule: {clause}

RULE: {description}

TEST: {test}

OBJECT: {object_type}

HOW TO FIX:
This is a verapdf-detected PDF/UA violation. The specific fix depends on the rule, but common approaches:

1. Using Adobe Acrobat Pro:
   - Run the full Accessibility Checker
   - Fix issues reported in the same clause
   - Re-validate with verapdf

2. Recreate from source:
   - If you have the source document (Word, InDesign, etc.), fix there
   - Use proper accessibility features in authoring tool
   - Re-export with accessibility enabled

3. For detailed remediation:
   - Review PDF/UA specification for clause {clause}
   - Consult verapdf validation rules documentation
   - Consider professional PDF remediation services for complex documents

WHAT THIS FIXES: Ensures PDF meets PDF/UA (ISO 14289-1) standard for accessibility."""

        return {
            "id": f"verapdf-{clause.lower().replace(' ', '-').replace(':', '-')}",
            "impact": impact,
            "description": f"PDF/UA {clause}: {description}",
            "help": help_text,
            "helpUrl": help_url,
            "tags": ["pdf-ua", "verapdf", clause.lower()],
            "nodes": [{
                "html": f"PDF/UA Rule: {clause}",
                "target": [object_type or "document"],
                "failureSummary": f"Test failed: {test}"
            }]
        }

    def _convert_verapdf_rule_to_violation_from_xml(self, rule_elem: ET.Element) -> Dict:
        """Convert a verapdf XML rule element to our violation format"""
        clause = rule_elem.get("clause", "")
        description = rule_elem.findtext("description", "PDF/UA compliance rule failed")
        test = rule_elem.findtext("test", "")
        object_type = rule_elem.findtext("object", "")

        # Rest is same as JSON version
        impact = "serious"
        help_url = "https://docs.verapdf.org/validation/pdfa-parts-2-and-3/"

        help_text = f"""This PDF fails PDF/UA compliance rule: {clause}

RULE: {description}

TEST: {test}

OBJECT: {object_type}

HOW TO FIX:
This is a verapdf-detected PDF/UA violation. See verapdf documentation for detailed remediation guidance."""

        return {
            "id": f"verapdf-{clause.lower().replace(' ', '-').replace(':', '-')}",
            "impact": impact,
            "description": f"PDF/UA {clause}: {description}",
            "help": help_text,
            "helpUrl": help_url,
            "tags": ["pdf-ua", "verapdf", clause.lower()],
            "nodes": [{
                "html": f"PDF/UA Rule: {clause}",
                "target": [object_type or "document"],
                "failureSummary": f"Test failed: {test}"
            }]
        }
