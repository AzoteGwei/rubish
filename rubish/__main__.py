from .tg import app
from .db import conn
import uvloop
import asyncio
from loguru import logger
import sys

def setup_logging():
    log_format = "[{level}][{time:HH:mm:ss}][{module}] {message}"
    logger.remove()
    
    logger.add(sys.stderr, format=log_format, colorize=True)

    logger.add("app.log", rotation="50 MB", format=log_format, encoding="utf-8")



if __name__ == "__main__":
    # uvloop.install()
    setup_logging()
    logger.info("Server started.")
    try:
        app.run()
    finally:
        logger.info("Stop stoping.")
        conn.close()