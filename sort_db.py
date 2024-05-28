"""Filter the database according to various parameters."""

import asyncio
import atexit
import logging
import logging.handlers
from queue import SimpleQueue

import aiosqlite
import bs4
from tqdm import tqdm

import utils


async def main(
    db: aiosqlite.Connection,
) -> None:
    """Filter the database according to various parameters."""
    logger.info("Connected to the database.")
    trims_list = await db.execute_fetchall(
        "SELECT * FROM trims WHERE specs_source IS NULL AND options_source IS NULL",
    )
    trims_list = list(trims_list)
    logger.info("Trims size: %s", len(trims_list))

    # Get the specs and options for each trim
    logger.info("Getting the specs and options for each trim...")
    content_div_class = "mainbar"
    for trim in tqdm(trims_list):
        if trim[5] or trim[6]:
            continue
        raw_source = bs4.BeautifulSoup(trim[4], "html.parser")
        specs_source = raw_source.find("div", class_=content_div_class)
        options_source = (
            specs_source.find_next("div", class_=content_div_class)
            if specs_source
            else None
        )

        # Write the processed sources to the database if they are Null in the database
        await db.execute(
            "UPDATE trims SET specs_source = ?, options_source = ? WHERE id = ?",
            (str(specs_source), str(options_source), trim[0]),
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

    # Clear the console
    utils.clear_console()
    db = asyncio.new_event_loop().run_until_complete(
        aiosqlite.connect(utils.DATABASE_FILE_PATH),
    )
    try:
        listener.start()
        atexit.register(listener.stop)
        asyncio.run(main(db))
    except (RuntimeError, KeyboardInterrupt):
        print("\nExiting...")
    finally:
        asyncio.run(db.close())
exit()
