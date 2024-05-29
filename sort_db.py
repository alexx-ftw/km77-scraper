"""Filter the database according to various parameters."""

import asyncio
import atexit
import logging
import logging.handlers
from queue import SimpleQueue

import aiosqlite
import bs4
from bs4 import NavigableString, ResultSet, Tag
from tqdm import tqdm

import utils


def sanitize_text(text: str) -> str:
    """Sanitize the text."""
    return (
        text.replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace("(", "_")
        .replace(")", "_")
        .replace(".", "_")
        .replace("%", "porc")
        .replace(",", "_")
    )


async def prompt_new_column(
    db: aiosqlite.Connection,
    column_name: str,
    answer: str | None = None,
) -> None:
    """Prompt the user to add a new column to the trims table."""
    if not answer:
        add_column = input(
            f"Add column '{column_name}' to the trims table? (Y/n): ",
        )
    else:
        add_column = answer
    if add_column.lower() not in ("y", "yes", "", "\n"):
        return

    await db.execute(
        f"ALTER TABLE trims ADD COLUMN {column_name} TEXT",
    )
    await db.commit()


async def main(
    db: aiosqlite.Connection,
) -> None:
    """Filter the database according to various parameters."""
    logger.info("Connected to the database.")

    # Get trims table number of rows
    trims_count = next(iter(await db.execute_fetchall("SELECT COUNT(*) FROM trims")))
    trims_count = trims_count[0]
    logger.info("Trims count: %s", trims_count)

    # Get the specs and options for each trim
    logger.info("Getting the specs and options for each trim...")
    content_div_class = "mainbar"
    for trim_id in tqdm(range(trims_count)):
        trim = next(
            iter(
                await db.execute_fetchall(
                    "SELECT * FROM trims WHERE id = ?",
                    (trim_id + 1,),
                ),
            ),
        )
        raw_source = bs4.BeautifulSoup(trim[4], "html.parser")
        source_1 = raw_source.find("div", class_=content_div_class)
        if source_1:
            source_2 = source_1.find_next("div", class_=content_div_class)
        else:
            source_2 = None

        if source_1 and source_2:
            # Join the two sources
            specops_source = source_1
            # specops_source.append(source_2)
        elif source_1:
            specops_source = source_1
        elif source_2:
            specops_source = source_2
        else:
            specops_source = None

        if (
            (not source_1 and not source_2)
            or not specops_source
            or isinstance(
                specops_source,
                NavigableString,
            )
        ):
            reason = (
                "source_1 and source_2 are None"
                if not source_1 and not source_2
                else "specops_source is a NavigableString"
                if specops_source
                else "specops_source is None"
            )
            logger.info("No source found for trim %s. Reason: %s", trim[0], reason)
            continue

        # Find all the tables with class "table" in the source
        tables: ResultSet[Tag] = specops_source.find_all("table", class_="table")
        if not tables:
            logger.info("No tables found for trim %s.", trim[0])
            continue

        # Get the specs and options from the tables
        for table in tables:
            # Find "tr" elements in the table
            trs: ResultSet[Tag] = table.find_all("tr")
            # Get "th" and "td" elements from the "tr" elements
            for tr in trs:
                th = tr.find("th")
                td = tr.find("td")

                # ! SKIP THIS "tr"
                skip_trs = [
                    "Sólo en paquete",
                    # "€",
                ]
                if td and any(
                    skip_tr in td.get_text(strip=True) for skip_tr in skip_trs
                ):
                    reason = f"td contains {skip_trs}"
                    logger.info(
                        "Skipping tr %s for trim %s. Reason: %s",
                        sanitize_text(tr.get_text(strip=True)),
                        trim[0],
                        reason,
                    )
                    continue
                column_exists = await db.execute_fetchall(
                    "PRAGMA table_info(trims)",
                )
                column_exists = list(column_exists)
                if th and isinstance(th, Tag) and td and isinstance(td, Tag):
                    # Remove any inside "span" elements from the "th"
                    spans: ResultSet[Tag] = th.find_all("span")
                    for span in spans:
                        span.decompose()
                    # Get the text from the "th" and "td" elements
                    th_text = sanitize_text(th.get_text(strip=True))
                    td_text = td.get_text(strip=True)
                    known_columns = {
                        "Start_and_stop": "Automatismo_de_parada_y_arranque_del_motor",
                    }
                    for key, value in known_columns.items():
                        if value in th_text:
                            th_text = key
                            break

                    # Check if there exists a column with the name of the "th" text in the trims table
                    if all(column[1] != th_text for column in column_exists):
                        logger.info(
                            "Column %s not found in trims table. Prompting...",
                            th_text,
                        )
                        await prompt_new_column(db, th_text, "y")

                    # Write the specs and options to the database
                    await db.execute(
                        f"UPDATE trims SET {th_text} = ? WHERE id = ?",  # nosec # noqa: S608
                        (td_text, trim[0]),
                    )
                    await db.commit()
                # If the "th" element has "scope" attribute set to "row"
                elif th and isinstance(th, Tag) and th.get("scope") == "row":
                    title = sanitize_text(th.get_text(strip=True))
                    # All the following "tr" elements that dont have a "th" are subtitles
                    # The first "td" element inside the "tr" element is the key
                    # The second "td" element inside the "tr" element is the value
                    # The key will be appended to the title with a space in between and then sanitized
                    while True:
                        tr_s = tr.find_next("tr")
                        if not tr_s:
                            break
                        # If "tr" has "th" element, break the loop
                        if tr_s.find("th"):
                            break
                        td_1 = tr_s.find("td")
                        td_2 = (
                            td_1.find_next("td")
                            if td_1 and isinstance(td_1, Tag)
                            else None
                        )
                        if (
                            td_1
                            and td_2
                            and isinstance(td_1, Tag)
                            and isinstance(td_2, Tag)
                        ):
                            key = sanitize_text(td_1.get_text(strip=True))
                            value = td_2.get_text(strip=True)
                            col_name = sanitize_text(f"{title} {key}")
                            if col_name not in [column[1] for column in column_exists]:
                                await prompt_new_column(db, col_name, "y")
                            await db.execute(
                                f"UPDATE trims SET {col_name} = ? WHERE id = ?",  # nosec # noqa: S608
                                (value, trim[0]),
                            )
                            await db.commit()
                        else:
                            logger.info("No key or value found for trim %s.", trim[0])
                            break
                        tr = tr_s
                elif (
                    td
                    and isinstance(td, Tag)
                    and any(
                        sanitize_text(td.get_text(strip=True)) in col[1]
                        for col in column_exists
                    )
                ):
                    # If there is a column that includes the text of the "td" element
                    # Means that it is already written to the database
                    pass
                else:
                    logger.info("No th or td found for trim %s.", trim[0])
                    logger.info("th: %s", th.get_text(strip=True)) if th else None
                    logger.info("td: %s", td.get_text(strip=True)) if td else None

        # Commit the changes to the database
        await db.commit()
    logger.info("Finished updating the database.")


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
    db = asyncio.new_event_loop().run_until_complete(
        aiosqlite.connect(utils.DATABASE_FILE_PATH),
    )
    try:
        listener.start()
        atexit.register(listener.stop)
        asyncio.run(main(db))
    except (RuntimeError, KeyboardInterrupt):
        listener.stop()
        logger.info("Exiting...")
    finally:
        asyncio.run(db.close())
exit()
