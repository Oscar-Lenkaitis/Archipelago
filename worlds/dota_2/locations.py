from __future__ import annotations

import json
from importlib import resources
import typing
from typing import TYPE_CHECKING, Dict, List
from dataclasses import dataclass

from BaseClasses import ItemClassification, Location

from . import items




if TYPE_CHECKING:
    from .world import DOTA2World


@dataclass(frozen=True)
class LocationDef:
    name: str
    type: str = ""  # "HERO_WIN", "ITEM_BUY", "GAME_STAT", "GOAL"


class DOTA2Location(Location):
    game = "DOTA2"


def load_hero_locations() -> List[LocationDef]:
    locs: List[LocationDef] = []

    with resources.files(__package__).joinpath("data/heroes.json").open("r", encoding="utf-8") as f:
        data = json.load(f)

        for hero in data['dota_heroes']:
            name = 'Win as ' + hero['localized_name']
            type = "HERO_WIN"
            locs.append(LocationDef(name = name, type=type))

    return locs

def load_item_locations() -> List[LocationDef]:
    locs: List[LocationDef] = []

    with resources.files(__package__).joinpath("data/itemPurchases.json").open("r", encoding="utf-8") as f:
        data = json.load(f)

        for item in data['purchase_locations']:
            type = ''
            name = item['name']
            if(name == 'Goal'):
                type = "GOAL"
            else: 
                type = "ITEM_BUY"

            locs.append(LocationDef(name = name, type=type))

    return locs

def build_location_name_to_id(base_id: int, location_defs: List[LocationDef], filter_fn: typing.Callable[[LocationDef], bool] | None = None,
    ) -> Dict[str, int]:
    """Build name -> id. If filter_fn is set, only include defs that pass it; IDs use index in full list."""
    if filter_fn is None:
        return {d.name: base_id + i for i, d in enumerate(location_defs)}
    return {d.name: base_id + i for i, d in enumerate(location_defs) if filter_fn(d)}






# def get_location_names_with_ids(location_names: list[str]) -> dict[str, int | None]:
#     return {location_name: LOCATION_NAME_TO_ID[location_name] for location_name in location_names}

# def create_all_locations(world: DOTA2World) -> None:
#     create_regular_locations(world)
#     create_events(world)

# def create_regular_locations(world: DOTA2World) -> None:
#     # Finally, we need to put the Locations ("checks") into their regions.
#     # Once again, before we do anything, we can grab our regions we created by using world.get_region()
#     overworld = world.get_region("Overworld")
#     top_left_room = world.get_region("Top Left Room")
#     bottom_right_room = world.get_region("Bottom Right Room")
#     right_room = world.get_region("Right Room")

#     # One way to create locations is by just creating them directly via their constructor.
#     bottom_left_chest = DOTA2Location(
#         world.player, "Bottom Left Chest", world.location_name_to_id["Bottom Left Chest"], overworld
#     )

#     # You can then add them to the region.
#     overworld.locations.append(bottom_left_chest)

#     # A simpler way to do this is by using the region.add_locations helper.
#     # For this, you need to have a dict of location names to their IDs (i.e. a subset of location_name_to_id)
#     # Aha! So that's why we made that "get_location_names_with_ids" helper method earlier.
#     # You also need to pass your overridden Location class.
#     bottom_right_room_locations = get_location_names_with_ids(
#         ["Bottom Right Room Left Chest", "Bottom Right Room Right Chest"]
#     )
#     bottom_right_room.add_locations(bottom_right_room_locations, DOTA2Location)

#     top_left_room_locations = get_location_names_with_ids(["Top Left Room Chest"])
#     top_left_room.add_locations(top_left_room_locations, DOTA2Location)

#     right_room_locations = get_location_names_with_ids(["Right Room Enemy Drop"])
#     right_room.add_locations(right_room_locations, DOTA2Location)

#     # Locations may be in different regions depending on the player's options.
#     # In our case, the hammer option puts the Top Middle Chest into its own room called Top Middle Room.
#     top_middle_room_locations = get_location_names_with_ids(["Top Middle Chest"])
#     if world.options.hammer:
#         top_middle_room = world.get_region("Top Middle Room")
#         top_middle_room.add_locations(top_middle_room_locations, DOTA2Location)
#     else:
#         overworld.add_locations(top_middle_room_locations, DOTA2Location)

#     # Locations may exist only if the player enables certain options.
#     # In our case, the extra_starting_chest option adds the Bottom Left Extra Chest location.
#     if world.options.extra_starting_chest:
#         # Once again, it is important to stress that even though the Bottom Left Extra Chest location doesn't always
#         # exist, it must still always be present in the world's location_name_to_id.
#         # Whether the location actually exists in the seed is purely determined by whether we create and add it here.
#         bottom_left_extra_chest = get_location_names_with_ids(["Bottom Left Extra Chest"])
#         overworld.add_locations(bottom_left_extra_chest, DOTA2Location)

# def create_events(world: DOTA2World) -> None:
#     # Sometimes, the player may perform in-game actions that allow them to progress which are not related to Items.
#     # In our case, the player must press a button in the top left room to open the final boss door.
#     # AP has something for this purpose: "Event locations" and "Event items".
#     # An event location is no different than a regular location, except it has the address "None".
#     # It is treated during generation like any other location, but then it is discarded.
#     # This location cannot be "sent" and its item cannot be "received", but the item can be used in logic rules.
#     # Since we are creating more locations and adding them to regions, we need to grab those regions again first.
#     top_left_room = world.get_region("Top Left Room")
#     final_boss_room = world.get_region("Final Boss Room")

#     # One way to create an event is simply to use one of the normal methods of creating a location.
#     button_in_top_left_room = DOTA2Location(world.player, "Top Left Room Button", None, top_left_room)
#     top_left_room.locations.append(button_in_top_left_room)

#     # We then need to put an event item onto the location.
#     # An event item is an item whose code is "None" (same as the event location's address),
#     # and whose classification is "progression". Item creation will be discussed more in items.py.
#     # Note: Usually, items are created in world.create_items(), which for us happens in items.py.
#     # However, when the location of an item is known ahead of time (as is the case with an event location/item pair),
#     # it is common practice to create the item when creating the location.
#     # Since locations also have to be finalized after world.create_regions(), which runs before world.create_items(),
#     # we'll create both the event location and the event item in our locations.py code.
#     button_item = items.DOTA2Item("Top Left Room Button Pressed", ItemClassification.progression, None, world.player)
#     button_in_top_left_room.place_locked_item(button_item)

#     # A way simpler way to do create an event location/item pair is by using the region.create_event helper.
#     # Luckily, we have another event we want to create: The Victory event.
#     # We will use this event to track whether the player can win the game.
#     # The Victory event is a completely optional abstraction - This will be discussed more in set_rules().
#     final_boss_room.add_event(
#         "Final Boss Defeated", "Victory", location_type=DOTA2Location, item_type=items.DOTA2Item
#     )

    # If you create all your regions and locations line-by-line like this,
    # the length of your create_regions might get out of hand.
    # Many worlds use more data-driven approaches using dataclasses or NamedTuples.
    # However, it is worth understanding how the actual creation of regions and locations works,
    # That way, we're not just mindlessly copy-pasting! :)