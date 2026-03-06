import tarfile
from pathlib import Path

from source.tasks.runtime_backup import create_runtime_backup, restore_runtime_backup


def test_runtime_backup_and_restore_roundtrip(tmp_path) -> None:
    source_dir = tmp_path / 'var'
    media_dir = source_dir / 'media'
    media_dir.mkdir(parents=True)
    (source_dir / 'cache_store.json').write_text('{"ok": true}')
    (media_dir / 'sample.txt').write_text('hello')

    archive_path = tmp_path / 'runtime-backup.tar.gz'
    backup = create_runtime_backup(destination_path=str(archive_path), source_dir=str(source_dir))

    assert backup.exists()
    with tarfile.open(backup, 'r:gz') as bundle:
        assert 'var/cache_store.json' in bundle.getnames()
        assert 'var/media/sample.txt' in bundle.getnames()

    restore_target = tmp_path / 'restore-target'
    restore_target.mkdir()
    restored_root = restore_runtime_backup(str(backup), target_dir=str(restore_target))

    assert restored_root.exists()
    assert (restored_root / 'cache_store.json').read_text() == '{"ok": true}'
    assert (restored_root / 'media' / 'sample.txt').read_text() == 'hello'
