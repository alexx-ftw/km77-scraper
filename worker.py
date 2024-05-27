"""This file contains the worker code."""

import logging
import subprocess

import aiohttp
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


# Here you can configure the Redis connection.
# The default is to connect to localhost:6379, no password.


host = "nc.vayasuerte.com"
port = 6379
password = None
REDIS_SETTINGS = RedisSettings(
    host=host,
    port=port,
    password=password,
)
print("Worker started.")
command = ["redis-cli", "-h", "localhost", "ping"]
try:
    is_local = "PONG" in subprocess.check_output(command).decode()
except FileNotFoundError:
    is_local = False
print(is_local)
if is_local:
    host = "localhost"
    REDIS_SETTINGS.host = host
    print("Connected to local Redis.")


async def get_source(ctx, url: str) -> str:
    """Get the source of a page. Returns a BeautifulSoup object."""
    try:
        async with aiohttp.ClientSession() as session:
            html = await session.get(url)
            source = await html.text()
    except aiohttp.TooManyRedirects:
        logger.exception(f"Too many redirects for {url}.")
        source = ""
    return source


class w_settings:
    """This class is used to configure the worker."""

    functions = [get_source]
    redis_settings = REDIS_SETTINGS
    max_jobs = 10_000
    queue_read_limit = 10
    keep_result_forever = True
    keep_result = 36_000
