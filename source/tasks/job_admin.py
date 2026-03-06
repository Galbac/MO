from __future__ import annotations

import argparse
import asyncio
import json

from source.services import JobService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Manage runtime background jobs')
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser('list', help='List current jobs')

    retry = sub.add_parser('retry', help='Retry a failed job by id')
    retry.add_argument('job_id', type=int)

    prune = sub.add_parser('prune', help='Prune jobs by status')
    prune.add_argument('--status', action='append', dest='statuses', default=[])

    return parser


async def _run_async(args: argparse.Namespace) -> int:
    service = JobService()
    if args.command == 'list':
        print(json.dumps(service.list_jobs(), ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == 'retry':
        record = await service.retry_failed_job(args.job_id)
        print(json.dumps(record, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == 'prune':
        removed = service.prune_jobs(statuses=args.statuses or None)
        print(json.dumps({'removed': removed}, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    raise ValueError(f'Unsupported command: {args.command}')


def main() -> None:
    args = _parser().parse_args()
    raise SystemExit(asyncio.run(_run_async(args)))


if __name__ == '__main__':
    main()
