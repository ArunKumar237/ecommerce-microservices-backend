import os

LOG_DIR = os.getenv("LOG_DIR", None)
if not LOG_DIR:
    if os.path.isdir("/app"):
        LOG_DIR = "/app/logs"
    else:
        LOG_DIR = os.path.join(os.getcwd(), "logs")

os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "ecommerce.log")
LOG_ERROR_FILE = os.path.join(LOG_DIR, "ecommerce.error.log")

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s %(levelname)s [%(name)s] %(message)s"},
        "simple": {"format": "%(levelname)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "verbose",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "verbose",
            "filename": LOG_FILE,
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf8",
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "verbose",
            "filename": LOG_ERROR_FILE,
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf8",
        },
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console", "file", "error_file"],
    },
    "loggers": {
        "django": {"level": "INFO", "handlers": ["console", "file"], "propagate": True},
        "django.request": {"level": "ERROR", "handlers": ["console", "error_file"], "propagate": False},
        "payments": {"level": "DEBUG", "handlers": ["console", "file"], "propagate": False},
        "orders": {"level": "DEBUG", "handlers": ["console", "file"], "propagate": False},
        "products": {"level": "DEBUG", "handlers": ["console", "file"], "propagate": False},
        "users": {"level": "DEBUG", "handlers": ["console", "file"], "propagate": False},
        "celery": {"level": "INFO", "handlers": ["console", "file"], "propagate": False},
    },
}
