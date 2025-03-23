"""Run the aiohttp application server."""
import logging
import logging.config
from app.main import run_app

# 配置日志系统
logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': 'app.log',
            'mode': 'a',
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True
        },
        'app': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False
        },
    }
})

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting multiprocessing application")
    run_app()
    logger.info("Application shutdown complete")
