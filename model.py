"""Model class for representing a car model object."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import trim
import utils

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import aiosqlite
    from bs4 import BeautifulSoup, Tag

    import make


class Model:
    """Model class for representing a car model object."""

    def __init__(
        self: Model,
        ident: int,
        name: str,
        children_url: str,
        make: make.Make,
    ) -> None:
        """Initialize the Model object."""
        self.id = ident
        self.name = name
        self.children_url = children_url
        self.children_source: Tag | None = None
        self.make = make

        self.year: int
        self.make: make.Make

        self.trims: list[trim.Trim] = []

    def add_trim(self: Model, trim: trim.Trim) -> None:
        """Add a trim to the model's list of trims."""
        self.trims.append(trim)

    async def get_trims(
        self: Model,
        db: aiosqlite.Connection,
    ) -> None:
        """Get the trims for a given model."""
        # Get the trim's:
        # - Name
        # - Production dates
        # - Href
        try:
            # Check if the model has no trims
            if "informacion" in self.children_url:
                logger.debug("Skipping %s as it has no trims", self.name)
                return
            # Get the trims
            if not self.children_source:
                logger.error("No source found for %s", self.name)
                return
            trims_html = self.children_source.find_all("td", class_="vehicle-name")
            logger.debug("Found %s trims for %s", str(len(trims_html)), self.name)
            if not trims_html:
                logger.error("No trims found for %s %s", self.make.name, self.name)
                return
            for trim_html in trims_html:
                trim_name = trim_html.find("a").text.split("\n")[1].strip()
                # Check if there is already a trim with the same name
                if any(trim_obj.name == trim_name for trim_obj in self.trims):
                    # Skip the trim if it already exists
                    continue

                trim_production = (
                    trim_html.find("span").text.split("\n")[0].strip() + ")"
                )
                trim_href = trim_html.find("a")["href"]
                next_id = await utils.get_next_id("trims", db=db)
                new_trim_obj = trim.Trim(
                    ident=next_id,
                    name=trim_name,
                    children_url=utils.BASE_URL + trim_href,
                    model=self,
                )
                # Insert the trim into the database
                await utils.insert_into_database(new_trim_obj, "trims", db=db)
                # Add the trim to the model
                self.add_trim(trim=new_trim_obj)
        except Exception:
            logger.exception("Error getting trims for %s", self.name)
            return
