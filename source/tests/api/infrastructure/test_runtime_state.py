from source.services import CacheService, JobService, RuntimeStateStore


def test_runtime_state_store_uses_local_backend_without_redis() -> None:
    store = RuntimeStateStore()
    assert store.backend_name() == 'local'

    store.write_namespace('smoke', {'ok': True})
    assert store.read_namespace('smoke', {}) == {'ok': True}


def test_cache_and_jobs_share_runtime_store_fallback() -> None:
    cache = CacheService()
    jobs = JobService()

    assert cache.backend_name() == 'local'
    assert jobs.backend_name() == 'local'
