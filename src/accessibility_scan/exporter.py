"""Export scan results to multiple formats"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader


class ResultExporter:
    """Export violations to CSV, JSON, Markdown"""

    SEVERITY_ORDER = {"critical": 4, "serious": 3, "moderate": 2, "minor": 1}

    def __init__(self, results: List[Dict], output_dir: Path, min_severity: str = None):
        self.results = results
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.min_severity = min_severity.lower() if min_severity else None

    def _should_include_violation(self, violation: Dict) -> bool:
        """Check if violation meets minimum severity threshold"""
        if not self.min_severity:
            return True

        impact = violation.get('impact', 'moderate').lower()
        min_level = self.SEVERITY_ORDER.get(self.min_severity, 1)
        violation_level = self.SEVERITY_ORDER.get(impact, 1)

        return violation_level >= min_level

    def export_all(self):
        """Export to all formats"""
        self.export_csv()
        self.export_json()
        self.export_markdown()

    def export_csv(self) -> Path:
        """Export violations as CSV for Jira import"""
        csv_path = self.output_dir / "violations.csv"

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'Summary',
                'Description',
                'Page URL',
                'Severity',
                'WCAG Criterion',
                'Element',
                'Help URL'
            ])

            # Violations
            for page_result in self.results:
                url = page_result.get('url', '')

                for violation in page_result.get('violations', []):
                    if not self._should_include_violation(violation):
                        continue

                    for node in violation.get('nodes', []):
                        writer.writerow([
                            f"[A11y] {violation['id']}: {violation['description'][:50]}...",
                            violation['description'],
                            url,
                            violation['impact'].upper() if violation.get('impact') else 'MODERATE',
                            ', '.join(violation.get('tags', [])),
                            node.get('html', '')[:100],
                            violation.get('helpUrl', '')
                        ])

        return csv_path

    def export_json(self) -> Path:
        """Export full results as JSON"""
        json_path = self.output_dir / "violations.json"

        # Filter results if min_severity set
        filtered_results = []
        for page_result in self.results:
            filtered_violations = [
                v for v in page_result.get('violations', [])
                if self._should_include_violation(v)
            ]
            filtered_results.append({
                **page_result,
                'violations': filtered_violations
            })

        export_data = {
            "scan_date": datetime.now().isoformat(),
            "total_pages": len(filtered_results),
            "total_violations": sum(
                len(r.get('violations', []))
                for r in filtered_results
            ),
            "pages": filtered_results
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)

        return json_path

    def export_markdown(self) -> Path:
        """Export violations as Markdown report"""
        md_path = self.output_dir / "violations.md"

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("# Accessibility Scan Results\n\n")
            f.write(f"**Scan Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            total_violations = sum(
                len(r.get('violations', []))
                for r in self.results
            )
            f.write(f"**Total Pages:** {len(self.results)}\n")
            f.write(f"**Total Violations:** {total_violations}\n\n")

            f.write("---\n\n")

            for page_result in self.results:
                url = page_result.get('url', '')
                violations = [
                    v for v in page_result.get('violations', [])
                    if self._should_include_violation(v)
                ]

                if not violations:
                    continue

                f.write(f"## {url}\n\n")
                f.write(f"**Violations:** {len(violations)}\n\n")

                for violation in violations:
                    impact = violation.get('impact', 'moderate').upper()
                    f.write(f"### [{impact}] {violation['id']}\n\n")
                    f.write(f"**Description:** {violation['description']}\n\n")
                    f.write(f"**WCAG:** {', '.join(violation.get('tags', []))}\n\n")
                    f.write(f"**Help:** {violation.get('helpUrl', 'N/A')}\n\n")

                    f.write(f"**Affected Elements:** {len(violation.get('nodes', []))}\n\n")

                    for i, node in enumerate(violation.get('nodes', [])[:3], 1):
                        f.write(f"{i}. `{node.get('html', '')[:80]}...`\n")

                    if len(violation.get('nodes', [])) > 3:
                        f.write(f"   _...and {len(violation['nodes']) - 3} more_\n")

                    f.write("\n---\n\n")

        return md_path

    def get_summary(self) -> Dict:
        """Get summary statistics"""
        total_violations = 0
        by_severity = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}

        for page_result in self.results:
            for violation in page_result.get('violations', []):
                if not self._should_include_violation(violation):
                    continue

                total_violations += len(violation.get('nodes', []))
                impact = violation.get('impact', 'moderate').lower()
                by_severity[impact] = by_severity.get(impact, 0) + len(violation.get('nodes', []))

        return {
            "total_pages": len(self.results),
            "total_violations": total_violations,
            "by_severity": by_severity
        }
