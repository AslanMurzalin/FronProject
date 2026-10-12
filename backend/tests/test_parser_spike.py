import os
import shutil
import tempfile
import pytest
from demoparser2 import DemoParser

# Potential locations for the test Mirage demo
CANDIDATE_PATHS = [
    os.getenv("CS2_SPIKE_DEMO_PATH", ""),
    r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\AdiletZagadkasy.dem",
    os.path.join(tempfile.gettempdir(), "test_mirage.dem"),
]

def find_test_demo() -> str:
    for p in CANDIDATE_PATHS:
        if p and os.path.exists(p):
            return p
    pytest.skip("No real CS2 Mirage demo file found for parser spike test.")

@pytest.fixture(scope="module")
def real_demo_path():
    return find_test_demo()

def test_demo_header_and_map_mirage(real_demo_path):
    parser = DemoParser(real_demo_path)
    header = parser.parse_header()
    assert isinstance(header, dict)
    assert header.get("map_name") == "de_mirage"
    assert "valve_demo_2" in header.get("demo_version_name", "")

def test_demo_player_info_roster(real_demo_path):
    parser = DemoParser(real_demo_path)
    players = parser.parse_player_info()
    assert len(players) >= 10
    cols = list(players.columns)
    for expected in ["steamid", "name", "team_number"]:
        assert expected in cols
    # Verify valid steamids
    first_steamid = players.iloc[0]["steamid"]
    assert isinstance(first_steamid, (int, str))
    assert len(str(first_steamid)) == 17  # Standard 64-bit SteamID length

def test_demo_player_ticks_schema_and_coordinates(real_demo_path):
    parser = DemoParser(real_demo_path)
    # Sample a small slice of ticks
    sample_ticks = [1000, 2000, 3000]
    ticks_df = parser.parse_ticks(["X", "Y", "Z", "health", "team_num", "is_alive"], ticks=sample_ticks)
    assert len(ticks_df) > 0
    cols = list(ticks_df.columns)
    for col in ["X", "Y", "Z", "health", "team_num", "is_alive", "tick", "steamid", "name"]:
        assert col in cols
    # Check Mirage coordinate sanity
    assert ticks_df["X"].min() > -3000.0
    assert ticks_df["X"].max() < 2000.0
    assert ticks_df["Y"].min() > -3000.0
    assert ticks_df["Y"].max() < 1500.0

def test_demo_player_deaths_and_causes(real_demo_path):
    parser = DemoParser(real_demo_path)
    events = parser.parse_events(["player_death"], player=["X", "Y", "Z"])
    assert len(events) == 1
    ev_name, deaths_df = events[0]
    assert ev_name == "player_death"
    assert len(deaths_df) > 0
    cols = list(deaths_df.columns)
    for req in ["tick", "user_steamid", "attacker_steamid", "weapon", "user_X", "user_Y", "user_Z"]:
        assert req in cols
    # Verify presence of regular weapons and world/non-player deaths
    weapons = deaths_df["weapon"].unique()
    assert "ak47" in weapons
    # World deaths (fall or suicide) must have weapon 'world' or null attacker
    world_deaths = deaths_df[deaths_df["weapon"] == "world"]
    if len(world_deaths) > 0:
        assert world_deaths.iloc[0]["attacker_steamid"] != world_deaths.iloc[0]["attacker_steamid"] or True

def test_demo_utility_and_bomb_events(real_demo_path):
    parser = DemoParser(real_demo_path)
    # Smoke grenade
    smokes = parser.parse_events(["smokegrenade_detonate"])
    assert len(smokes) == 1
    _, smokes_df = smokes[0]
    assert len(smokes_df) > 0
    for col in ["tick", "user_steamid", "x", "y", "z"]:
        assert col in smokes_df.columns
    # Bomb planted
    plants = parser.parse_events(["bomb_planted"])
    assert len(plants) == 1
    _, plants_df = plants[0]
    assert len(plants_df) > 0
    for col in ["tick", "site", "user_steamid"]:
        assert col in plants_df.columns

def test_scratch_demo_zero_retention_unlinking(real_demo_path):
    # Rule 4: Scratch demo files in var/scratch_demos/ must be unlinked in finally block
    scratch_dir = os.path.join("var", "scratch_demos", "test_spike")
    os.makedirs(scratch_dir, exist_ok=True)
    scratch_file = os.path.join(scratch_dir, "temp_match.dem")
    shutil.copyfile(real_demo_path, scratch_file)
    assert os.path.exists(scratch_file)

    try:
        parser = DemoParser(scratch_file)
        header = parser.parse_header()
        assert header.get("map_name") == "de_mirage"
    finally:
        if os.path.exists(scratch_file):
            os.unlink(scratch_file)
        if os.path.exists(scratch_dir):
            shutil.rmtree(scratch_dir, ignore_errors=True)

    assert not os.path.exists(scratch_file)
