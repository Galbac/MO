from pathlib import Path


def test_makefile_contains_core_tasks() -> None:
    content = Path('Makefile').read_text()
    for target in ['dev:', 'test:', 'lint:', 'format:', 'typecheck:', 'migrate-up:', 'compose-up:']:
        assert target in content
