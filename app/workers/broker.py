import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AsyncIO, Retries

from app.core.config import get_settings

_configured = False


def configure_broker() -> RedisBroker:
    """
    Configure Dramatiq once for API process and worker process.

    AsyncIO middleware allows `async def` actors (Dramatiq 1.17+).
    """
    global _configured
    settings = get_settings()
    # namespace = REDIS_PREFIX — shared Redis must isolate this project's keys.
    broker = RedisBroker(url=settings.redis_url, namespace=settings.redis_prefix)
    # Retries is usually present by default; ensure AsyncIO is registered.
    if not any(isinstance(m, AsyncIO) for m in broker.middleware):
        broker.add_middleware(AsyncIO())
    if not any(isinstance(m, Retries) for m in broker.middleware):
        broker.add_middleware(Retries(max_retries=3))
    dramatiq.set_broker(broker)
    _configured = True
    return broker


def ensure_broker() -> None:
    if not _configured:
        configure_broker()
