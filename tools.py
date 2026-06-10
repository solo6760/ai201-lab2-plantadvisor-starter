import json
import os
from datetime import datetime
from config import DATA_PATH

# Plant database and seasonal data are loaded once at module load.
# This mirrors how a real service would cache its data source in memory.
with open(os.path.join(DATA_PATH, "plants.json"), encoding="utf-8") as f:
    _plant_db = json.load(f)

with open(os.path.join(DATA_PATH, "seasons.json"), encoding="utf-8") as f:
    _season_data = json.load(f)

# Maps calendar months to seasons for auto-detection.
_MONTH_TO_SEASON = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "fall",  10: "fall",  11: "fall",
}


def lookup_plant(plant_name: str) -> dict:
    """
    Search the plant database for a plant by name and return its care information.

    TODO — Milestone 1:

    Right now this always returns a "not found" response. Your job is to implement
    the search logic so it can actually find plants.

    The plant database (_plant_db) is a dict where keys are lowercase slugs like
    "pothos", "snake_plant", "fiddle_leaf_fig". Each plant also has a "display_name"
    field and an "aliases" list with common alternate names.

    Your implementation should handle all three:
      1. Direct key match (e.g., "pothos" → finds "pothos")
      2. Display name match (e.g., "Pothos" → finds "pothos")
      3. Alias match (e.g., "devil's ivy" → finds "pothos")

    All matching should be case-insensitive. Strip whitespace from the input.

    Return format when found:
      {"found": True, "plant": <the full plant dict>}

    Return format when not found:
      {"found": False, "name": <original input>, "message": <helpful string>}

    The message in the not-found case matters — the agent will use it to decide
    what to tell the user. Your spec has a dedicated field for this — think about
    what information would actually be helpful to the agent.

    Before writing code, complete the lookup_plant section of specs/tool-functions-spec.md.
    """
    # Input normalization
    normalized = plant_name.strip().lower()

    # 1. Direct key match (slug)
    if normalized in _plant_db:
        return {"found": True, "plant": _plant_db[normalized]}

    # 2 & 3. Iterative search through values
    for plant in _plant_db.values():
        # Display name match
        if plant["display_name"].lower() == normalized:
            return {"found": True, "plant": plant}
        
        # Alias match
        if normalized in [alias.strip().lower() for alias in plant.get("aliases", [])]:
            return {"found": True, "plant": plant}

    return {
        "found": False,
        "name": plant_name,
        "message": f"I couldn't find a plant matching '{plant_name}' in my database. Please check the spelling or try a different common name. I have care information for many common houseplants like Pothos, Snake Plant, and Monstera.",
    }


def get_seasonal_conditions(season: str | None = None) -> dict:
    """
    Return current seasonal care context for houseplants.

    If season is provided and valid, returns that season's data.
    If season is None (or invalid), auto-detects from the current calendar month.

    Pre-implemented — read through this and the spec before working on lookup_plant().
    """
    VALID_SEASONS = {"spring", "summer", "fall", "winter"}

    if season and season.lower() in VALID_SEASONS:
        # Caller specified a valid season — use it directly
        season_key = season.lower()
        detected = False
    else:
        # Auto-detect from the current month using the _MONTH_TO_SEASON mapping
        current_month = datetime.now().month
        season_key = _MONTH_TO_SEASON[current_month]
        detected = True

    # Copy the season dict so we don't mutate the cached data
    result = dict(_season_data[season_key])
    result["detected_season"] = detected
    return result


def search_plants_by_attribute(light_requirement: str | None = None, difficulty: str | None = None) -> dict:
    """
    Search the plant database for plants matching specific care criteria.
    """
    matches = []
    
    for slug, plant in _plant_db.items():
        # Check difficulty filter
        if difficulty and plant.get("difficulty", "").lower() != difficulty.lower():
            continue
            
        # Check light requirement filter
        if light_requirement:
            plant_light = plant.get("light", {}).get("requirement", "").lower()
            if light_requirement.lower() not in plant_light:
                continue
        
        matches.append({
            "slug": slug,
            "display_name": plant["display_name"],
            "difficulty": plant["difficulty"],
            "light_requirement": plant["light"]["requirement"]
        })
        
    if matches:
        return {"found": True, "count": len(matches), "plants": matches}
    
    return {
        "found": False, 
        "message": f"No plants found matching the criteria (Light: {light_requirement}, Difficulty: {difficulty})."
    }


def get_plant_list() -> dict:
    """
    Return a list of all plant names and their difficulty levels present in the database.
    """
    plants = []
    for slug, plant in _plant_db.items():
        plants.append({
            "slug": slug,
            "display_name": plant.get("display_name"),
            "difficulty": plant.get("difficulty")
        })
    return {"plants": plants}
