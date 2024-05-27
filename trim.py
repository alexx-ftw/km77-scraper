"""Trim class for car trims."""
# pyright: reportUnknownMemberType=false, reportAttributeAccessIssue=false

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import aiosqlite
    from bs4 import ResultSet, Tag

    import model

logger = logging.getLogger(__name__)


class Trim:
    """Trim class for car trims."""

    def __init__(
        self: Trim,
        ident: int,
        name: str,
        children_url: str,
        model: model.Model,
    ) -> None:
        """Initialize the Trim object."""
        self.id = ident
        self.name = name
        self.children_url = children_url
        self.children_source: Tag | None = None
        self.model = model

        self.model: model.Model
        self.production: dict[str, int]
        self.specs: list[dict[str, Any]] = []
        self.options: list[dict[str, Any]] = []

    def __str__(self: Trim) -> str:
        """Return the Trim's name."""
        return self.name

    async def get_specops(
        self: Trim,
        db: aiosqlite.Connection,
    ) -> None:
        """Get the data for a given trim."""
        if self.specs and self.options:
            return
        if not self.children_source:
            logger.error("No source found for %s", self.name)
            return
        # Get the specs and options.
        # The specs tables are inside a "div" with the id "measurements-1"
        # The options tables are inside a "div" with the id "features-2"
        specs_div = self.children_source.find(
            "div",
            {"id": "measurements-1"},
            recursive=True,
        )
        options_div = self.children_source.find(
            "div",
            {"id": "features-2"},
            recursive=True,
        )

        for div in [specs_div, options_div]:
            if div is None:
                continue

            # Get the tables
            tables: ResultSet[Tag] = div.find_all("table") if div else []  # type: ignore[]

            # Remove any empty tables
            tables = [table for table in tables if table.find("tr")]  # type: ignore[]

            # Get the data from the tables
            for table in tables:
                # Check if the table has a caption
                caption = table.find("caption", class_="caption-top")
                if caption:
                    caption = (
                        caption.text.split("\n")[1].strip()
                        if div != specs_div
                        else caption.text.strip()
                    )
                else:
                    # If there is no caption, skip the table
                    continue

                # Get the data
                rows = table.find_all("tr")
                data = {}
                last_pseudo_key = None
                num_tds = 3
                for row in rows:
                    tds = row.find_all("td")
                    if len(tds) == num_tds:
                        # This is a special case where the row has 3 "td" elements
                        # The first "td" is the package name, the second "td" is the price, and the third "td" is the checkbox
                        package_name = tds[0].text.strip().split("\n")[0]
                        price = tds[1].text.strip()

                        if modal := tds[0].find("div", class_="modal-body"):
                            # Extract the addons from the modal
                            addons = [li.text for li in modal.find_all("li")]
                        else:
                            addons = []

                        data[package_name] = {
                            "price": price,
                            "addons": addons,
                        }
                    elif row.find("td") is None:
                        last_pseudo_key = row.find("th").text
                        if "\n" in last_pseudo_key:
                            last_pseudo_key = last_pseudo_key.split("\n")[1].strip()
                        data[last_pseudo_key] = {}
                    elif row.find("th") is None:
                        # This is a special case where the row does not have a "th" and a "td"
                        # but only 2 "td" elements
                        # The first "td" is the key and the second "td" is the value
                        key = row.find_all("td")[0].text
                        if "\n" in key:
                            key = key.split("\n")[1].strip()
                        value = row.find_all("td")[1].text
                        if "\n" in value:
                            value = value.split("\n")[1].strip()
                        data[last_pseudo_key][key] = value

                    else:
                        key = row.find("th").text.split("\n")[1].strip()
                        value = (
                            (
                                row.find("td", class_="text-right")
                                .text.split("\n")[1]
                                .strip()
                            )
                            if "Distintivo ambiental" not in key
                            else row.find("td").find("img")["alt"]
                        )

                        data[key] = value

                if div == specs_div:
                    self.specs.append({"caption": caption, "data": data})
                else:
                    self.options.append({"caption": caption, "data": data})
