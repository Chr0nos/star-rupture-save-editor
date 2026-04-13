# Star Rupture Save Editor

A CLI tool for inspecting and modifying Star Rupture save files (`.sav`).

Originally created to migrate saves from the **PTR (Public Test Release)** branch back to the main branch after the developers marked them as incompatible. With this tool, those saves are fully recognized and playable on the main branch.

## ⚠️ Warning

**Always back up your save files before using this tool.** Mistakes are not recoverable — copy your entire save folder to a safe location first.

## Installation

Requires [uv](https://github.com/astral-sh/uv).

```bash
uv sync
```

## Commands

### `migrate` — PTR → main branch migration

Strips PTR-specific fields that cause the game to reject the save on the main branch.

```bash
uv run starrupturesaveeditor/saveeditor.py migrate <save_slot> <output_slot>
```

**Example:**

```bash
uv run starrupturesaveeditor/saveeditor.py migrate saves/PTR0 saves/0
# Produces: saves/0.sav + saves/0.met
```

### `decode` — Export save to JSON

Decompresses a `.sav` file to human-readable JSON for inspection or manual editing.

```bash
uv run starrupturesaveeditor/saveeditor.py decode <input.sav> <output.json>
```

**Example:**

```bash
uv run starrupturesaveeditor/saveeditor.py decode saves/Slot1.sav saves/Slot1.json
```

### `encode` — Import JSON back to save

Recompresses an edited JSON file back into a `.sav` file the game can load.

```bash
uv run starrupturesaveeditor/saveeditor.py encode <input.json> <output_slot>
```

**Example:**

```bash
uv run starrupturesaveeditor/saveeditor.py encode saves/Slot1.json saves/Slot1_edited
# Produces: saves/Slot1_edited.sav + saves/Slot1_edited.met
```

### `list-players` — List players in a save

Shows all player IDs and their current world positions.

```bash
uv run starrupturesaveeditor/saveeditor.py list-players <input_file>
```

**Example:**

```bash
uv run starrupturesaveeditor/saveeditor.py list-players saves/Slot1.sav
```

### `set-player-attribute` — Modify a player survival stat

Sets a survival attribute (health, energy, shield, etc.) for a specific player.

```bash
uv run starrupturesaveeditor/saveeditor.py set-player-attribute <input_file> <output_slot> <player_id> <property> <min> <max> <current>
```

**Settable attributes:** `health`, `energy`, `shield`, `hydration`, `calories`, `toxicity`, `radiation`, `heat`, `drain`, `corrosion`, `oxygen`, `medToolCharge`, `grenadeCharge`, `movementSpeedMultiplier`

**Example** — refill health for player 0:

```bash
uv run starrupturesaveeditor/saveeditor.py set-player-attribute saves/Slot1.sav saves/Slot1_fixed 0 health 0 150 100
```

### `list-corporations` — List corporations

Shows all corporations with their level, reputation, and visibility.

```bash
uv run starrupturesaveeditor/saveeditor.py list-corporations <input_file>
```

**Example:**

```bash
uv run starrupturesaveeditor/saveeditor.py list-corporations saves/Slot1.sav
```

### `set-datapoints` — Set datapoints balance

Sets the player's datapoints (in-game currency).

```bash
uv run starrupturesaveeditor/saveeditor.py set-datapoints <input_file> <output_slot> <datapoints>
```

**Example:**

```bash
uv run starrupturesaveeditor/saveeditor.py set-datapoints saves/Slot1.sav saves/Slot1_rich 99999
```

## Save file locations

**Linux (Steam/Proton):**
```
~/.local/share/Steam/steamapps/compatdata/1631270/pfx/drive_c/users/steamuser/AppData/Local/StarRupture/Saved/SaveGames/
```

**Windows:**
```
C:\Program Files (x86)\Steam\userdata\[Your_Steam_ID]\1631270\remote\Saved\SaveGames
```

Each slot consists of two files: `<SlotName>.sav` (compressed game data) and `<SlotName>.met` (metadata). Both are regenerated when you use any command that writes an output slot.

Save slot names visible in-game are single digits (`0` through `9`). Using any other name (e.g. `PTR0`, `backup`) will create a valid save file but it won't appear in the game's save list — useful as a staging area before writing to a proper slot.

## How it works

### .sav file structure

Star Rupture save files use a custom compressed format:

| Offset | Size | Description |
|--------|------|-------------|
| 0 | 4 bytes | Uncompressed JSON size (little-endian) |
| 4 | 2 bytes | zlib header (`0x78 0x9C`) |
| 6 | variable | Deflate payload — compressed JSON game data |
| end | 4 bytes | Adler32 checksum |

### PTR migration

The `migrate` command removes the `gameVersion` root key and the per-player `lastPlayedGameVersion` field that were added during the PTR and cause the main branch to reject the save.

## Credits

Special thanks to [AlienXAXS/StarRupture-Save-Manager](https://github.com/AlienXAXS/StarRupture-Save-Manager) for their amazing work reverse-engineering the `.sav` format and sharing how the file obfuscation works.
