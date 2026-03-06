from source.services.job_service import JobService


async def process_due_jobs() -> int:
    return await JobService().process_due_jobs()
