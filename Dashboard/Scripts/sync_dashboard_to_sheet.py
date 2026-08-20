import json
import pathlib
import sys

# Add Scripts directory to sys.path to import palworld_sync
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import palworld_sync as sync

def sync_dashboard_json_to_sheet():
    dashboard_json = pathlib.Path(__file__).parent.parent / "Dashboard" / "pals.json"
    if not dashboard_json.exists():
        print(f"[!] Dashboard JSON file not found at {dashboard_json}")
        return False

    with open(dashboard_json, "r", encoding="utf-8") as f:
        structured_pals = json.load(f)

    print(f"[*] Preparing {len(structured_pals)} Pal entries for Google Sheets upload...")

    rows_data = []
    for idx, pal in enumerate(structured_pals, start=2):
        paldeck_num = pal.get("paldeck_num", "#???")
        display_name = pal.get("name", "Unknown Pal")
        portrait_formula = f'=XLOOKUP(A{idx}, PalsTable[Paldeck #], PalsTable[Portrait])'
        elem1 = pal.get("element1", "Neutral")
        elem2 = pal.get("element2") or ""
        raw_id = pal.get("raw_id", "Custom_Pal")
        level = pal.get("level", 1)
        stars = pal.get("stars", "-")
        gender_str = pal.get("gender_symbol") or ("♂ Male" if pal.get("gender") == "male" else "♀ Female" if pal.get("gender") == "female" else "⚪ N/A")
        favorite_str = pal.get("favorite", "-")
        location = pal.get("location", "Palbox Storage")
        origin_str = "IMAGE" if pal.get("is_imported") else "-"
        
        # Work suitabilities
        work_badges = pal.get("work_suitabilities", [])
        work_str = ", ".join([f"{w['emoji']} {w['level']}" for w in work_badges]) if work_badges else "-"

        is_boss_str = "Yes (Alpha)" if pal.get("is_boss") else "No"
        hp_iv = pal.get("hp_iv", 50)
        melee_iv = pal.get("melee_iv", 50)
        shot_iv = pal.get("shot_iv", 50)
        def_iv = pal.get("def_iv", 50)

        # Active skills (pad to 3)
        act_skills = list(pal.get("active_skills", []))
        while len(act_skills) < 3:
            act_skills.append("-")
        act_skills = act_skills[:3]

        # Passive skills (pad to 4 names)
        pass_objs = pal.get("passive_skills", [])
        pass_skills = []
        for p in pass_objs:
            if isinstance(p, dict):
                pass_skills.append(p.get("name", "-"))
            elif isinstance(p, str):
                pass_skills.append(p)
        while len(pass_skills) < 4:
            pass_skills.append("-")
        pass_skills = pass_skills[:4]

        # Column Z (26th column) - Unique ID for each Pal
        inst_guid = pal.get("instance_guid", f"custom-guid-{idx}")

        row = [
            paldeck_num,
            display_name,
            portrait_formula,
            elem1,
            elem2,
            raw_id,
            level,
            stars,
            gender_str,
            favorite_str,
            location,
            origin_str,
            work_str,
            is_boss_str,
            hp_iv,
            melee_iv,
            shot_iv,
            def_iv,
        ] + act_skills + pass_skills + [inst_guid]

        rows_data.append(row)

    print(f"[*] Uploading {len(rows_data)} rows to Google Sheet 'My Pals' tab...")
    sync.upload_to_google_sheet(rows_data, sync.GOOGLE_CREDENTIALS_JSON)
    print(f"[OK] Successfully updated 'My Pals' table with {len(rows_data)} Pal entries!")
    return True

if __name__ == "__main__":
    sync_dashboard_json_to_sheet()
