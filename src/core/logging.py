"""Central logging configuration using structlog."""

import logging

import structlog


def setup_logging(debug: bool = False, json_output: bool = False) -> None:
    """Configure structlog for the application.

    Args:
        debug: Enable DEBUG level logging
        json_output: Use JSON output format (for production/machine parsing)
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    level = logging.DEBUG if debug else logging.INFO

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Suppress noisy third-party loggers
    for name in (
        "httpx",
        "chromadb",
        "sentence_transformers",
        "transformers",
        "huggingface_hub",
        "transformers.modeling_utils",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)
