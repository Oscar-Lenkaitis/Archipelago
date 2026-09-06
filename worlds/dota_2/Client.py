from __future__ import annotations
import re
import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Any
from datetime import datetime


from CommonClient import CommonContext, gui_enabled, server_loop, console_loop, ClientCommandProcessor

class Dota2CommandProcessor(ClientCommandProcessor):
    """DOTA2 2 client commands."""
    # def _cmd_heroes(self) -> None:
    #     """List heroes unlocked via received 'Unlock <Hero>' items (requires connection)."""
    #     self.ctx.cmd_heroes()

    def _cmd_goal(self) -> None:
        """Show your goal and how far you are from completing it."""
        self.ctx.cmd_goal()

    def _cmd_set_player_id(self, steamid3: str = "") -> None:
        """Set your SteamID. /set_player_id 123456789"""
        self.ctx.cmd_set_player_id([steamid3] if steamid3 else [])

try:
    from Utils import async_start
except Exception:
    async_start = None
try:
    from NetUtils import ClientStatus
except Exception:
    ClientStatus = None  # type: ignore[misc, assignment]

logger = logging.getLogger("Client")



@dataclass
class Dota2Save:
     # Per-seed metadata (seed_name will be filled once connected)
    seed_name: str = "unconnected"
    start_date_local: str = ""  # ISO8601 with local offset, set once at creation

    # Player config: stored as digits only (e.g. "123456789")
    steamid: Optional[str] = None

    Primordial_fragments_total: int = 0
    wins_total: int = 0
    
    # Unique heroes we've won with (authoritative for goal; not derived from server state)
    unique_heroes_won: list[str] = None
    
    # Anti-duplicate
    submitted_match_ids: list[str] = None

    most_recent_game_time: int

    def __post_init__(self) -> None:
        if self.submitted_match_ids is None:
            self.submitted_match_ids = []
        if not isinstance(self.unique_heroes_won, list):
            self.unique_heroes_won = []
        if not self.start_date_local:
            self.start_date_local = datetime.now().astimezone().replace(microsecond=0).isoformat()

def _get_save_dir() -> Path:
    try:
        from Utils import user_path  # type: ignore
        return Path(user_path("saves", "deadlock"))
    except Exception:
        return Path(".") / "deadlock_saves"


def _safe_filename(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s)[:120]

# Goal type values (must match options.GoalType)
GOAL_UNIQUE_CHARACTERS = 0
GOAL_TOTAL_WINS = 1
GOAL_PRIMORDIAL_FRAGMENTS = 2
GOAL_WIN_WITH_CHARACTER = 3

# MacGuffin item name (must match items.FILLER_ITEM_NAME)
FILLER_ITEM_NAME = "Primordial Fragment"

def _get_goal_options(slot_data: dict) -> tuple[int, int, int, int, int, str]:
    """Return (goal_type, unique_characters_to_win, total_wins_to_win,  fragments_to_win,  fragments_to_unlock_final, final_character) from slot_data."""
    if not isinstance(slot_data, dict):
        slot_data = {}
    raw_goal = slot_data.get("goal_type", GOAL_UNIQUE_CHARACTERS)
    if raw_goal in (1, "1", "total_wins"):
        goal_type = GOAL_TOTAL_WINS
    elif raw_goal in (2, "2", " fragments"):
        goal_type = GOAL_PRIMORDIAL_FRAGMENTS
    elif raw_goal in (3, "3", "win_with_character"):
        goal_type = GOAL_WIN_WITH_CHARACTER
    else:
        goal_type = GOAL_UNIQUE_CHARACTERS
    raw_unique = slot_data.get("unique_characters_to_win", 10)
    raw_total = slot_data.get("total_wins_to_win", 25)
    raw_fragments = slot_data.get("fragments_to_win", 10)
    raw_fragments_unlock = slot_data.get("fragments_to_unlock_final", 10)
    final_character = str(slot_data.get("final_character", "") or "").strip()
    try:
        unique = int(raw_unique)
    except (TypeError, ValueError):
        unique = 10
    try:
        total_wins = int(raw_total)
    except (TypeError, ValueError):
        total_wins = 25
    try:
        fragments = int(raw_fragments)
    except (TypeError, ValueError):
        fragments = 10
    try:
        fragments_unlock = int(raw_fragments_unlock)
    except (TypeError, ValueError):
        fragments_unlock = 10
    unique = max(1, min(38, unique))
    total_wins = max(1, min(100, total_wins))
    max_fragments = 20 if slot_data.get("game_mode", 0) == 1 else 10
    fragments = max(1, min(max_fragments, fragments))
    fragments_unlock = max(1, min(max_fragments, fragments_unlock))
    return (goal_type, unique, total_wins, fragments, fragments_unlock, final_character)

def _count_fragments_received(ctx: "Dota2Context") -> int:
    """Return how many fragments (MacGuffin) items the player has received."""
    try:
        game_items = ctx.item_names[ctx.game]
    except (KeyError, TypeError, AttributeError):
        game_items = {}
    count = 0
    for net_item in getattr(ctx, "items_received", []):
        item_id = getattr(net_item, "item", None)
        if item_id is None:
            continue
        if game_items.get(item_id) == FILLER_ITEM_NAME:
            count += 1
    return count

async def _check_goal_and_send_if_met(
    ctx: "Dota2Context",
    location_name_to_id: dict[str, int] | None = None,
    missing: set[int] | None = None,
    wins_after: int | None = None,
    hero_name_this_win: str | None = None,
) -> None:
    """If the player has met their win condition, send the Goal location check and status."""
    if location_name_to_id is None:
        try:
            game_locations = ctx.location_names[ctx.game]
        except (KeyError, TypeError):
            game_locations = {}
        location_name_to_id = {name: loc_id for loc_id, name in game_locations.items()}
    if missing is None:
        missing = getattr(ctx, "missing_locations", set())
    if wins_after is None:
        wins_after = ctx.save.wins_total
    slot_data = getattr(ctx, "slot_data", None) or {}
    goal_type, unique_req, total_wins_req, fragments_req, fragments_unlock_req, final_character = _get_goal_options(slot_data)
    goal_met = False
    if goal_type == GOAL_UNIQUE_CHARACTERS and len(ctx.save.unique_heroes_won) >= unique_req:
        goal_met = True
    elif goal_type == GOAL_TOTAL_WINS and wins_after >= total_wins_req:
        goal_met = True
    elif goal_type == GOAL_PRIMORDIAL_FRAGMENTS:
        if _count_fragments_received(ctx) >= fragments_req:
            goal_met = True
    elif goal_type == GOAL_WIN_WITH_CHARACTER and final_character and hero_name_this_win is not None:
        if _count_fragments_received(ctx) >= fragments_unlock_req and hero_name_this_win == final_character:
            goal_met = True
    if goal_met and ClientStatus is not None:
        goal_loc_id = location_name_to_id.get("Goal")
        if goal_loc_id is not None and goal_loc_id in missing:
            await ctx.check_locations([goal_loc_id])
            ctx.output("Goal completed! You have met the win condition.")
            ctx.finished_game = True
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])




class Dota2Context(CommonContext):
    game = "DOTA 2"


    def __init__(self, server_address = None, password = None):
        super().__init__(server_address, password)

        self.command_processor = Dota2CommandProcessor
        
        self.items_handling = 0b111

        self.save: Dota2Save = Dota2Save(seed_name=self.seed_name)
        self._save_path: Optional[Path] = None
        self._save_loaded_for_seed: bool = False

        # load offline save immediately so /stats and /set_player_id work before connect
        self.ensure_seed_save_loaded()
        

    async def server_auth(self, password_requested: bool = False) -> None:
        """After RoomInfo, get slot name (if needed) and send Connect packet so the server joins us to the room."""
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect(game="DOTA 2")

    # ---------- output ----------
    def output(self, text: str) -> None:
    # This shows in the GUI log pane (because of logging_pairs = [("Client","Archipelago")])
        try:
            logger.info(text)
        except Exception:
            # ultra-safe fallback
            print(text)

     # ---------- packets ----------
    def on_package(self, cmd: str, args: dict[str, Any]) -> None:
        if cmd == "RoomInfo":
            new_seed = args.get("seed_name") or "unknown_seed"
            if isinstance(new_seed, str) and new_seed:
                if new_seed != self.seed_name:
                    # When seed changes, rotate save
                    self.seed_name = new_seed
                    self._save_loaded_for_seed = False
                    self._warned_no_heroes = False
                    self.ensure_seed_save_loaded(migrate_from_unconnected=True)
        elif cmd == "Connected":
            # Store slot_data so we can read goal options (goal_type, unique_characters_to_win, total_wins_to_win, fragments_to_win)
            setattr(self, "slot_data", args.get("slot_data") or {})
            super().on_package(cmd, args)
            return
        elif cmd == "ReceivedItems":
            # Primordial Fragments (MacGuffin) goal can be met by receiving items; check after each batch
            if async_start:
                async_start(_check_goal_and_send_if_met(self), name="check_goal")

        super().on_package(cmd, args)

     # ---------- persistence ----------

    def _compute_save_path(self, seed_name: Optional[str] = None) -> Path:
        """Save path uses only seed and slot so it stays stable when server host/port or team changes."""
        slot = self.auth or "no_slot"
        seed = seed_name or self.seed_name or "unconnected"
        base = f"DOTA2__{_safe_filename(seed)}__{_safe_filename(slot)}"
        return _get_save_dir() / f"{base}.json"

    def _compute_legacy_save_path(self, seed_name: Optional[str] = None) -> Path:
        """Old path (server, team, slot, seed) for one-time migration only."""
        server = self.server_address or "no_server"
        slot = self.auth or "no_slot"
        team = str(getattr(self, "team", "0"))
        seed = seed_name or self.seed_name or "unconnected"
        base = f"DOTA2__{server}__{team}__{slot}__{seed}"
        return _get_save_dir() / f"{_safe_filename(base)}.json"

    def ensure_seed_save_loaded(self, migrate_from_unconnected: bool = False) -> None:
        if self._save_loaded_for_seed:
            return

        path = self._compute_save_path()
        self._save_path = path

        try:
            # If we're connecting for the first time and have an "unconnected" save, migrate it
            if migrate_from_unconnected and not path.exists():
                unconnected_path = self._compute_save_path(seed_name="unconnected")
                if unconnected_path.exists():
                    data = json.loads(unconnected_path.read_text(encoding="utf-8"))
                    migrated = Dota2Save(**data)
                    migrated.seed_name = self.seed_name
                    self.save = migrated
                    self._save_loaded_for_seed = True
                    self.save_save()
                    self.output(f"Migrated Deadlock save to seed '{self.seed_name}': {path.name}")
                    return

            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                self.save = Dota2Save(**data)
                self.save.seed_name = self.seed_name
                self._save_loaded_for_seed = True
                return

            # One-time migration from old path (server__team__slot__seed) if it exists
            legacy_path = self._compute_legacy_save_path()
            if legacy_path.exists():
                data = json.loads(legacy_path.read_text(encoding="utf-8"))
                self.save = Dota2Save(**data)
                self.save.seed_name = self.seed_name
                self._save_loaded_for_seed = True
                self.save_save()
                self.output(f"Migrated Deadlock save to new path (seed+slot): {path.name}")
                return

            # Create new
            self.save = Dota2Save(seed_name=self.seed_name)
            self._save_loaded_for_seed = True
            self.save_save()
        except Exception as e:
            self.output(f"Failed to load/create save ({path}): {e}")
            self._save_loaded_for_seed = True

    def save_save(self) -> None:
        if self._save_path is None:
            self._save_path = self._compute_save_path()
        self.save.seed_name = self.seed_name or self.save.seed_name or "unconnected"

        try:
            self._save_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_path.write_text(json.dumps(asdict(self.save), indent=2), encoding="utf-8")
        except Exception as e:
            self.output(f"Failed to write save ({self._save_path}): {e}")

    # --------- Commands ---------
    def cmd_goal(self) -> None:
        """Show current goal and progress toward it."""
        if not self.is_connected():
            self.output("Not connected. Connect to an Archipelago server to see your goal.")
            return
        self.ensure_seed_save_loaded()
        slot_data = getattr(self, "slot_data", None) or {}
        goal_type, unique_req, total_wins_req, fragment_req, fragment_unlock_req, final_character = _get_goal_options(slot_data)

        if goal_type == GOAL_UNIQUE_CHARACTERS:
            current = len(self.save.unique_heroes_won)
            self.output(f"Goal: Win with {unique_req} unique character(s).")
            self.output(f"Progress: {current} / {unique_req} unique character(s) won with.")
        elif goal_type == GOAL_TOTAL_WINS:
            current = self.save.wins_total
            self.output(f"Goal: Win {total_wins_req} match(es).")
            self.output(f"Progress: {current} / {total_wins_req} win(s).")
        elif goal_type == GOAL_WIN_WITH_CHARACTER and final_character:
            fragments_current = _count_fragments_received(self)
            self.output(f"Goal: Collect {fragment_unlock_req} fragments to unlock your final character, then win one match with them.")
            self.output(f"Win with: {final_character}")
            self.output(f"Progress: {fragments_current} / {fragment_unlock_req} fragments. Then win one match with {final_character}.")
        else:
            current = _count_fragments_received(self)
            self.output(f"Goal: Collect {fragment_req} fragments (MacGuffin).")
            self.output(f"Progress: {current} / {fragment_req} fragments received.")

    def cmd_set_player_id(self, args: list[str]) -> None:
        self.ensure_seed_save_loaded()

        if not args:
            self.output("Usage: /set_player_id 123456789  (steamid 32bit)")
            return

        self.save.steamid = args[0].strip()
        self.save_save()
        self.output(f"SteamID set to {args[0].strip()} (saved locally).")


async def _main() -> None:
    ctx = Dota2Context()
    if gui_enabled:
        ctx.run_gui()
        # Run server_loop as a task so it can return when no address without exiting the app.
        # Main loop waits for exit_event (set when user closes window / uses /exit) then shuts down.
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        await ctx.exit_event.wait()
        await ctx.shutdown()
    else:
        console_loop(ctx)
        await server_loop(ctx)


def run_deadlock_client(*args: str) -> None:
    asyncio.run(_main())