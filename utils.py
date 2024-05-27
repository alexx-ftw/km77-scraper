"""Utility functions for the tests."""
# pyright: reportMissingModuleSource=false

from __future__ import annotations

import logging
import os
import subprocess  # nosec
import typing
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
import bs4
import colored
from tqdm import tqdm

from make import Make
from model import Model
from trim import Trim

if TYPE_CHECKING:
    from collections.abc import Sequence

    import aiosqlite

# Set up the logger
logger = logging.getLogger(__name__)

DATABASE_FILE_NAME = "km77.db"
DATABASE_FILE_PATH = Path.joinpath(Path(__file__).parent, DATABASE_FILE_NAME)
BASE_URL = "https://www.km77.com"


class CustomFormatter(logging.Formatter):
    """Custom formatter to remove the logger name from the log messages."""

    COLORS: typing.ClassVar = {
        "DEBUG": colored.fg("blue"),
        "INFO": "",
        "WARNING": colored.fg("yellow"),
        "ERROR": colored.fg("red"),
        "CRITICAL": colored.fg("red"),
    }

    def format(self: CustomFormatter, record: logging.LogRecord) -> str:
        """Format the log message."""
        levelname = record.levelname
        color = self.COLORS.get(levelname, "")
        return f"{color}{record.getMessage()}{colored.attr('reset')}"


def clear_console() -> None:
    """Clear the console."""
    if os.name == "nt":
        subprocess.run("cls", shell=True, check=False)  # nosec # noqa: S607, S602
    else:
        subprocess.run("clear", shell=True, check=False)  # nosec # noqa: S607, S602


async def get_next_id(table: str, db: aiosqlite.Connection) -> int:
    """Get the next id for a given table."""
    try:
        cursor = await db.execute(f"SELECT MAX(id) FROM {table}")  # noqa: S608 # nosec
        max_id = await cursor.fetchone()
    except Exception:
        logger.exception("Error getting the next id for %s", table)
        return 1
    return max_id[0] + 1 if max_id[0] else 1  # type: ignore[]


async def insert_into_database(
    obj: Make | Model | Trim,
    table: str,
    db: aiosqlite.Connection,
) -> None:
    """Insert a make, model or trim into the database."""
    try:
        if table == "makes" and isinstance(obj, Make):
            logger.debug("Inserting %s into the database.", obj.name)
            await db.execute(
                "INSERT OR IGNORE INTO makes (name, url) VALUES (?, ?)",
                (obj.name, obj.children_url),
            )
            if obj.children_source is not None:
                await db.execute(
                    "UPDATE makes SET children_source = ? WHERE id = ?",
                    (str(obj.children_source), obj.id),
                )
        elif table == "models" and isinstance(obj, Model):
            logger.debug("Inserting %s into the database.", obj.name)
            await db.execute(
                "INSERT OR IGNORE INTO models (make_id, name, url) VALUES (?, ?, ?)",
                (obj.make.id, obj.name, obj.children_url),
            )
            if obj.children_source is not None:
                await db.execute(
                    "UPDATE models SET children_source = ? WHERE id = ?",
                    (str(obj.children_source), obj.id),
                )
        elif table == "trims" and isinstance(obj, Trim):
            logger.debug("Inserting %s into the database.", obj.name)
            await db.execute(
                "INSERT OR IGNORE INTO trims (name, url, model_id) VALUES (?, ?, ?)",
                (obj.name, obj.children_url, obj.model.id),
            )
            if obj.children_source is not None:
                await db.execute(
                    "UPDATE trims SET children_source = ? WHERE id = ?",
                    (str(obj.children_source), obj.id),
                )
        logger.debug("Committing the changes to the database.")
        await db.commit()

    except Exception as e:
        logger.exception("Error inserting %s into the database:", obj.name)
        if "UNIQUE constraint failed" in str(e):
            logger.warning("The %s %s is already in the database.", table, obj.name)
            # Continue with the next object
            return


async def load_database(
    db: aiosqlite.Connection,
) -> list[Make]:
    """Load the database from the given file."""
    logger.debug("Creating the tables if they don't exist.")
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS makes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            children_source TEXT,
            UNIQUE (name, url)
        )
        """,
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            make_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            children_source TEXT,
            FOREIGN KEY (make_id) REFERENCES makes (id),
            UNIQUE (make_id, name, url)
        )
        """,
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS trims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            children_source TEXT,
            FOREIGN KEY (model_id) REFERENCES models (id),
            UNIQUE (model_id, name, url)
        )
        """,
    )
    await db.commit()

    makes: list[Make] = []
    try:
        logger.debug("Getting the makes from the database.")
        makes_in_db = await db.execute_fetchall("SELECT * FROM makes")
    except Exception:
        logger.exception("Error getting the makes from the database.")
        return makes
    logger.debug("Loading the makes from the database.")
    # Get the total number of trims
    n_trims = await db.execute("SELECT COUNT(*) FROM trims")
    n_trims = await n_trims.fetchone()
    p_bar = tqdm(
        total=n_trims[0],
        desc="Loading the database",
        smoothing=0,
        unit=" trims",
    )
    for make_row in makes_in_db:
        make_obj = Make(
            ident=make_row[0],
            name=make_row[1],
            children_url=make_row[2],
        )
        if make_row[3]:
            make_obj.children_source = bs4.BeautifulSoup(make_row[3], "html.parser")
        for model_row in await db.execute_fetchall(
            "SELECT * FROM models WHERE make_id = ?",
            (make_obj.id,),
        ):
            model_obj = Model(
                ident=model_row[0],
                name=model_row[2],
                children_url=model_row[3],
                make=make_obj,
            )
            if model_row[4]:
                model_obj.children_source = bs4.BeautifulSoup(
                    model_row[4],
                    "html.parser",
                )
            make_obj.add_model(model_obj)
            for trim_row in await db.execute_fetchall(
                "SELECT * FROM trims WHERE model_id = ?",
                (model_obj.id,),
            ):
                trim_obj = Trim(
                    ident=trim_row[0],
                    name=trim_row[2],
                    children_url=trim_row[3],
                    model=model_obj,
                )
                if trim_row[4]:
                    trim_obj.children_source = bs4.BeautifulSoup(
                        trim_row[4],
                        "html.parser",
                    )
                model_obj.add_trim(trim_obj)
                p_bar.update(1)
        makes.append(make_obj)
    p_bar.close()
    return makes


AIOHTTP_MAX_SIZE = 8192 * 3


async def get_source(
    url: str,
) -> bs4.BeautifulSoup:
    """Get the source of a page. Returns a BeautifulSoup object."""
    try:
        async with aiohttp.ClientSession(
            max_field_size=AIOHTTP_MAX_SIZE,
            max_line_size=AIOHTTP_MAX_SIZE,
        ) as session:
            logger.debug("Getting the source for %s", url)
            html = await session.get(url)
            source = await html.text()
    except aiohttp.TooManyRedirects:
        logger.exception("Too many redirects for %s.", url)
        source = ""
    return bs4.BeautifulSoup(source, "html.parser")


async def get_children_sources(
    parents_list: Sequence[Make | Model | Trim],
    db: aiosqlite.Connection,
) -> None:
    """Get the source code for each object in the list and process it."""
    parent = (
        "Make"
        if isinstance(parents_list[0], Make)
        else "Model"
        if isinstance(parents_list[0], Model)
        else "Trim"
    )
    child = (
        "Model"
        if isinstance(parents_list[0], Make)
        else "Trim"
        if isinstance(parents_list[0], Model)
        else "SpecOp"
    )
    bold = "\033[1m"
    reset = "\033[0m"
    h2 = f"{bold}Getting the {child}s for each {parent}.{reset}"
    logger.info(h2)
    for obj in tqdm(parents_list, desc=f"Getting {child}s sources", smoothing=0):
        try:
            if obj.children_source is not None:
                logger.debug("Children Source already found for %s", obj.name)
                continue
            logger.debug("Getting children source for %s", obj.name)
            obj.children_source = await get_source(obj.children_url)
            (
                obj.children_source.append(
                    await get_source(f"{obj.children_url}/equipamiento"),
                )
                if isinstance(obj, Trim)
                else None
            )
            if isinstance(obj, Make):
                await db.execute(
                    "UPDATE makes SET children_source = ? WHERE id = ?",
                    (str(obj.children_source), obj.id),
                )
            elif isinstance(obj, Model):
                await db.execute(
                    "UPDATE models SET children_source = ? WHERE id = ?",
                    (str(obj.children_source), obj.id),
                )
            else:
                await db.execute(
                    "UPDATE trims SET children_source = ? WHERE id = ?",
                    (str(obj.children_source), obj.id),
                )
            await db.commit()
        except Exception:
            logger.exception(
                "Error getting children source for %s\nURL: %s:",
                obj.name,
                obj.children_url,
            )


async def process_children_sources(
    parents_list: Sequence[Make | Model | Trim],
    db: aiosqlite.Connection,
) -> None:
    """Process the source code for each object in the list."""
    for parent in tqdm(
        parents_list,
        desc=f"Processing {parents_list[0].__class__.__name__}s",
        smoothing=0,
    ):
        try:
            logger.debug("Processing %s", parent.name)
            if isinstance(parent, Make):
                logger.debug("Getting models for %s", parent.name)
                await parent.get_models(db)
            elif isinstance(parent, Model):
                logger.debug("Getting trims for %s", parent.name)
                await parent.get_trims(db)
            else:
                logger.debug("Getting options for %s", parent.name)
                await parent.get_specops(db)
        except Exception:
            logger.exception("Error getting %s", parent.name)


def report_progress(makes_list: list[Make]) -> None:
    """Log the progress of the database."""
    text = "Database has:"
    text += f"\n\t{len(makes_list)} makes" if any(makes_list) else ""
    text += (
        f"\n\t{len([model for make in makes_list for model in make.models])} models"
        if any(model for make in makes_list for model in make.models)
        else ""
    )
    text += (
        f"\n\t{len([trim for make in makes_list for model in make.models for trim in model.trims])} trims"
        if any(
            trim for make in makes_list for model in make.models for trim in model.trims
        )
        else ""
    )
    text += (
        f"\n\t{len([option for make in makes_list for model in make.models for trim in model.trims for option in trim.options])} options"
        if any(
            option
            for make in makes_list
            for model in make.models
            for trim in model.trims
            for option in trim.options
        )
        else ""
    )
    text += "\n"
    logger.info(text)
