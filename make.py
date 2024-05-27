"""Make class."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import model
import utils

if TYPE_CHECKING:
    import aiosqlite
    from bs4 import Tag

# Set up the logger
logger = logging.getLogger(__name__)


class Make:
    """Make class."""

    def __init__(
        self: Make,
        ident: int,
        name: str,
        children_url: str,
    ) -> None:
        """Initialize the Make object."""
        self.id = ident
        self.name = name
        self.children_url = children_url
        self.models: list[model.Model] = []

        self.children_source: Tag | None = None

    def __str__(self: Make) -> str:
        """Return the Make's name."""
        return self.name

    def add_model(self: Make, model: model.Model) -> None:
        """Add a model to the Make's list of models."""
        self.models.append(model)

    async def get_models(
        self: Make,
        db: aiosqlite.Connection,
    ) -> None:
        """Get the models for a given make."""
        # Check if the "model" is a valid model
        if "coches" not in self.children_url:
            logger.debug("Skipping %s as it is not a valid model", self.name)
            return
        if not self.children_source:
            logger.error("No source found for %s", self.name)
            return
        models = self.children_source.find_all("li", class_="vehicle-block")

        # Get the models
        for model_html in models:
            # Parse the model's:
            # - Name
            # - Year
            # - Href
            try:
                model_name_html = model_html.find("div", class_="veh-name")
                model_name = model_name_html.text.split("|")[0].strip()
                if all(model_obj.name != model_name for model_obj in self.models):
                    model_year = model_name_html.find("span").text
                    model_url = model_html.find("a")["href"]
                    next_id = await utils.get_next_id("models", db=db)
                    model_obj = model.Model(
                        ident=next_id,
                        name=model_name,
                        children_url=utils.BASE_URL + model_url + "/datos",
                        make=self,
                    )
                    # Insert the model into the database
                    await utils.insert_into_database(model_obj, "models", db=db)
                    # Add the model to the make
                    self.add_model(model_obj)
            except AttributeError:
                logger.exception("Error getting model for %s", self.name)
                return
