# CS2 Real-Demo Parser Spike & Event Inspection Report

**Document Version:** 1.0  
**Target Issue:** Issue #2 (`Task 2: Real-Demo Parser Spike & Event Inspection`)  
**Demo Analyzed:** `AdiletZagadkasy.dem` (CS2 FACEIT Match on `de_mirage`)  
**Parser Library:** `demoparser2` (Rust-backed CS2 demo parser)  
**Date:** 2026-10-13  

---

## 1. Executive Summary

This spike tests extracting match ticks, round events, utility detonations, player rosters, and death coordinates from a real CS2 match demo recorded on `de_mirage`. It establishes the empirical schema and coordinate bounds that all subsequent domain models (`app/services/analysis/models.py`, Issue #10) and unit test fixtures (`backend/tests/fixtures/`, Issue #11) must adhere to.

---

## 2. `demoparser2` API Surface & Invocation Rules

In CS2, `demoparser2` exposes an object-oriented API via the `DemoParser` class. Key observations from testing:

```python
from demoparser2 import DemoParser

parser = DemoParser(demo_path)
```

1. **Header Parsing:** `parser.parse_header() -> dict`
   Returns metadata dictionary with `map_name`, `server_name`, `patch_version`, and engine flags.
2. **Player Info:** `parser.parse_player_info() -> pandas.DataFrame`
   Returns participants with columns `['steamid', 'name', 'team_number']`.
3. **Event Parsing:** `parser.parse_events(event_names: List[str], player: Optional[List[str]] = None) -> List[Tuple[str, pandas.DataFrame]]`
   - **Crucial:** `event_names` must be passed as a **list of strings** (e.g. `['player_death']`), not a bare string.
   - Passing `player=['X', 'Y', 'Z']` automatically binds 3D coordinates for `attacker_X/Y/Z`, `user_X/Y/Z`, and `assister_X/Y/Z` directly into the returned DataFrame.
4. **Tick Data:** `parser.parse_ticks(wanted_props: List[str], ticks: Optional[List[int]] = None) -> pandas.DataFrame`
   Extracts player state at specified or all ticks.

---

## 3. Demo Header & Map Inspection

| Field | Type | Sample Value | Notes |
| :--- | :--- | :--- | :--- |
| `map_name` | `str` | `"de_mirage"` | Used by Issue #9 to validate map compatibility |
| `server_name` | `str` | `"FACEIT.com register to play here"` | Confirms FACEIT competitive match |
| `demo_version_name` | `str` | `"valve_demo_2"` | CS2 Valve demo format |
| `patch_version` | `str` | `"14181"` | Game build version |
| `fullpackets_version` | `str` | `"2"` | Packet framing version |

---

## 4. Player Roster Schema (`parse_player_info()`)

Returns 10 human players for standard 5v5 competitive matches:

| Column | Type | Nullable | Description / Sample |
| :--- | :--- | :--- | :--- |
| `steamid` | `int64` | No | 64-bit SteamID (e.g. `76561199148823733`) |
| `name` | `str` | No | Player in-game nickname (e.g. `"-kyzzen-"`, `"sh1izzza"`) |
| `team_number` | `int64` | No | Starting team assignment (`2` for T, `3` for CT) |

---

## 5. Player Ticks Schema (`parse_ticks()`)

Extracted using `parser.parse_ticks(['X', 'Y', 'Z', 'health', 'team_num', 'is_alive'])`:

| Column | Type | Nullable | Description / Range |
| :--- | :--- | :--- | :--- |
| `tick` | `int64` | No | Match tick index (e.g. `1000`, `2000`) |
| `steamid` | `int64` | No | Player SteamID |
| `name` | `str` | No | Player nickname |
| `team_num` | `int64` | No | `2` = Terrorist (T), `3` = Counter-Terrorist (CT) |
| `health` | `int64` | No | Player health points (`0` to `100`) |
| `is_alive` | `bool` | No | `True` if alive, `False` if dead |
| `X` | `float32` | No | X-coordinate in game units |
| `Y` | `float32` | No | Y-coordinate in game units |
| `Z` | `float32` | No | Z-coordinate (elevation) in game units |

### Observed Mirage Coordinate Boundaries
Across the entire match on `de_mirage`, player positions occupy the following bounds:
- **X Dimension:** `[-2656.0, 1423.0]` (West to East)
- **Y Dimension:** `[-2581.0, 888.0]` (South to North)
- **Z Dimension:** `[-368.0, 16.0]` (Underpass floor to Palace / Sniper's Nest elevation)

---

## 6. Player Death Events (`parse_events(['player_death'])`)

Extracted with `player=['X', 'Y', 'Z']` to capture player positions at moment of death:

| Column | Type | Nullable | Description / Semantics |
| :--- | :--- | :--- | :--- |
| `tick` | `int64` | No | Tick timestamp of death |
| `user_steamid` | `int64` | No | SteamID of victim (the player who died) |
| `user_name` | `str` | No | Nickname of victim |
| `user_X`, `user_Y`, `user_Z` | `float64` | No | 3D coordinates of victim at death |
| `attacker_steamid` | `float64 / int64` | Yes | SteamID of killer; `NaN` / null for world/fall deaths |
| `attacker_name` | `str` | Yes | Nickname of killer; `NaN` / null for world deaths |
| `attacker_X`, `attacker_Y`, `attacker_Z` | `float64` | Yes | 3D coordinates of killer; `NaN` for world deaths |
| `assister_steamid` | `float64 / int64` | Yes | SteamID of assister; `NaN` if unassisted |
| `weapon` | `str` | No | Weapon used (e.g. `ak47`, `awp`, `knife`) or cause |
| `headshot` | `bool` | No | `True` if headshot, `False` otherwise |
| `distance` | `float32` | No | Distance between attacker and victim |

### Special Death Causes & Tradeability Guardrails
In CS2 demos, non-player deaths exhibit distinct characteristics:
1. **Fall Damage / World Damage:**
   - `weapon`: `"world"`
   - `attacker_steamid`: `NaN` (or identical to `user_steamid`)
   - `attacker_X`, `attacker_Y`, `attacker_Z`: `NaN`
   - *Rule:* Must be flagged `is_tradeable = False` (Issue #10, Issue #18).
2. **Bomb Explosion (C4):**
   - `weapon`: `"planted_c4"`
   - `attacker_steamid`: `NaN` or non-player entity
   - *Rule:* Must be flagged `is_tradeable = False`.
3. **Friendly Fire / Team Kill:**
   - `attacker_steamid` belongs to teammate.
   - *Rule:* Must be flagged `is_tradeable = False`.
4. **Suicide:**
   - `user_steamid == attacker_steamid`.
   - *Rule:* Must be flagged `is_tradeable = False`.

---

## 7. Utility Detonation Events

Utility events provide the foundation for site execution detection (Issue #19).

### 7.1 Smoke Grenade (`smokegrenade_detonate`)
- **Columns:** `['entityid', 'tick', 'user_name', 'user_steamid', 'x', 'y', 'z']`
- **Coordinate Case:** Lowercase `x`, `y`, `z` (`float64`).
- **Semantics:** Indicates bloom position and tick of smoke grenade.

### 7.2 Flashbang (`flashbang_detonate`)
- **Columns:** `['entityid', 'tick', 'user_name', 'user_steamid', 'x', 'y', 'z']`
- **Semantics:** Detonation position and tick of flashbang.

### 7.3 HE Grenade (`hegrenade_detonate`)
- **Columns:** `['entityid', 'tick', 'user_name', 'user_steamid', 'x', 'y', 'z']`
- **Semantics:** Detonation position and tick of high explosive grenade.

### 7.4 Molotov / Incendiary (`inferno_startburn`)
- **Columns:** `['entityid', 'tick', 'user_name', 'user_steamid', 'x', 'y', 'z']`
- **Semantics:** Start tick and origin position of molotov flame spread.

---

## 8. Bomb Events

| Event | Columns | Key Semantics |
| :--- | :--- | :--- |
| `bomb_planted` | `['c4', 'site', 'tick', 'user_name', 'user_steamid']` | `site` is numeric site ID (e.g. 91, 92); marks transition to post-plant |
| `bomb_defused` | `['site', 'tick', 'user_name', 'user_steamid']` | Defuse tick |
| `bomb_exploded` | `['site', 'tick']` | Bomb explosion tick; excludes surviving players from late death penalties |

---

## 9. Round Boundary Events

| Event | Columns | Key Semantics |
| :--- | :--- | :--- |
| `round_freeze_end` | `['tick']` | Marks end of freeze time; players can move |
| `round_officially_ended` | `['tick']` | Marks end of round scoring |
| `round_prestart` | `['tick']` | Round setup tick |
| `round_poststart` | `['tick']` | Round start |

---

## 10. Design Directives for Subsequent Issues

1. **Issue #10 (`app/services/analysis/adapter.py`):**
   - Must normalize `x/y/z` (lowercase in grenades) and `X/Y/Z` (uppercase in ticks/deaths) to a unified float tuple `(float, float, float)`.
   - Must cast `steamid` and `user_steamid` to string representations (`str(int(val))`) to prevent 64-bit precision truncation in JSON serializers.
   - Must set `is_tradeable = False` whenever `weapon in ['world', 'planted_c4']` or `attacker_steamid is None` or `attacker_steamid == user_steamid`.
2. **Issue #11 (`backend/tests/fixtures/`):**
   - Fixture JSON files must use exact column names and coordinate ranges documented in Sections 5, 6, and 7.
   - Coordinate numbers must fall within `X: [-2656, 1423]`, `Y: [-2581, 888]`, `Z: [-368, 16]`.
3. **Issue #19 (`Site Execution Detection`):**
   - Use `smokegrenade_detonate` and `flashbang_detonate` ticks to construct the $\ge 2$ utility deployment window.
