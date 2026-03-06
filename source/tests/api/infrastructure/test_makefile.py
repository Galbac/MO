from pathlib import Path


def test_makefile_contains_core_tasks() -> None:
    content = Path('Makefile').read_text()
    for target in ['dev:', 'test:', 'lint:', 'format:', 'typecheck:', 'migrate-up:', 'compose-up:']:
        assert target in content


def test_makefile_has_worker_and_contract_targets() -> None:
    content = __import__("pathlib").Path("Makefile").read_text()
    assert "worker:" in content
    assert "test-contract:" in content
    assert "test-load:" in content
