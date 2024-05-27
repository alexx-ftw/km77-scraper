"""Scrape the car makes, models, trims and options from the km77 website."""

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
import tqdm  # type: ignore[reportMissingTypeStubs]

import utils
from make import Make

if typing.TYPE_CHECKING:
    from bs4 import ResultSet, Tag


async def main(
    db: aiosqlite.Connection,
) -> None:
    """Scrape the car makes from the km77 website."""
    logger.info("Connected to the database.")

    # Try to load the makes from the database
    makes_list = await utils.load_database(db=db) or []
    logger.info("Loaded %d makes from the database.", len(makes_list))

    # ! Get the Makes
    if not makes_list:
        # Get the source code of the Makes page
        soup = await utils.get_source(f"{utils.BASE_URL}/coches")
        logger.info("Got the source code of the Makes page.")

        # Find all the car brands in the page
        makes_css_class = "js-brand-item"
        makes_names: ResultSet[Tag] = soup.find_all("div", class_=makes_css_class)
        logger.info("Found %d makes.", len(makes_names))

        # Get the makes and their URLs
        # makes_names = makes_names[:1] # For testing purposes # noqa: ERA001
        for html_element in tqdm.tqdm(
            makes_names,
            desc="Generating makes",
            smoothing=0,
        ):
            a_tag = html_element.find("a")
            make_name = a_tag.text if a_tag else html_element.text
            if any(make_obj.name == make_name for make_obj in makes_list):
                continue
            make_url = str(a_tag["href"])  # type: ignore[reportArgumentType]
            next_id = await utils.get_next_id("makes", db=db)
            make_obj = Make(
                ident=next_id,
                name=make_name,
                children_url=utils.BASE_URL
                + make_url
                + "?market[]=available&market[]=discontinued",
            )
            makes_list.append(make_obj)

            # Insert the make into the database
            logger.debug("Inserting %s into the database.", make_obj)
            await utils.insert_into_database(make_obj, "makes", db=db)

        logger.info("Generated %d makes.", len(makes_list))

    # Report the progress
    utils.report_progress(makes_list=makes_list)

    # # ! Get the Models for each Make
    # makes_list = makes_list[:2]  # For testing purposes
    if not all(
        make.models
        for make in tqdm.tqdm(makes_list, desc="Getting models", smoothing=0)
    ):
        await utils.get_children_sources(
            parents_list=makes_list,
            db=db,
        )
        await utils.process_children_sources(
            parents_list=makes_list,
            db=db,
        )

    # Report the progress
    utils.report_progress(makes_list=makes_list)

    # ! Get the Trims for each Model
    all_models = [model for make in makes_list for model in make.models]
    # all_models = all_models[:10]  # For testing purposes
    if not all(
        model.trims
        for model in tqdm.tqdm(all_models, desc="Getting trims", smoothing=0)
    ):
        await utils.get_children_sources(
            parents_list=all_models,
            db=db,
        )
        await utils.process_children_sources(
            parents_list=all_models,
            db=db,
        )

    # Report the progress
    utils.report_progress(makes_list=makes_list)

    # ! Get the Specs and Options for each Trim
    all_trims = [trim for model in all_models for trim in model.trims]
    # all_trims = all_trims[:10]  # For testing purposes # noqa: ERA001
    if not all(
        trim.specs
        for trim in tqdm.tqdm(all_trims, desc="Getting specs and options", smoothing=0)
    ):
        await utils.get_children_sources(
            parents_list=all_trims,
            db=db,
        )
        # await utils.process_children_sources(
        #     parents_list=all_trims,
        #     db=db,
        # )

    # Report the progress
    utils.report_progress(makes_list=makes_list)

    # Close everything
    logger.info("Done.")
    await db.close()


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
