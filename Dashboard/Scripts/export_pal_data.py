import json
import sys
import os
from pathlib import Path

# Add current directory to path to import palworld_sync
sys.path.insert(0, str(Path(__file__).parent))

import palworld_sync as sync

PAL_ICON_BASE_URL = "https://raw.githubusercontent.com/palworld-modding/icons/main/pals"

def get_pal_portrait_url(raw_id: str, display_name: str) -> str:
    """Generates local portrait URL for Pal, falling back to remote icon URL."""
    name_slug = display_name.lower().replace(" ", "-").replace("'", "").replace(".", "")
    clean_id = raw_id.replace("BOSS_", "").replace("Raid_", "").replace("NPC_", "").replace("SUMMON_", "").lower()
    clean_id_dash = clean_id.replace("_", "-")

    slug_map = {
        "astralyn": "astralym.png",
        "lilyqueen-noct": "lyleen-noct.png",
        "worldtreedragon": "astralym.png",
        "lilyqueen_dark": "lyleen-noct.png"
    }

    base_dir = Path(__file__).parent.parent / "Dashboard" / "Images" / "Everything Else" / "Palworld Complete Palpedia List"

    target_name = None
    if name_slug in slug_map:
        target_name = slug_map[name_slug]
    elif clean_id in slug_map:
        target_name = slug_map[clean_id]
    elif clean_id_dash in slug_map:
        target_name = slug_map[clean_id_dash]
    elif (base_dir / f"{name_slug}.png").exists():
        target_name = f"{name_slug}.png"
    elif (base_dir / f"{clean_id}.png").exists():
        target_name = f"{clean_id}.png"
    elif (base_dir / f"{clean_id_dash}.png").exists():
        target_name = f"{clean_id_dash}.png"

    if target_name:
        return f"Images/Everything Else/Palworld Complete Palpedia List/{target_name}"

    return f"https://raw.githubusercontent.com/palworld-modding/icons/main/pals/{clean_id}.png"

def export_pals_to_json(output_path: Path):
    target_save = sync.find_target_save()
    if not target_save:
        print("[!] Save file not found.")
        return False

    print(f"[*] Extracting Pal data from: {target_save}")
    sync.harvest_installed_mod_passives()

    # Parse Level.sav & LocalData.sav
    raw_pals = sync.parse_palworld_save(Path(target_save))
    if not raw_pals:
        print("[!] No Pals extracted.")
        return False

    structured_pals = []

    for row in raw_pals:
        if len(row) < 26:
            continue

        paldeck_num = row[0]
        display_name = row[1]
        raw_id = row[5]
        level = row[6]
        star_str = row[7]
        gender_raw = row[8]
        fav_str = row[9]
        location = row[10]
        origin_str = row[11]
        work_str = row[12]
        is_alpha_str = row[13]
        hp_iv = row[14]
        melee_iv = row[15]
        shot_iv = row[16]
        def_iv = row[17]
        active_skills = [s for s in row[18:21] if s and s != "-"]
        passive_skills = [p for p in row[21:25] if p and p != "-"]
        inst_guid = row[25]

        # Extract Element 1 and Element 2 from PAL_MASTER_MAP
        pal_info = sync.get_pal_info(raw_id)
        elem1 = pal_info[2] if len(pal_info) > 2 else "Neutral"
        elem2 = pal_info[3] if len(pal_info) > 3 and pal_info[3] else None

        # Parse work suitabilities into structured badges
        work_badges = []
        if work_str and work_str != "-":
            parts = [p.strip() for p in work_str.split(",")]
            for part in parts:
                tokens = part.split()
                if len(tokens) == 2:
                    emoji, lvl = tokens[0], tokens[1]
                    work_badges.append({"emoji": emoji, "level": lvl})

        # Structured passive skills with heatmap colors
        passive_objs = []
        for p_name in passive_skills:
            lvl = sync.get_passive_skill_level(p_name)
            hex_color = sync.PASSIVE_HEATMAP_HEX_MAP.get(lvl, "#2a2d34")
            passive_objs.append({
                "name": p_name,
                "tier": lvl,
                "color": hex_color
            })

        # Standardized gender string
        gender_type = "male" if "♂" in gender_raw else "female" if "♀" in gender_raw else "unknown"

        pal_obj = {
            "paldeck_num": paldeck_num,
            "name": display_name,
            "raw_id": raw_id,
            "portrait_url": get_pal_portrait_url(raw_id, display_name),
            "level": level,
            "stars": star_str,
            "gender": gender_type,
            "gender_symbol": gender_raw,
            "favorite": fav_str,
            "location": location,
            "is_imported": "IMAGE" in str(origin_str) or "Global" in location,
            "element1": elem1,
            "element2": elem2,
            "work_suitabilities": work_badges,
            "is_boss": is_alpha_str == "Yes (Alpha)",
            "hp_iv": hp_iv,
            "melee_iv": melee_iv,
            "shot_iv": shot_iv,
            "def_iv": def_iv,
            "active_skills": active_skills,
            "passive_skills": passive_objs,
            "instance_guid": inst_guid
        }

        structured_pals.append(pal_obj)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(structured_pals, f, indent=2, ensure_ascii=False)

    js_path = output_path.with_suffix(".js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.PALS_DATA = ")
        json.dump(structured_pals, f, indent=2, ensure_ascii=False)
        f.write(";\n")

    print(f"[OK] Exported {len(structured_pals)} Pals to {output_path} and {js_path}")
    return True

if __name__ == "__main__":
    out = Path(__file__).parent.parent / "Dashboard" / "pals.json"
    export_pals_to_json(out)
