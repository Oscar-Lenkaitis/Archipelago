from __future__ import annotations

import typing
from typing import Any, Mapping, List

from BaseClasses import Region, ItemClassification
from worlds.AutoWorld import World, WebWorld

# Imports of base Archipelago modules must be absolute.
from BaseClasses import Tutorial
from worlds.AutoWorld import World, WebWorld

# Imports of your world's files must be relative.
from .options import (DOTA2Options, GoalType, _FINAL_CHARACTER_NAMES,)
from .items import DOTA2Item, load_hero_unlock_items, build_item_name_to_id, FILLER_ITEM_NAME, VICTORY_ITEM_NAME
from .locations import DOTA2Location, LocationDef, load_hero_locations, build_location_name_to_id, load_item_locations
from .rules import set_dota_rules
from .regions import create_regions_and_locations
# For our game to display correctly on the website, we need to define a WebWorld subclass.
class DOTA2WebWorld(WebWorld):
    # We need to override the "game" field of the WebWorld superclass.
    # This must be the same string as the regular World class.
    game = "DOTA 2"

    # Your game pages will have a visual theme (affecting e.g. the background image).
    # You can choose between dirt, grass, grassFlowers, ice, jungle, ocean, partyTime, and stone.
    theme = "stone"

    # A WebWorld can have any number of tutorials, but should always have at least an English setup guide.
    # Many WebWorlds just have one setup guide, but some have multiple, e.g. for different languages.
    # We need to create a Tutorial object for every setup guide.
    # In order, we need to provide a title, a description, a language, a filepath, a link, and authors.
    # The filepath is relative to a "/docs/" directory in the root folder of your apworld.
    # The "link" parameter is unused, but we still need to provide it.
    setup_en = Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up DOTA 2 for MultiWorld.",
        "English",
        "setup_en.md",
        "setup/en",
        ["CaptainBoscar"],
    )

    # We add these tutorials to our WebWorld by overriding the "tutorials" field.
    tutorials = [setup_en]


class DOTA2World(World):
    game = "DOTA 2"
    web = DOTA2WebWorld()
      # This is how we associate the options defined in our options.py with our world.
    options_dataclass = DOTA2Options
    options: DOTA2Options  # Common mistake: This has to be a colon (:), not an equals sign (=).


    # Choose a stable, unique base_id range for your world.
    base_id = 770_1540

     # These are populated at import time from JSON.
    _item_defs = load_hero_unlock_items()

    _location_defs: List[LocationDef] = []
    _location_defs.extend(load_hero_locations())
    _location_defs.extend(load_item_locations())

    item_name_to_id = build_item_name_to_id(base_id, _item_defs)
    # location_name_to_id is set per-instance in generate_early from filtered defs (see below).
    location_name_to_id = build_location_name_to_id(base_id + 10_000, _location_defs)


    def create_item(self, name: str) -> DOTA2Item:
        # Determine classification from defs or fallback for special items.
        if name == FILLER_ITEM_NAME:
            # Primordial Fragments (MacGuffin) use filler classification in defs; DeadlockItem.excludable
            # is overridden so they are never placed on excluded locations.
            classification = ItemClassification.filler
        elif name == VICTORY_ITEM_NAME:
            classification = ItemClassification.progression
        else:
            d = next((x for x in self._item_defs if x.name == name), None)
            if d is None:
                raise KeyError(f"Unknown item '{name}'")
            classification = d.classification
        return DOTA2Item(name, classification, self.item_name_to_id.get(name), self.player)

    def create_event(self, name: str) -> DOTA2Item:
        # Event items have id=None (not part of item_name_to_id)
        return DOTA2Item(name, ItemClassification.progression, None, self.player)
    

    def generate_early(self) -> None:

        #no current game mode option
        #mode = self._game_mode_value()
       
        # def mode_ok(d: LocationDef) -> bool:
        #     m = getattr(d, "game_mode", "") or ""
        #     return m == "" or m == mode
        def item_type_valid(d: LocationDef) -> bool:
            return d.type == "HERO_WIN" or d.type ==  "ITEM_BUY" or d.type ==  "GAME_STAT" or d.type ==  "GOAL"
    
        self._filtered_location_defs = [d for d in self._location_defs if item_type_valid(d)]
        self.location_name_to_id = build_location_name_to_id(
            self.base_id + 10_000, self._location_defs, filter_fn=item_type_valid
        )

    def create_regions(self) -> None:
        create_regions_and_locations(self, self._filtered_location_defs)

    def _max_primordial_fragments_placeable(self) -> int:
        """MacGuffin slots ~= non-Goal check locations (Goal holds locked Victory)."""
        return len(self._filtered_location_defs) - 1

    def _effective_primordial_fragments_to_unlock_final(self) -> int:
        """
        primordial fragments required before final character counts as unlocked (Win with Character).
        Capped so the threshold is reachable before opening that hero's win checks
        (those checks may contain primordial fragments). Matches what we send in slot_data.
        """
        max_sp = self._max_primordial_fragments_placeable()
        v = min(self.options.primordial_fragments_to_unlock_final.value, max_sp)
        #no game/check options right now
        # if self.options.game_mode == GameMode.option_street_brawl:
        #     v = min(v, 143)
        if self.options.goal_type.value == GoalType.option_win_with_character:
            v = min(v, max(1, max_sp - 1))
        return max(1, v)

    def _goal_location_name(self) -> str:
        if self.options.goal_type == GoalType.option_unique_characters:
            x = self.options.unique_characters_to_win.value
            return f"Goal: Win with {x} Unique Characters"
        if self.options.goal_type == GoalType.option_total_wins:
            x = self.options.total_wins_to_win.value
            return f"Goal: Win {x} Total Matches"
        if self.options.goal_type == GoalType.option_win_with_character:
            x = self.options.primordial_fragments_to_unlock_final.value
            hero = _FINAL_CHARACTER_NAMES[self.options.final_character.value] if self.options.final_character.value < len(_FINAL_CHARACTER_NAMES) else "?"
            return f"Goal: Win with {hero} (after {x} Spirits)"
        x = self.options.spirits_to_win.value
        return f"Goal: Collect {x} Spirits"

    def fill_slot_data(self) -> Mapping[str, Any]:
        """Data sent to the client in the Connected packet so /goal and win condition use the correct options."""
        # Max fragmetns = number of check locations (pool size); Goal has locked Victory so pool size is locations - 1
        max_primordial_fragments = self._max_primordial_fragments_placeable()
        primordial_fragments_to_win = min(self.options.primordial_fragments_to_win.value, max_primordial_fragments)
        primordial_fragments_to_unlock_final = self._effective_primordial_fragments_to_unlock_final()
        final_character_index = self.options.final_character.value
        final_character_name = _FINAL_CHARACTER_NAMES[final_character_index] if final_character_index < len(_FINAL_CHARACTER_NAMES) else ""
        return {
            "goal_type": self.options.goal_type.value,
            "unique_characters_to_win": self.options.unique_characters_to_win.value,
            "total_wins_to_win": self.options.total_wins_to_win.value,
            "primordial_fragments_to_win": primordial_fragments_to_win,
            "primordial_fragments_to_unlock_final": primordial_fragments_to_unlock_final,
            "final_character": final_character_name,
            # "game_mode": self.options.game_mode.value,
            # "exclude_hard_locations": self.options.exclude_hard_locations.value,
        }
    def create_items(self) -> None:
        # Add all defined items with copies
        pool = []
        final_character_name = ""
        if self.options.goal_type == GoalType.option_win_with_character:
            idx = self.options.final_character.value
            if idx < len(_FINAL_CHARACTER_NAMES):
                final_character_name = _FINAL_CHARACTER_NAMES[idx]
        unlock_final_item = f"Unlock {final_character_name}" if final_character_name else ""
        for d in self._item_defs:
            if unlock_final_item and d.name == unlock_final_item:
                continue  # Do not add Unlock FinalCharacter to pool; player gets it when they reach X Spirits
            for _ in range(d.copies):
                pool.append(self.create_item(d.name))

        # Pad pool so total items = (locations - 1): Goal gets a locked Victory in set_rules, so it doesn't take from the pool.
        loc_count = len(self.multiworld.get_locations(self.player))
        fill_count = loc_count - 1
        if len(pool) < fill_count:
            pool += [self.create_item(FILLER_ITEM_NAME) for _ in range(fill_count - len(pool))]

        self.multiworld.itempool += pool

    def set_rules(self) -> None:
        set_dota_rules(self)

        goal_loc = self.multiworld.get_location("Goal", self.player)
        goal_loc.place_locked_item(self.create_item(VICTORY_ITEM_NAME))

        if self.options.goal_type == GoalType.option_primordial_fragments:
            # MacGuffin win: collect X fragments. Allow Victory OR Spirits so the filler sees a reachable win (Victory at Goal).
            primordial_fragments_required = self.options.primordial_fragments_to_win.value
        
            self.multiworld.completion_condition[self.player] = (
                lambda state, p=self.player, req=primordial_fragments_required: (
                    state.has(VICTORY_ITEM_NAME, p) or state.has(FILLER_ITEM_NAME, p) >= req
                )
            )
        else:
            self.multiworld.completion_condition[self.player] = (
                lambda state: state.has(VICTORY_ITEM_NAME, self.player)
            )
    

    # origin_region_name = "Overworld"

    # def create_regions(self) -> None:
    #     regions.create_and_connect_regions(self)
    #     locations.create_all_locations(self)

    # def set_rules(self) -> None:
    #     rules.set_all_rules(self)

    # def create_items(self) -> None:
    #     items.create_all_items(self)

    # def create_item(self, name: str) -> items.DOTA2Item:
    #     return items.create_item_with_correct_classification(self, name)

    # def get_filler_item_name(self) -> str:
    #     return items.get_random_filler_item_name(self)

    # def fill_slot_data(self) -> Mapping[str, Any]:
    #     # If you need access to the player's chosen options on the client side, there is a helper for that.
    #     return self.options.as_dict(
    #         "hard_mode", "hammer", "extra_starting_chest", "confetti_explosiveness", "player_sprite"
    #     )

def _launch_dota2_client(*args: str) -> None:
    from worlds import LauncherComponents
    from .Client import run_dota2_client
    LauncherComponents.launch(run_dota2_client, name="DOTA 2 Client", args=args)

def _register_dota2_icon() -> str:
    """
    Register our icon with LauncherComponents using the apworld format so the launcher
    loads it from inside the apworld (no cache folder or filesystem extraction needed).
    See: LauncherComponents.py comment re "ap:module.name/path/to/file.png"
    """
    try:
        from worlds import LauncherComponents
    except ImportError:
        return "icon"  # fallback to default

    icon_key = "dota2"
    if icon_key not in LauncherComponents.icon_paths:
        LauncherComponents.icon_paths[icon_key] = f"ap:{__name__}/icons/Dota2.png"
    return icon_key

def _register_launcher_component() -> None:
    try:
        from worlds.LauncherComponents import Component, components
    except ImportError:
        return

    components.append(Component(
        display_name="Dota 2 Client",
        func=_launch_dota2_client,
        game_name="Dota 2",
        supports_uri=True,
        description="DOTA 2 Archipelago client.",
        icon=_register_dota2_icon(),
    ))

_register_launcher_component()