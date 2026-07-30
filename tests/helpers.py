"""Synthetic atlas fixtures used only for tests and documentation examples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw

from megumin_pet.contract import (
    ACTIVE_CELL_KEYS,
    ATLAS_HEIGHT,
    ATLAS_WIDTH,
    CELL_HEIGHT,
    CELL_WIDTH,
    COLUMNS,
    ROWS,
    cell_key,
)

Change = Literal["blank", "edge", "shift", "recolor"]


def make_pet(
    root: Path,
    *,
    pet_id: str = "fixture-pet",
    changes: dict[tuple[int, int], Change] | None = None,
    sprite_path: str = "spritesheet.webp",
) -> Path:
    """Create a valid abstract v2 pet fixture, optionally with targeted mutations."""
    pet_dir = root
    pet_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": pet_id,
        "displayName": "Fixture Pet",
        "description": "An abstract generated fixture used only by the PetDiff test suite.",
        "spriteVersionNumber": 2,
        "spritesheetPath": sprite_path,
    }
    (pet_dir / "pet.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    image = Image.new("RGBA", (ATLAS_WIDTH, ATLAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    mutations = changes or {}
    for row in range(ROWS):
        for column in range(COLUMNS):
            key = cell_key(row, column)
            mutation = mutations.get((row, column))
            if key not in ACTIVE_CELL_KEYS and mutation is None:
                continue
            if mutation == "blank":
                continue
            local_x = 28 + (column % 3) * 3
            local_y = 30 + (row % 4) * 2
            width = 72 + (column % 4) * 4
            height = 104 + (row % 3) * 5
            if mutation == "shift":
                local_x += 34
                local_y += 20
            if mutation == "edge":
                local_x = 0
            left = column * CELL_WIDTH + local_x
            top = row * CELL_HEIGHT + local_y
            color = (
                (40 + row * 17) % 220,
                (60 + column * 23) % 220,
                (90 + row * 11 + column * 7) % 220,
                255,
            )
            if mutation == "recolor":
                color = (245, 20, 195, 255)
            draw.rectangle((left, top, left + width, top + height), fill=color)
            eye_y = top + 24
            draw.rectangle((left + 18, eye_y, left + 22, eye_y + 4), fill=(255, 255, 255, 255))
            draw.rectangle((left + 48, eye_y, left + 52, eye_y + 4), fill=(255, 255, 255, 255))
    atlas_path = pet_dir.joinpath(*sprite_path.split("/"))
    atlas_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(atlas_path, format="WEBP", lossless=True, method=6)
    return pet_dir
