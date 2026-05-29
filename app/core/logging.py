import logging
import sys
import warnings

import structlog

from app.core.config import settings
from app.core.sqlalchemy_pool_cancel_filter import SQLAlchemyPoolCancelFilter


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.LOG_LEVEL,
    )

    # Spurious sklearn thread-race warning (its config propagation races on the
    # global warnings.filters under concurrent inference). The anomaly adapter
    # serializes our sklearn calls; this filter is insurance so residual edge
    # cases never spam the deployed logs.
    warnings.filterwarnings(
        "ignore",
        message=r".*should be used with.*sklearn\.utils\.parallel\.Parallel.*",
        category=UserWarning,
    )

    # Drop the noisy "Exception terminating connection" records that
    # SQLAlchemy emits when asyncpg's terminate() is cancelled by uvicorn's
    # shutdown — see SQLAlchemyPoolCancelFilter docstring for the race.
    _shutdown_filter = SQLAlchemyPoolCancelFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(_shutdown_filter)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
