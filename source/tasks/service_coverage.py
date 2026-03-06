from __future__ import annotations

import argparse
import json
import re
import sys
import trace as trace_module
from pathlib import Path
from typing import Iterable

import pytest

DEFAULT_THRESHOLD = 80.0
SUMMARY_RE = re.compile(r"^\s*(?P<lines>\d+)\s+(?P<cov>\d+)%\s+\S+\s+\((?P<path>.+)\)$")


def parse_trace_summary(output: str, service_root: str = "source/services") -> dict[str, object]:
    entries: list[dict[str, object]] = []
    total_lines = 0
    covered_lines = 0
    root_fragment = service_root.replace('\\', '/')
    for raw_line in output.splitlines():
        match = SUMMARY_RE.match(raw_line.strip())
        if not match:
            continue
        path_value = match.group('path').replace('\\', '/')
        if root_fragment not in path_value:
            continue
        lines = int(match.group('lines'))
        coverage_pct = int(match.group('cov'))
        covered = round(lines * coverage_pct / 100)
        total_lines += lines
        covered_lines += covered
        entries.append({
            'path': path_value,
            'lines': lines,
            'coverage_pct': coverage_pct,
            'covered_lines_estimate': covered,
        })
    overall_pct = round((covered_lines / total_lines * 100) if total_lines else 0.0, 2)
    return {
        'service_root': service_root,
        'total_lines': total_lines,
        'covered_lines_estimate': covered_lines,
        'coverage_pct': overall_pct,
        'files': sorted(entries, key=lambda item: str(item['path'])),
    }


def build_service_report(pytest_args: Iterable[str], service_root: str = 'source/services') -> dict[str, object]:
    root = Path(service_root).resolve()
    tracer = trace_module.Trace(count=True, trace=False)
    exit_code = tracer.runfunc(pytest.main, list(pytest_args))
    if exit_code != 0:
        raise SystemExit(int(exit_code))

    results = tracer.results()
    counts = results.counts
    files: list[dict[str, object]] = []
    total_lines = 0
    covered_lines = 0

    for path in sorted(root.glob('*.py')):
        executable = set(trace_module._find_executable_linenos(str(path)).keys())
        if not executable:
            continue
        executed = {lineno for (filename, lineno), count in counts.items() if Path(filename).resolve() == path and count > 0}
        covered = len(executable & executed)
        lines = len(executable)
        pct = round((covered / lines * 100) if lines else 0.0, 2)
        total_lines += lines
        covered_lines += covered
        files.append({
            'path': str(path),
            'lines': lines,
            'covered_lines': covered,
            'coverage_pct': pct,
        })

    return {
        'service_root': str(root),
        'total_lines': total_lines,
        'covered_lines': covered_lines,
        'coverage_pct': round((covered_lines / total_lines * 100) if total_lines else 0.0, 2),
        'files': files,
    }


def _report_path(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / 'service_coverage.json'


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate service-layer coverage report using stdlib trace.')
    parser.add_argument('--threshold', type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument('--output-dir', default='var/coverage')
    args, pytest_args = parser.parse_known_args()
    if not pytest_args:
        pytest_args = ['-q']

    report = build_service_report(pytest_args)
    report['threshold_pct'] = float(args.threshold)
    report['passed'] = report['coverage_pct'] >= float(args.threshold)

    output_dir = Path(args.output_dir)
    report_path = _report_path(output_dir)
    report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))

    print(f"Service coverage: {report['coverage_pct']}% ({report['covered_lines']}/{report['total_lines']} lines)")
    print(f"Report: {report_path}")
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
