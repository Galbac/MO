from pathlib import Path

from source.tasks import service_coverage
from source.tasks.service_coverage import build_service_report, parse_trace_summary


SAMPLE_TRACE_OUTPUT = """
  120    90%   source.services.auth_user_service   (/workspace/source/services/auth_user_service.py)
   80    75%   source.services.user_engagement_service   (/workspace/source/services/user_engagement_service.py)
  999    12%   unrelated.module   (/workspace/.venv/lib/python/site-packages/unrelated.py)
"""


def test_parse_trace_summary_aggregates_only_service_modules() -> None:
    report = parse_trace_summary(SAMPLE_TRACE_OUTPUT)

    assert report['total_lines'] == 200
    assert report['covered_lines_estimate'] == 168
    assert report['coverage_pct'] == 84.0
    assert len(report['files']) == 2
    assert all('/source/services/' in item['path'] for item in report['files'])


def test_makefile_exposes_coverage_service_target() -> None:
    content = Path('Makefile').read_text()
    assert 'coverage-service:' in content


def test_build_service_report_uses_trace_results(monkeypatch, tmp_path) -> None:
    service_file = tmp_path / 'service_a.py'
    service_file.write_text('def alpha():\n    return 1\n\n\ndef beta():\n    return 2\n')

    class FakeResults:
        counts = {(str(service_file), 1): 1, (str(service_file), 2): 1}

    class FakeTrace:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def runfunc(self, func, args):
            assert func is service_coverage.pytest.main
            assert args == ['-q']
            return 0

        def results(self):
            return FakeResults()

    monkeypatch.setattr(service_coverage.trace_module, 'Trace', FakeTrace)
    monkeypatch.setattr(service_coverage.trace_module, '_find_executable_linenos', lambda filename: {1: None, 2: None, 5: None, 6: None})

    report = build_service_report(['-q'], service_root=str(tmp_path))

    assert report['total_lines'] == 4
    assert report['covered_lines'] == 2
    assert report['coverage_pct'] == 50.0
    assert report['files'][0]['path'] == str(service_file)
