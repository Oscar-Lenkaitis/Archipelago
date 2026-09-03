from __future__ import annotations
import json
from importlib import resources
from typing import TYPE_CHECKING, Dict, List, Optional
from dataclasses import dataclass

from BaseClasses import Item, ItemClassification

if TYPE_CHECKING:
    from .world import DOTA2World


VICTORY_ITEM_NAME = "Victory"
# MacGuffin item: collect X to win (Prim goal) or unlock final character (Win with Character).
# Spirits stay classified as filler in item definitions so they don't interfere with progression
# density, but we override DeadlockItem.excludable so Spirits are never placed in excluded
# locations.
FILLER_ITEM_NAME = "Primordial Fragment"

class DOTA2Item(Item):
    game = "DOTA2"

    @property
    def excludable(self) -> bool:  # type: ignore[override]
        # Treat Primordial Fragments (MacGuffin) as non-excludable even though they are filler-classified.
        # This ensures they can't be placed on user-excluded locations while keeping them
        # out of progression-balancing logic.
        if self.name == FILLER_ITEM_NAME:
            return False
        return super().excludable
    
@dataclass(frozen=True)
class ItemDef:
    name: str
    classification: ItemClassification
    copies: int
    include_in_filler: bool

def _parse_classification(value: str) -> ItemClassification:
    v = (value or "").strip().lower()
    match v:
        case "progression":
            return ItemClassification.progression
        case "useful":
            return ItemClassification.useful
        case "trap":
            return ItemClassification.trap
        case "filler":
            return ItemClassification.filler
        case _:
            # Default to filler if unknown, but better to be strict for dev:
            raise ValueError(f"Unknown item classification '{value}'")

def load_hero_unlock_items() -> List[ItemDef]:
    # Works in source and in zipped apworld due to importlib.resources.
    
    with resources.files(__package__).joinpath("data/unlockHeroItems.json").open("r", encoding="utf-8") as f:
        data = json.load(f)
        items: List[ItemDef] = []

        for item in data['unlock_hero_items']:
            name = item["name"]
            classification = _parse_classification(item["classification"])
            copies = item["copies"]
            include_in_filler = item["include_in_filler"].strip().lower() == "true"
            items.append(ItemDef(name=name, classification=classification, copies=copies, include_in_filler=include_in_filler))
        return items

# Internal filler item used to pad itempool to location count when needed.
FILLER_ITEM_NAME = "Primordial Fragment"

def build_item_name_to_id(base_id: int, item_defs: list[ItemDef]) -> dict[str, int]:
    names = [d.name for d in item_defs]

    if FILLER_ITEM_NAME not in names:
        names.append(FILLER_ITEM_NAME)

    if VICTORY_ITEM_NAME not in names:
        names.append(VICTORY_ITEM_NAME)

    return {name: i for i, name in enumerate(names, base_id)}

# ITEM_NAME_TO_ID = {
#     "Key": 1,
#     "Sword": 2,
#     "Shield": 3,
#     "Hammer": 4,
#     "Health Upgrade": 5,
#     "Confetti Cannon": 6,
#     "Math Trap": 7,
# }

# DEFAULT_ITEM_CLASSIFICATIONS = {
#     "Key": ItemClassification.progression,
#     "Sword": ItemClassification.progression | ItemClassification.useful,  # Items can have multiple classifications.
#     "Shield": ItemClassification.progression,
#     "Hammer": ItemClassification.progression,
#     "Health Upgrade": ItemClassification.useful,
#     "Confetti Cannon": ItemClassification.filler,
#     "Math Trap": ItemClassification.trap,
# }

# class DOTA2Item(Item):
#     game = "DOTA2"

# def get_random_filler_item_name(world: DOTA2World) -> str:
#     # APQuest has an option called "trap_chance".
#     # This is the percentage chance that each filler item is a Math Trap instead of a Confetti Cannon.
#     # For this purpose, we need to use a random generator.

#     # IMPORTANT: Whenever you need to use a random generator, you must use world.random.
#     # This ensures that generating with the same generator seed twice yields the same output.
#     # DO NOT use a bare random object from Python's built-in random module.
#     if world.random.randint(0, 99) < world.options.trap_chance:
#         return "Math Trap"
#     return "Confetti Cannon"

# def create_item_with_correct_classification(world: DOTA2World, name: str) -> DOTA2Item:
#     # Our world class must have a create_item() function that can create any of our items by name at any time.
#     # So, we make this helper function that creates the item by name with the correct classification.
#     # Note: This function's content could just be the contents of world.create_item in world.py directly,
#     # but it seemed nicer to have it in its own function over here in items.py.
#     classification = DEFAULT_ITEM_CLASSIFICATIONS[name]

#     # It is perfectly normal and valid for an item's classification to differ based on the player's options.
#     # In our case, Health Upgrades are only relevant to logic (and thus labeled as "progression") in hard mode.
#     if name == "Health Upgrade" and world.options.hard_mode:
#         classification = ItemClassification.progression

#     return DOTA2Item(name, classification, ITEM_NAME_TO_ID[name], world.player)

# # With those two helper functions defined, let's now get to actually creating and submitting our itempool.
# def create_all_items(world: DOTA2World) -> None:
#     # This is the function in which we will create all the items that this world submits to the multiworld item pool.
#     # There must be exactly as many items as there are locations.
#     # In our case, there are either six or seven locations.
#     # We must make sure that when there are six locations, there are six items,
#     # and when there are seven locations, there are seven items.

#     # Creating items should generally be done via the world's create_item method.
#     # First, we create a list containing all the items that always exist.

#     itempool: list[Item] = [
#         world.create_item("Key"),
#         world.create_item("Sword"),
#         world.create_item("Shield"),
#         world.create_item("Health Upgrade"),
#         world.create_item("Health Upgrade"),
#     ]

#     # Some items may only exist if the player enables certain options.
#     # In our case, If the hammer option is enabled, the sixth item is the Hammer.
#     # Otherwise, we add a filler Confetti Cannon.
#     if world.options.hammer:
#         # Once again, it is important to stress that even though the Hammer doesn't always exist,
#         # it must be present in the worlds item_name_to_id.
#         # Whether it is actually in the itempool is determined purely by whether we create and add the item here.
#         itempool.append(world.create_item("Hammer"))

#     # Archipelago requires that each world submits as many locations as it submits items.
#     # This is where we can use our filler and trap items.
#     # APQuest has two of these: The Confetti Cannon and the Math Trap.
#     # (Unfortunately, Archipelago is a bit ambiguous about its terminology here:
#     #  "filler" is an ItemClassification separate from "trap", but in a lot of its functions,
#     #  Archipelago will use "filler" to just mean "an additional item created to fill out the itempool".
#     #  "Filler" in this sense can technically have any ItemClassification,
#     #  but most commonly ItemClassification.filler or ItemClassification.trap.
#     #  Starting here, the word "filler" will be used to collectively refer to APQuest's Confetti Cannon and Math Trap,
#     #  which are ItemClassification.filler and ItemClassification.trap respectively.)
#     # Creating filler items works the same as any other item. But there is a question:
#     # How many filler items do we actually need to create?
#     # In regions.py, we created either six or seven locations depending on the "extra_starting_chest" option.
#     # In this function, we have created five or six items depending on whether the "hammer" option is enabled.
#     # We *could* have a really complicated if-else tree checking the options again, but there is a better way.
#     # We can compare the size of our itempool so far to the number of locations in our world.

#     # The length of our itempool is easy to determine, since we have it as a list.
#     number_of_items = len(itempool)

#     # The number of locations is also easy to determine, but we have to be careful.
#     # Just calling len(world.get_locations()) would report an incorrect number, because of our *event locations*.
#     # What we actually want is the number of *unfilled* locations. Luckily, there is a helper method for this:
#     number_of_unfilled_locations = len(world.multiworld.get_unfilled_locations(world.player))

#     # Now, we just subtract the number of items from the number of locations to get the number of empty item slots.
#     needed_number_of_filler_items = number_of_unfilled_locations - number_of_items

#     # Finally, we create that many filler items and add them to the itempool.
#     # To create our filler, we could just use world.create_item("Confetti Cannon").
#     # But there is an alternative that works even better for most worlds, including APQuest.
#     # As discussed above, our world must have a get_filler_item_name() function defined,
#     # which must return the name of an infinitely repeatable filler item.
#     # Defining this function enables the use of a helper function called world.create_filler().
#     # You can just use this function directly to create as many filler items as you need to complete your itempool.
#     itempool += [world.create_filler() for _ in range(needed_number_of_filler_items)]

#     # But... is that the right option for your game? Let's explore that.
#     # For some games, the concepts of "regular itempool filler" and "additionally created filler" are different.
#     # These games might want / require specific amounts of specific filler items in their regular pool.
#     # To achieve this, they will have to intentionally create the correct quantities using world.create_item().
#     # They may still use world.create_filler() to fill up the rest of their itempool with "repeatable filler",
#     # after creating their "specific quantity" filler and still having room left over.

#     # But there are many other games which *only* have infinitely repeatable filler items.
#     # They don't care about specific amounts of specific filler items, instead only caring about the proportions.
#     # In this case, world.create_filler() can just be used for the entire filler itempool.
#     # APQuest is one of these games:
#     # Regardless of whether it's filler for the regular itempool or additional filler for item links / etc.,
#     # we always just want a Confetti Cannon or a Math Trap depending on the "trap_chance" option.
#     # We defined this behavior in our get_random_filler_item_name() function, which in world.py,
#     # we'll bind to world.get_filler_item_name(). So, we can just use world.create_filler() for all of our filler.

#     # Anyway. With our world's itempool finalized, we now need to submit it to the multiworld itempool.
#     # This is how the generator actually knows about the existence of our items.
#     world.multiworld.itempool += itempool

#     # Sometimes, you might want the player to start with certain items already in their inventory.
#     # These items are called "precollected items".
#     # They will be sent as soon as they connect for the first time (depending on your client's item handling flag).
#     # Players can add precollected items themselves via the generic "start_inventory" option.
#     # If you want to add your own precollected items, you can do so via world.push_precollected().
#     if world.options.start_with_one_confetti_cannon:
#         # We're adding a filler item, but you can also add progression items to the player's precollected inventory.
#         starting_confetti_cannon = world.create_item("Confetti Cannon")
#         world.push_precollected(starting_confetti_cannon)
