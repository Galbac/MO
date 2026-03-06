from __future__ import annotations

import argparse
import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import Path

from source.config.settings import settings


def create_runtime_backup(destination_path: str | None = None, source_dir: str | None = None) -> Path:
    root = Path(source_dir or 'var')
    backups_dir = Path(settings.maintenance.backups_dir)
    backups_dir.mkdir(parents=True, exist_ok=True)
    target = Path(destination_path) if destination_path else backups_dir / f"runtime-backup-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}.tar.gz"
    with tarfile.open(target, 'w:gz') as archive:
        if root.exists():
            archive.add(root, arcname=root.name)
    return target


def restore_runtime_backup(archive_path: str, target_dir: str | None = None) -> Path:
    archive = Path(archive_path)
    if not archive.exists():
        raise FileNotFoundError(f'Archive not found: {archive}')
    destination = Path(target_dir or '.')
    runtime_root = destination / 'var'
    archive_bytes = archive.read_bytes()
    temp_archive = destination / '.runtime-restore.tmp.tar.gz'
    temp_archive.write_bytes(archive_bytes)
    try:
        if runtime_root.exists():
            shutil.rmtree(runtime_root)
        with tarfile.open(temp_archive, 'r:gz') as bundle:
            try:
                bundle.extractall(destination, filter='data')
            except TypeError:
                bundle.extractall(destination)
    finally:
        temp_archive.unlink(missing_ok=True)
    return runtime_root


def main() -> None:
    parser = argparse.ArgumentParser(description='Backup or restore local runtime state.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    backup = subparsers.add_parser('backup')
    backup.add_argument('--output', dest='output', default=None)
    backup.add_argument('--source', dest='source', default=None)

    restore = subparsers.add_parser('restore')
    restore.add_argument('archive')
    restore.add_argument('--target', dest='target', default='.')

    args = parser.parse_args()
    if args.command == 'backup':
        path = create_runtime_backup(destination_path=args.output, source_dir=args.source)
        print(path)
        return
    restored = restore_runtime_backup(args.archive, target_dir=args.target)
    print(restored)


if __name__ == '__main__':
    main()
