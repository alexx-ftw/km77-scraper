import asyncio
import atexit
import cProfile
import logging
import logging.handlers
import pstats
import sys
import typing
from pathlib import Path
from queue import SimpleQueue

import aiosqlite
import colored  # type: ignore[reportMissingTypeStubs]
import tqdm  # type: ignore[reportMissingTypeStubs]

import utils

if typing.TYPE_CHECKING:
    from bs4 import ResultSet, Tag


async def main(db: aiosqlite.Connection) -> None:
    """Get the source code for the Trims page."""
    logger.info("Connected to the database.")

    # Get all the trims from the database whose children_source column is empty
    trims = await db.execute_fetchall(
        "SELECT * FROM trims WHERE children_source IS NULL",
    )
    logger.info("Got %d trims from the database.", len(trims))

    # Get the source code for the trims
    for trim in tqdm.tqdm(
        trims,
        desc="Getting trims",
        smoothing=0,
    ):
        trim_id = trim[0]
        trim_url = trim[3]

        # Get the source code for the trim
        trim_source = await utils.get_source(trim_url)
        if not trim_source:
            logger.error("No source code found for %s", trim_url)
            continue

        # Update the database with the source code
        await db.execute(
            "UPDATE trims SET children_source = ? WHERE id = ?",
            (str(trim_source), trim_id),
        )
        await db.commit()


if __name__ == "__main__":
    # Set up the logger
    file_handler = logging.FileHandler("km77.log", mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(utils.CustomFormatter("%(message)s"))

    logging_queue = SimpleQueue()  # type: ignore[assignment]
    queue_handler = logging.handlers.QueueHandler(logging_queue)  # type: ignore[arg-type]
    listener = logging.handlers.QueueListener(
        logging_queue,  # type: ignore[arg-type]
        file_handler,
        stream_handler,
        respect_handler_level=True,
    )

    logging.basicConfig(
        level=logging.NOTSET,
        handlers=[queue_handler],
        encoding="utf-8",
    )

    logger = logging.getLogger(__name__)

    logging.getLogger("aiosqlite").setLevel(logging.INFO)

    # Clear the console
    utils.clear_console()

    # Print the welcome message
    logger.info("Scraping the km77 website...")

    if CLEAR_DATABASE := False:
        logger.warning("CLEAR_DATABASE is set to %s", CLEAR_DATABASE)
        # Double check if the user wants to clear the database
        logger.warning("Are you sure you want to clear the database? (y/n)")
        user_input = input()
        if user_input.lower() != "y":
            sys.exit()

        # Clear the database
        with Path.open(utils.DATABASE_FILE_PATH, "w") as f:
            pass

    with cProfile.Profile() as pr:
        listener.start()
        atexit.register(listener.stop)

        db = asyncio.new_event_loop().run_until_complete(
            aiosqlite.connect(utils.DATABASE_FILE_PATH),
        )
    try:
        asyncio.run(main(db=db))
        # stats = pstats.Stats(pr) # noqa: ERA001
        # stats.strip_dirs() # noqa: ERA001
        # stats.sort_stats("cumulative") # noqa: ERA001
        # stats.print_stats(20) # noqa: ERA001
    except KeyboardInterrupt:
        logger.info("User interrupted the program.")
        asyncio.new_event_loop().run_until_complete(db.close())

    sys.exit()
