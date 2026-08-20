import glob
import json
import os
import re
import struct
import sys
import time
import traceback
import uuid
import zlib
from pathlib import Path

# Add Palworld Save Tool library directory to sys.path for palooz Oodle decompressor
SAVE_TOOL_LIB = Path(r"C:\Users\Natha\Desktop\Games\Palworld\Save Tool\lib")
if SAVE_TOOL_LIB.is_dir() and str(SAVE_TOOL_LIB) not in sys.path:
    sys.path.append(str(SAVE_TOOL_LIB))

import gspread
import psutil


# ==============================================================================
# CONFIGURATION & DIRECTORIES
# ==============================================================================
BASE_SCRIPT_DIR = Path(
    r"C:\Users\Natha\Desktop\Games\Palworld\Automatic_uploader"
)
LOGS_DIR = BASE_SCRIPT_DIR / "Logs"
EXPORTS_DIR = BASE_SCRIPT_DIR / ".json exports"

GOOGLE_CREDENTIALS_JSON = BASE_SCRIPT_DIR / "credentials.json"
GOOGLE_SHEET_NAME = "Palworld Master Database"

# Optional: Paste your full Google Sheet URL or Sheet ID here to bypass Drive search
GOOGLE_SHEET_URL_OR_KEY = ""

TARGET_SHEET_TAB_NAME = "My Pals"
PASSIVE_REF_TAB_NAME = "Passives and Implants"
SKILL_FRUITS_TAB_NAME = "Skill Fruits"

# ==============================================================================
# WORKBOOK REFERENCE FOR ELEMENT ICONS (Colors Tab)
# ==============================================================================
ELEMENT_REF_SHEET = "Colors"  # Reference tab containing Element icons
ELEMENT_NAME_COL = "B"        # Column containing Element text (starting row 3)
ELEMENT_ICON1_COL = "F"       # Column containing Primary Type Icon (Icon1)
ELEMENT_ICON2_COL = "G"       # Column containing Secondary Type Icon (Icon2)

PINNED_WORLD_SAVE_GUID = "66C167B649D78C6448EC92A2D0C95070"

SAVE_DIR = Path(
    os.path.expandvars(r"%LOCALAPPDATA%\Pal\Saved\SaveGames")
)

PROCESS_NAME = "Palworld-Win64-Shipping.exe"
POLL_INTERVAL_SECONDS = 5

GLOBAL_DNA_ICON_URL = "https://raw.githubusercontent.com/palworld-modding/icons/main/dna_purple.png"

# ==============================================================================
# WORK SUITABILITY COLUMNS & EMOJI REPEATER
# ==============================================================================
WORK_SUITABILITY_ORDER = [
    ("Kindling", ["Kindling"]),
    ("Watering", ["Watering"]),
    ("Planting", ["Planting"]),
    ("Generating Electricity", ["Electricity", "Generating Electricity"]),
    ("Handiwork", ["Handiwork"]),
    ("Gathering", ["Gathering"]),
    ("Lumbering", ["Lumbering"]),
    ("Mining", ["Mining"]),
    ("Medicine Production", ["Medicine", "Medicine Production"]),
    ("Cooling", ["Cooling"]),
    ("Transporting", ["Transporting"]),
    ("Farming", ["Farming"]),
]

WORK_EMOJI_MAP = {
    "Kindling": "🔥",
    "Watering": "💧",
    "Planting": "🌱",
    "Generating Electricity": "⚡",
    "Handiwork": "🔨",
    "Gathering": "🌾",
    "Lumbering": "🪓",
    "Mining": "⛏️",
    "Medicine Production": "🧪",
    "Cooling": "❄️",
    "Transporting": "📦",
    "Farming": "🐣",
}

# ==============================================================================
# SESSION TRANSCRIPT LOGGER
# ==============================================================================
class DualStream:
    """Tees standard output to both console and per-run log file cleanly."""
    def __init__(self, terminal_stream, file_stream):
        self.terminal = terminal_stream
        self.file = file_stream
        self.encoding = getattr(terminal_stream, "encoding", "utf-8")

    def write(self, message):
        try:
            self.terminal.write(message)
        except UnicodeEncodeError:
            try:
                self.terminal.write(message.encode(self.encoding, errors="replace").decode(self.encoding))
            except Exception:
                pass
        except Exception:
            pass
        try:
            if not self.file.closed:
                self.file.write(message)
                self.file.flush()
        except Exception:
            pass

    def flush(self):
        try:
            self.terminal.flush()
        except Exception:
            pass
        try:
            if not self.file.closed:
                self.file.flush()
        except Exception:
            pass

    def isatty(self):
        return getattr(self.terminal, "isatty", lambda: False)()


def init_session_transcript():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    log_path = LOGS_DIR / f"Transcript_{timestamp}.log"
    log_file = open(log_path, "a", encoding="utf-8")

    sys.stdout = DualStream(sys.__stdout__, log_file)
    sys.stderr = DualStream(sys.__stderr__, log_file)
    return log_file

# ==============================================================================
# MASTER ELEMENT TYPE NORMALIZATION & FORMULA BUILDERS
# ==============================================================================
MASTER_ELEMENT_COMBINATIONS = {
    "Neutral", "Fire", "Water", "Grass", "Electric", "Ice", "Ground", "Dark", "Dragon",
    "Dark / Dragon", "Dark / Electric", "Dark / Fire", "Dark / Grass", "Dark / Ground",
    "Dark / Ice", "Dark / Neutral", "Dark / Water",
    "Dragon / Electric", "Dragon / Fire", "Dragon / Grass", "Dragon / Ground",
    "Dragon / Ice", "Dragon / Neutral", "Dragon / Water",
    "Electric / Fire", "Electric / Grass", "Electric / Ground", "Electric / Ice",
    "Electric / Neutral", "Electric / Water",
    "Fire / Grass", "Fire / Ground", "Fire / Ice", "Fire / Neutral", "Fire / Water",
    "Grass / Ground", "Grass / Ice", "Grass / Neutral", "Grass / Water",
    "Ground / Ice", "Ground / Neutral", "Ground / Water",
    "Ice / Neutral", "Ice / Water",
    "Neutral / Water",
}


def format_combined_element(elem1, elem2=None):
    if not elem1 or elem1 == "-":
        return "-"
    
    elem1_clean = elem1.strip().capitalize()
    if not elem2 or elem2 == "-":
        return elem1_clean

    elem2_clean = elem2.strip().capitalize()
    
    forward_pair = f"{elem1_clean} / {elem2_clean}"
    reverse_pair = f"{elem2_clean} / {elem1_clean}"

    if forward_pair in MASTER_ELEMENT_COMBINATIONS:
        return forward_pair
    elif reverse_pair in MASTER_ELEMENT_COMBINATIONS:
        return reverse_pair
    
    return forward_pair


def build_element_xlookup_formula(element_str: str, icon_col: str) -> str:
    """Builds a Google Sheets XLOOKUP formula to pull Icon1 (F) or Icon2 (G) from Colors tab."""
    if not element_str or element_str == "-":
        return ""
    safe_elem = element_str.replace('"', '""')
    return (
        f'=IFERROR(XLOOKUP("{safe_elem}", '
        f"'{ELEMENT_REF_SHEET}'!{ELEMENT_NAME_COL}:{ELEMENT_NAME_COL}, "
        f"'{ELEMENT_REF_SHEET}'!{icon_col}:{icon_col}, "
        f'"{safe_elem if icon_col == ELEMENT_ICON1_COL else ""}"), "")'
    )

# ==============================================================================
# MASTER PAL MAPPING (Internal ID -> Name, Deck #, Type 1, Type 2, Base Work)
# ==============================================================================
PAL_MASTER_MAP = {
    "SheepBall": ("Lamball", "#001", "Neutral", None, "Handiwork Lv1, Transporting Lv1, Farming Lv1"),
    "PinkCat": ("Cattiva", "#002", "Neutral", None, "Handiwork Lv1, Transporting Lv1, Gathering Lv1, Mining Lv1"),
    "ChickenPal": ("Chikipi", "#003", "Neutral", None, "Gathering Lv1, Farming Lv1"),
    "Carbunclo": ("Lifmunk", "#004", "Grass", None, "Planting Lv1, Handiwork Lv1, Lumbering Lv1, Medicine Lv1, Gathering Lv1"),
    "BluePlatypus": ("Fuack", "#005", "Water", None, "Handiwork Lv1, Transporting Lv1, Watering Lv1"),
    "BluePlatypus_Fire": ("Fuack Ignis", "#005B", "Fire", "Water", "Handiwork Lv1, Transporting Lv1, Kindling Lv1"),
    "CuteFox": ("Vixy", "#006", "Neutral", None, "Gathering Lv1, Farming Lv1"),
    "FlyingManta": ("Celaray", "#007", "Water", None, "Transporting Lv1, Watering Lv1"),
    "FlyingManta_Thunder": ("Celaray Lux", "#007B", "Electric", "Water", "Transporting Lv1, Electricity Lv1"),
    "WoolFox": ("Cremis", "#008", "Neutral", None, "Gathering Lv1, Farming Lv1"),
    "KendoFrog": ("Croajiro", "#009", "Water", None, "Handiwork Lv1, Transporting Lv1, Watering Lv1"),
    "KendoFrog_Dark": ("Croajiro Noct", "#009B", "Dark", "Water", "Handiwork Lv1, Transporting Lv1, Gathering Lv1"),
    "LeafMomonga": ("Herbil", "#010", "Grass", "Neutral", "Planting Lv1, Gathering Lv1"),
    "Ganesha": ("Teafant", "#011", "Water", None, "Watering Lv1"),
    "PlantSlime": ("Gumoss", "#012", "Grass", "Ground", "Planting Lv1"),
    "PlantSlime_Flower": ("Gumoss (Flower)", "#012", "Grass", "Ground", "Planting Lv1"),
    "SamuraiDog": ("Pupperai", "#013", "Ground", None, "Handiwork Lv1, Mining Lv1"),
    "CloverFairy": ("Clovee", "#014", "Grass", "Neutral", "Planting Lv1, Handiwork Lv1"),
    "Hedgehog": ("Jolthog", "#015", "Electric", None, "Electricity Lv1"),
    "Hedgehog_Ice": ("Jolthog Cryst", "#015B", "Ice", None, "Cooling Lv1"),
    "NegativeKoala": ("Depresso", "#016", "Dark", None, "Handiwork Lv1, Transporting Lv1, Mining Lv1"),
    "Penguin": ("Pengullet", "#017", "Ice", "Water", "Handiwork Lv1, Transporting Lv1, Watering Lv1, Cooling Lv1"),
    "Penguin_Electric": ("Pengullet Lux", "#017B", "Electric", "Water", "Handiwork Lv1, Transporting Lv1, Electricity Lv1"),
    "CaptainPenguin": ("Penking", "#018", "Ice", "Water", "Handiwork Lv2, Transporting Lv2, Watering Lv2, Mining Lv2, Cooling Lv2"),
    "CaptainPenguin_Black": ("Penking Lux", "#018B", "Electric", "Water", "Handiwork Lv2, Transporting Lv2, Electricity Lv2, Mining Lv2"),
    "WizardOwl": ("Hoocrates", "#019", "Dark", None, "Gathering Lv1"),
    "Melpaca": ("Melpaca", "#020", "Neutral", None, "Farming Lv1"),
    "KingAlpaca": ("Kingpaca", "#021", "Neutral", None, "Gathering Lv1"),
    "KingAlpaca_Ice": ("Kingpaca Cryst", "#021B", "Ice", None, "Gathering Lv1, Cooling Lv1"),
    "Daedream": ("Daedream", "#022", "Dark", None, "Handiwork Lv1, Transporting Lv1, Gathering Lv1"),
    "Monkey": ("Tanzee", "#023", "Grass", None, "Planting Lv1, Handiwork Lv1, Lumbering Lv1, Transporting Lv1, Gathering Lv1"),
    "Monkey_Fire": ("Tanzee Ignis", "#023B", "Fire", None, "Kindling Lv1, Handiwork Lv1, Lumbering Lv1, Transporting Lv1"),
    "NightFox": ("Nox", "#024", "Dark", None, "Gathering Lv1"),
    "LavaGirl": ("Flambelle", "#025", "Fire", None, "Kindling Lv1, Handiwork Lv1, Transporting Lv1, Farming Lv1"),
    "FlameBambi": ("Rooby", "#026", "Fire", None, "Kindling Lv1"),
    "Bastet": ("Mau", "#027", "Dark", None, "Farming Lv1"),
    "Bastet_Ice": ("Mau Cryst", "#027B", "Ice", None, "Cooling Lv1, Farming Lv1"),
    "Boar": ("Rushoar", "#028", "Ground", None, "Mining Lv1"),
    "Kitsunebi": ("Foxparks", "#029", "Fire", None, "Kindling Lv1"),
    "Kitsunebi_Ice": ("Foxparks Cryst", "#029B", "Ice", None, "Cooling Lv1"),
    "NegativeOctopus": ("Killamari", "#030", "Dark", "Water", "Transporting Lv2, Gathering Lv1"),
    "NegativeOctopus_Neutral": ("Killamari Primo", "#030B", "Neutral", "Water", "Transporting Lv2, Gathering Lv1"),
    "CuteMole": ("Fuddler", "#031", "Ground", None, "Handiwork Lv1, Transporting Lv1, Mining Lv1"),
    "Deer": ("Eikthyrdeer", "#032", "Neutral", None, "Lumbering Lv2"),
    "Deer_Ground": ("Eikthyrdeer Terra", "#032B", "Ground", None, "Lumbering Lv2"),
    "Garm": ("Direhowl", "#033", "Neutral", None, "Gathering Lv1"),
    "BerryGoat": ("Caprity", "#034", "Grass", None, "Planting Lv2, Farming Lv1"),
    "BerryGoat_Dark": ("Caprity Noct", "#034B", "Dark", None, "Gathering Lv2, Farming Lv1"),
    "Swee": ("Swee", "#035", "Ice", None, "Gathering Lv1, Cooling Lv1"),
    "Sweepa": ("Sweepa", "#036", "Ice", None, "Gathering Lv2, Cooling Lv2"),
    "TentacleTurtle": ("Turtacle", "#037", "Water", None, "Watering Lv1, Farming Lv1"),
    "TentacleTurtle_Ground": ("Turtacle Terra", "#037B", "Ground", "Water", "Mining Lv1, Watering Lv1"),
    "WindChimes": ("Hangyu", "#038", "Ground", None, "Handiwork Lv1, Transporting Lv2, Gathering Lv1"),
    "WindChimes_Ice": ("Hangyu Cryst", "#038B", "Ice", None, "Handiwork Lv1, Transporting Lv2, Cooling Lv1"),
    "SweetsSheep": ("Woolipop", "#039", "Neutral", None, "Farming Lv1"),
    "SweetsSheep_Ground": ("Woolipop Terra", "#039B", "Ground", None, "Mining Lv1, Farming Lv1"),
    "CowPal": ("Mozzarina", "#040", "Neutral", None, "Farming Lv1"),
    "BlueDragon": ("Chillet", "#041", "Dragon", "Water", "Gathering Lv1, Cooling Lv1"),
    "BlueDragon_Ice": ("Chillet Ignis", "#041B", "Dragon", "Ice", "Kindling Lv1, Gathering Lv1"),
    "ElecCat": ("Sparkit", "#042", "Electric", None, "Handiwork Lv1, Transporting Lv1, Electricity Lv1"),
    "Kelpie": ("Dumud", "#043", "Water", None, "Watering Lv1, Mining Lv2, Farming Lv1"),
    "Kelpie_Fire": ("Kelpsea Ignis", "#043B", "Fire", None, "Kindling Lv1, Farming Lv1"),
    "PinkRabbit": ("Ribbuny", "#044", "Neutral", None, "Handiwork Lv1, Transporting Lv1, Gathering Lv1"),
    "PinkRabbit_Grass": ("Ribbuny Botan", "#044B", "Grass", None, "Planting Lv1, Handiwork Lv1, Gathering Lv1"),
    "JellyfishFairy": ("Jelliette", "#045", "Water", None, "Watering Lv2"),
    "JellyfishGhost": ("Jellroy", "#046", "Dark", "Water", "Gathering Lv1, Watering Lv1"),
    "ClioneTwins": ("Amione", "#047", "Water", None, "Watering Lv2, Medicine Lv1"),
    "OctopusGirl": ("Gloopie", "#048", "Dark", "Water", "Watering Lv1, Transporting Lv1"),
    "OctopusGirl_Neutral": ("Gloopie Primo", "#048B", "Neutral", "Water", "Watering Lv1, Transporting Lv1"),
    "Eagle": ("Galeclaw", "#049", "Neutral", None, "Gathering Lv1"),
    "GhostBlackCat": ("Wispaw", "#050", "Dark", None, "Gathering Lv1"),
    "HawkBird": ("Nitewing", "#051", "Neutral", None, "Gathering Lv2"),
    "CatBat": ("Tombat", "#052", "Dark", None, "Transporting Lv2, Mining Lv2, Gathering Lv2"),
    "ColorfulBird": ("Tocotoco", "#053", "Neutral", None, "Gathering Lv1"),
    "Kirin": ("Univolt", "#054", "Electric", None, "Lumbering Lv1, Electricity Lv2"),
    "Kirin_Ice": ("Univolt Cryst", "#054B", "Ice", None, "Lumbering Lv1, Cooling Lv2"),
    "SharkKid": ("Gobfin", "#055", "Water", None, "Handiwork Lv1, Transporting Lv1, Watering Lv2"),
    "SharkKid_Fire": ("Gobfin Ignis", "#055B", "Fire", None, "Kindling Lv2, Handiwork Lv1, Transporting Lv1"),
    "Werewolf": ("Loupmoon", "#056", "Dark", None, "Handiwork Lv2"),
    "Werewolf_Ice": ("Loupmoon Cryst", "#056B", "Ice", None, "Handiwork Lv2, Cooling Lv1"),
    "DarkCrow": ("Cawgnito", "#057", "Dark", None, "Lumbering Lv1"),
    "FlameBuffalo": ("Arsox", "#058", "Fire", None, "Kindling Lv2, Lumbering Lv1"),
    "FluffyBird": ("Muffly", "#059", "Ice", None, "Cooling Lv1, Gathering Lv1"),
    "LittleBriarRose": ("Bristla", "#060", "Grass", None, "Planting Lv1, Handiwork Lv1, Medicine Lv2, Transporting Lv1, Gathering Lv1"),
    "CuteButterfly": ("Cinnamoth", "#061", "Grass", None, "Planting Lv2, Medicine Lv1"),
    "ElecPomeranian": ("Puffolt", "#062", "Electric", None, "Electricity Lv1"),
    "FairyDragon": ("Elphidran", "#063", "Dragon", None, "Lumbering Lv2"),
    "FairyDragon_Water": ("Elphidran Aqua", "#063B", "Dragon", "Water", "Watering Lv3, Lumbering Lv2"),
    "BirdDragon": ("Vanwyrm", "#064", "Dark", "Fire", "Kindling Lv2, Transporting Lv3"),
    "BirdDragon_Ice": ("Vanwyrm Cryst", "#064B", "Dark", "Ice", "Cooling Lv2, Transporting Lv3"),
    "CatVampire": ("Felbat", "#065", "Dark", None, "Medicine Lv3"),
    "VioletFairy": ("Vaelet", "#066", "Grass", None, "Planting Lv2, Handiwork Lv2, Medicine Lv3, Transporting Lv1, Gathering Lv2"),
    "SoldierBee": ("Beegarde", "#067", "Grass", None, "Planting Lv1, Handiwork Lv1, Lumbering Lv1, Medicine Lv1, Transporting Lv2, Gathering Lv1, Farming Lv1"),
    "QueenBee": ("Elizabee", "#068", "Grass", None, "Planting Lv2, Handiwork Lv2, Lumbering Lv1, Gathering Lv2"),
    "PinkLizard": ("Lovander", "#069", "Dark", None, "Handiwork Lv2, Medicine Lv2, Transporting Lv2, Mining Lv1"),
    "NaughtyCat": ("Grintale", "#070", "Neutral", None, "Gathering Lv2"),
    "PurpleSpider": ("Tarantriss", "#071", "Dark", None, "Handiwork Lv1, Gathering Lv1"),
    "IceSeal": ("Polapup", "#072", "Ice", "Water", "Cooling Lv2, Watering Lv1"),
    "IceSeal_Ground": ("Polapup Terra", "#072B", "Ground", "Ice", "Mining Lv2, Cooling Lv1"),
    "LizardMan": ("Leezpunk", "#073", "Dark", None, "Handiwork Lv1, Transporting Lv1, Gathering Lv1"),
    "LizardMan_Fire": ("Leezpunk Ignis", "#073B", "Fire", None, "Kindling Lv1, Handiwork Lv1, Transporting Lv1, Gathering Lv1"),
    "Gorilla": ("Mossanda", "#074", "Neutral", None, "Planting Lv2, Handiwork Lv2, Lumbering Lv2, Transporting Lv3"),
    "Gorirat Terra": ("Gorirat Terra", "#074B", "Ground", None, "Handiwork Lv2, Transporting Lv3, Mining Lv2"),
    "Surfent": ("Surfent", "#075", "Water", None, "Watering Lv2"),
    "Surfent Terra": ("Surfent Terra", "#075B", "Ground", None, "Gathering Lv1"),
    "RobinHood": ("Robinquill", "#076", "Grass", None, "Planting Lv1, Handiwork Lv2, Lumbering Lv1, Medicine Lv1, Transporting Lv2, Gathering Lv2"),
    "RobinHood_Ground": ("Robinquill Terra", "#076B", "Grass", "Ground", "Handiwork Lv2, Lumbering Lv1, Medicine Lv1, Transporting Lv2, Gathering Lv2"),
    "FlowerRabbit": ("Flopie", "#077", "Grass", None, "Planting Lv1, Handiwork Lv1, Medicine Lv1, Transporting Lv1, Gathering Lv1"),
    "FoxMage": ("Wixen", "#078", "Fire", None, "Kindling Lv2, Handiwork Lv3, Transporting Lv2"),
    "FoxMage_Dark": ("Wixen Noct", "#078B", "Dark", "Fire", "Handiwork Lv3, Transporting Lv2, Gathering Lv1"),
    "CatMage": ("Katress", "#079", "Dark", None, "Handiwork Lv2, Medicine Lv2, Transporting Lv2"),
    "CatMage_Fire": ("Katress Ignis", "#079B", "Dark", "Fire", "Kindling Lv2, Handiwork Lv2, Transporting Lv2"),
    "HadesBird": ("Helzephyr", "#080", "Dark", None, "Transporting Lv3"),
    "HadesBird_Electric": ("Helzephyr Lux", "#080B", "Dark", "Electric", "Transporting Lv3, Electricity Lv2"),
    "GrassMinotaur": ("Elgrove", "#081", "Grass", None, "Planting Lv1, Lumbering Lv2"),
    "GrassMinotaur_Ice": ("Elgrove Cryst", "#081B", "Ice", None, "Lumbering Lv2, Cooling Lv1"),
    "Mutant": ("Lunaris", "#082", "Neutral", None, "Handiwork Lv3, Transporting Lv1, Gathering Lv1"),
    "FengyunDeeper": ("Fenglope", "#083", "Neutral", None, "Lumbering Lv2"),
    "FengyunDeeper_Electric": ("Fenglope Lux", "#083B", "Electric", None, "Lumbering Lv2, Electricity Lv1"),
    "FlowerDinosaur": ("Dinossom", "#084", "Dragon", "Grass", "Planting Lv2, Lumbering Lv2"),
    "FlowerDinosaur_Electric": ("Dinossom Lux", "#084B", "Dragon", "Electric", "Lumbering Lv2, Electricity Lv2"),
    "Ronin": ("Bushi", "#085", "Fire", None, "Kindling Lv2, Handiwork Lv1, Lumbering Lv3, Transporting Lv2, Gathering Lv1"),
    "Ronin_Dark": ("Bushi Noct", "#085B", "Dark", "Fire", "Handiwork Lv1, Lumbering Lv3, Transporting Lv2, Gathering Lv1"),
    "IceCrocodile": ("Munchill", "#086", "Ice", "Water", "Cooling Lv2, Mining Lv1"),
    "GrassMammoth": ("Mammorest", "#087", "Grass", "Ground", "Planting Lv2, Lumbering Lv2, Mining Lv2"),
    "GrassMammoth_Ice": ("Mammorest Cryst", "#087B", "Ground", "Ice", "Cooling Lv2, Lumbering Lv2, Mining Lv2"),
    "StuffedShark": ("Finsider", "#088", "Water", None, "Watering Lv2"),
    "StuffedShark_Fire": ("Finsider Ignis", "#088B", "Fire", "Water", "Kindling Lv2, Watering Lv1"),
    "FlowerDoll": ("Petallia", "#089", "Grass", None, "Planting Lv3, Handiwork Lv2, Medicine Lv2, Transporting Lv1, Gathering Lv2"),
    "FlowerDoll_Fire": ("Petallia Ignis", "#089B", "Fire", "Grass", "Kindling Lv3, Handiwork Lv2, Medicine Lv2, Transporting Lv1"),
    "PandaGirl": ("Leafan", "#090", "Grass", None, "Planting Lv2, Handiwork Lv1"),
    "Baphomet": ("Incineram", "#091", "Dark", "Fire", "Kindling Lv1, Handiwork Lv2, Transporting Lv2, Mining Lv1"),
    "Baphomet_Dark": ("Incineram Noct", "#091B", "Dark", None, "Handiwork Lv2, Transporting Lv2, Mining Lv1"),
    "RaijinDaughter": ("Dazzi", "#092", "Electric", None, "Handiwork Lv1, Transporting Lv1, Electricity Lv1"),
    "RaijinDaughter_Water": ("Dazzi Noct", "#092B", "Dark", "Electric", "Handiwork Lv1, Transporting Lv1, Electricity Lv1"),
    "FireKirin": ("Pyrin", "#093", "Fire", None, "Kindling Lv2, Lumbering Lv1"),
    "FireKirin_Dark": ("Pyrin Noct", "#093B", "Dark", "Fire", "Kindling Lv2, Lumbering Lv1"),
    "LazyDragon": ("Relaxaurus", "#094", "Dragon", "Water", "Transporting Lv1, Watering Lv2"),
    "LazyDragon_Electric": ("Relaxaurus Lux", "#094B", "Dragon", "Electric", "Transporting Lv1, Electricity Lv3"),
    "IceFox": ("Foxcicle", "#095", "Ice", None, "Cooling Lv2"),
    "ThunderBird": ("Beakon", "#096", "Electric", None, "Transporting Lv3, Electricity Lv2, Gathering Lv1"),
    "ThunderBird_Ice": ("Beakon Cryst", "#096B", "Ice", None, "Transporting Lv3, Cooling Lv2, Gathering Lv1"),
    "GhostAnglerfish": ("Ghangler", "#097", "Dark", "Water", "Watering Lv2"),
    "GhostAnglerfish_Fire": ("Ghangler Ignis", "#097B", "Fire", "Water", "Kindling Lv2, Watering Lv1"),
    "ThunderDog": ("Rayhound", "#098", "Electric", None, "Electricity Lv2"),
    "ThunderDog_Ice": ("Rayhound Cryst", "#098B", "Ice", None, "Cooling Lv2"),
    "DarkScorpion": ("Menasting", "#099", "Dark", "Ground", "Lumbering Lv2, Mining Lv3"),
    "DarkScorpion_Ground": ("Menasting Terra", "#099B", "Ground", None, "Lumbering Lv2, Mining Lv3"),
    "CactusDoll": ("Needoll", "#100", "Grass", None, "Planting Lv1, Handiwork Lv1"),
    "CactusDoll_Dark": ("Needoll Noct", "#100B", "Dark", "Grass", "Gathering Lv1, Handiwork Lv1"),
    "IceDeer": ("Reindrix", "#101", "Ice", None, "Cooling Lv2, Lumbering Lv1"),
    "GrassPanda": ("Mossanda", "#102", "Grass", None, "Planting Lv2, Handiwork Lv2, Lumbering Lv2, Transporting Lv3"),
    "GrassPanda_Electric": ("Mossanda Lux", "#102B", "Electric", None, "Handiwork Lv2, Lumbering Lv2, Transporting Lv3, Electricity Lv2"),
    "WeaselDragon": ("Chillet", "#103", "Dragon", "Ice", "Gathering Lv1, Cooling Lv1"),
    "WeaselDragon_Fire": ("Chillet Ignis", "#103B", "Dragon", "Fire", "Kindling Lv1, Gathering Lv1"),
    "RedArmorBird": ("Ragnahawk", "#104", "Fire", None, "Kindling Lv3, Transporting Lv3"),
    "VolcanoDragon": ("Moldron", "#105", "Fire", "Ground", "Kindling Lv3, Mining Lv3"),
    "VolcanoDragon_Ice": ("Moldron Cryst", "#105B", "Ground", "Ice", "Cooling Lv3, Mining Lv3"),
    "TropicalOstrich": ("Palumba", "#106", "Grass", None, "Planting Lv2, Gathering Lv1"),
    "DrillGame": ("Digtoise", "#107", "Ground", None, "Mining Lv3"),
    "SakuraSaurus": ("Broncherry", "#108", "Grass", None, "Planting Lv3"),
    "SakuraSaurus_Water": ("Broncherry Aqua", "#108B", "Grass", "Water", "Planting Lv3, Watering Lv3"),
    "LazyCatfish": ("Dumud", "#109", "Ground", "Water", "Watering Lv1, Mining Lv2, Farming Lv1"),
    "LazyCatfish_Gold": ("Dumud Gild", "#109B", "Ground", "Water", "Watering Lv1, Mining Lv3"),
    "Plesiosaur": ("Braloha", "#110", "Grass", "Ground", "Planting Lv2, Watering Lv2"),
    "AmaterasuWolf": ("Kitsun", "#111", "Fire", None, "Kindling Lv2"),
    "AmaterasuWolf_Dark": ("Kitsun Noct", "#111B", "Dark", None, "Gathering Lv2"),
    "Manticore": ("Blazehowl", "#112", "Fire", None, "Kindling Lv3, Lumbering Lv2"),
    "Manticore_Dark": ("Blazehowl Noct", "#112B", "Dark", "Fire", "Kindling Lv3, Lumbering Lv2"),
    "HerculesBeetle": ("Warsect", "#113", "Grass", "Ground", "Planting Lv1, Handiwork Lv1, Lumbering Lv3, Transporting Lv3"),
    "HerculesBeetle_Ground": ("Warsect Terra", "#113B", "Ground", None, "Handiwork Lv1, Lumbering Lv3, Mining Lv3"),
    "SnowPeafowl": ("Frostplume", "#114", "Ice", None, "Cooling Lv2, Gathering Lv1"),
    "DarkFlameFox": ("Majex", "#115", "Dark", "Fire", "Kindling Lv2, Gathering Lv1"),
    "WhiteMoth": ("Sibelyx", "#116", "Ice", None, "Medicine Lv2, Cooling Lv2, Farming Lv1"),
    "WhiteMoth_Neutral": ("Sibelyx Primo", "#116B", "Neutral", None, "Medicine Lv2, Farming Lv1"),
    "GhostBeast": ("Tombat", "#117", "Dark", None, "Transporting Lv2, Mining Lv2, Gathering Lv2"),
    "MushroomDragon": ("Shroomer", "#118", "Grass", None, "Planting Lv2, Handiwork Lv1, Lumbering Lv2, Gathering Lv2"),
    "MushroomDragon_Dark": ("Shroomer Noct", "#118B", "Dark", "Grass", "Handiwork Lv1, Lumbering Lv2, Gathering Lv2"),
    "IceWitch": ("Icelyn", "#119", "Ice", None, "Cooling Lv3, Medicine Lv2"),
    "MummyPal": ("Gildra", "#120", "Dark", "Ground", "Mining Lv2"),
    "Umihebi": ("Jormuntide", "#121", "Dragon", "Water", "Watering Lv4"),
    "Umihebi_Fire": ("Jormuntide Ignis", "#121B", "Dragon", "Fire", "Kindling Lv4"),
    "Suzaku": ("Suzaku", "#122", "Fire", None, "Kindling Lv3"),
    "Suzaku_Water": ("Suzaku Aqua", "#122B", "Water", None, "Watering Lv3"),
    "FeatherOstrich": ("Dazemu", "#123", "Ground", None, "Gathering Lv2"),
    "SkyDragon": ("Quivern", "#124", "Dragon", None, "Handiwork Lv1, Transporting Lv3, Mining Lv2, Gathering Lv2"),
    "SkyDragon_Grass": ("Quivern Botan", "#124B", "Dragon", "Grass", "Planting Lv2, Handiwork Lv1, Transporting Lv3, Gathering Lv2"),
    "LeafPrincess": ("Lullu", "#125", "Grass", None, "Planting Lv2, Handiwork Lv1"),
    "SmallArmadillo": ("Kikit", "#126", "Ground", None, "Mining Lv1"),
    "GuardianDog": ("Yakumo", "#127", "Neutral", None, "Gathering Lv2"),
    "SwordCutlassfish": ("Skutlass", "#128", "Water", None, "Watering Lv2"),
    "SwordCutlassfish_Fire": ("Skutlass Ignis", "#128B", "Fire", "Water", "Kindling Lv2, Watering Lv1"),
    "VolcanicMonster": ("Reptyro", "#129", "Fire", "Ground", "Kindling Lv3, Mining Lv3"),
    "VolcanicMonster_Ice": ("Reptyro Cryst", "#129B", "Ground", "Ice", "Cooling Lv3, Mining Lv3"),
    "NightBlueHorse": ("Starryon", "#130", "Dark", None, "Gathering Lv2"),
    "NightBlueHorse_Neutral": ("Starryon Primo", "#130B", "Neutral", None, "Gathering Lv2"),
    "RockBeast": ("Pierdon", "#131", "Ground", None, "Mining Lv3"),
    "RockBeast_Ice": ("Pierdon Cryst", "#131B", "Ice", None, "Mining Lv3, Cooling Lv2"),
    "WhiteTiger": ("Cryolinx", "#132", "Ice", None, "Handiwork Lv1, Lumbering Lv2, Cooling Lv3"),
    "WhiteTiger_Ground": ("Cryolinx Terra", "#132B", "Ground", None, "Handiwork Lv1, Lumbering Lv2, Mining Lv3"),
    "SmallYeti": ("Snugloo", "#133", "Ice", None, "Cooling Lv2, Transporting Lv1"),
    "Yeti": ("Wumpo", "#134", "Ice", None, "Handiwork Lv2, Lumbering Lv3, Transporting Lv4, Cooling Lv2"),
    "Yeti_Grass": ("Wumpo Botan", "#134B", "Grass", None, "Planting Lv1, Handiwork Lv2, Lumbering Lv3, Transporting Lv4"),
    "Sootseer": ("Sootseer", "#135", "Dark", "Fire", "Kindling Lv2, Gathering Lv1"),
    "VenusFlytrap": ("Carnibora", "#136", "Grass", None, "Planting Lv2, Gathering Lv2"),
    "KingBahamut": ("Blazamut", "#137", "Fire", None, "Kindling Lv3, Mining Lv4"),
    "KingBahamut_Dragon": ("Blazamut Ryu", "#137B", "Dragon", "Fire", "Kindling Lv4, Mining Lv4"),
    "GrassGolem": ("Dualith", "#138", "Grass", "Ground", "Lumbering Lv3, Mining Lv3"),
    "GrassGolem_Dark": ("Dualith Noct", "#138B", "Dark", "Ground", "Mining Lv3, Transporting Lv2"),
    "Anubis": ("Anubis", "#139", "Ground", None, "Handiwork Lv4, Transporting Lv2, Mining Lv3"),
    "Sekhmet": ("Sekhmet", "#140", "Ground", None, "Handiwork Lv3, Mining Lv3"),
    "ScorpionMan": ("Prixter", "#141", "Dark", "Ground", "Mining Lv3"),
    "ScorpionMan_Electric": ("Prixter Lux", "#141B", "Electric", "Ground", "Mining Lv3, Electricity Lv2"),
    "CubeTurtle": ("Tetroise", "#142", "Ground", None, "Mining Lv2"),
    "CubeTurtle_Neutral": ("Tetroise Primo", "#142B", "Neutral", None, "Mining Lv2"),
    "BadCatgirl": ("Nyafia", "#143", "Dark", None, "Handiwork Lv2, Gathering Lv1"),
    "MimicDog": ("Mimog", "#144", "Neutral", None, "Gathering Lv1"),
    "DarkAlien": ("Xenovader", "#145", "Dark", None, "Lumbering Lv2, Transporting Lv1"),
    "WhiteAlienDragon": ("Xenogard", "#146", "Dragon", None, "Mining Lv3"),
    "BlueberryFairy": ("Prunelia", "#147", "Dark", "Grass", "Planting Lv2, Medicine Lv2"),
    "GhostRabbit": ("Nitemary", "#148", "Dark", None, "Gathering Lv2"),
    "GhostRabbit_Grass": ("Nitemary Botan", "#148B", "Grass", None, "Planting Lv2, Gathering Lv2"),
    "BlackPuppy": ("Smokie", "#149", "Dark", None, "Gathering Lv1"),
    "BlackPuppy_Ice": ("Smokie Cryst", "#149B", "Dark", "Ice", "Cooling Lv1, Gathering Lv1"),
    "MysteryMask": ("Omascul", "#150", "Dark", None, "Gathering Lv2"),
    "IceNarwhal": ("Whalaska", "#151", "Ice", "Water", "Watering Lv3, Cooling Lv3"),
    "IceNarwhal_Fire": ("Whalaska Ignis", "#151B", "Fire", "Ice", "Kindling Lv3, Cooling Lv3"),
    "GrassRabbitMan": ("Verdash", "#152", "Grass", None, "Planting Lv2, Handiwork Lv3, Lumbering Lv2, Transporting Lv2, Gathering Lv3"),
    "GrimGirl": ("Splatterina", "#153", "Dark", None, "Handiwork Lv3, Transporting Lv2"),
    "GoldenHorse": ("Gildane", "#154", "Ground", None, "Gathering Lv2"),
    "SifuDog": ("Dogen", "#155", "Neutral", None, "Handiwork Lv2, Transporting Lv2"),
    "SumoDog": ("Bulldosu", "#156", "Ground", None, "Mining Lv3, Transporting Lv2"),
    "WhiteDeer": ("Celesdir", "#157", "Neutral", None, "Lumbering Lv3"),
    "WhiteDeer_Dark": ("Celesdir Noct", "#157B", "Dark", None, "Lumbering Lv3"),
    "BlackMetalDragon": ("Astegon", "#158", "Dark", "Dragon", "Handiwork Lv1, Mining Lv4"),
    "WingGolem": ("Knocklem", "#159", "Ground", None, "Handiwork Lv3, Transporting Lv3, Mining Lv3"),
    "WingGolem_Fire": ("Knocklem Ignis", "#159B", "Fire", None, "Kindling Lv3, Handiwork Lv3, Transporting Lv3"),
    "WhiteShieldDragon": ("Silvegis", "#160", "Dragon", None, "Lumbering Lv2, Mining Lv2"),
    "BlueThunderHorse": ("Azurmane", "#161", "Electric", None, "Electricity Lv3"),
    "LongCat": ("Valentail", "#162", "Neutral", None, "Gathering Lv2"),
    "ElecSnail": ("Snock", "#163", "Electric", None, "Electricity Lv1, Mining Lv1"),
    "ElecSnail_Ground": ("Snock Lux", "#163B", "Electric", "Ground", "Mining Lv2, Electricity Lv1"),
    "DandelionGirl": ("Souffline", "#164", "Grass", None, "Planting Lv1, Gathering Lv2"),
    "BrownRabbit": ("Lapiron", "#165", "Ground", None, "Handiwork Lv1, Mining Lv2"),
    "HoodGhost": ("Hoodle", "#166", "Dark", None, "Gathering Lv1"),
    "ElecLizard": ("Slowatt", "#167", "Electric", None, "Electricity Lv1"),
    "OniGhostGirl": ("Bakemi", "#168", "Dark", None, "Handiwork Lv2, Gathering Lv2"),
    "KingSunfish": ("Solmora", "#169", "Water", None, "Watering Lv3"),
    "KingSunfish_Thunder": ("Solmora Lux", "#169B", "Electric", "Water", "Watering Lv2, Electricity Lv2"),
    "SleeveRabbit": ("Lapure", "#170", "Neutral", None, "Handiwork Lv2"),
    "GhostDragon": ("Eidrolon", "#171", "Dark", "Dragon", "Mining Lv3"),
    "GhostDragon_Fire": ("Eidrolon Ignis", "#171B", "Dragon", "Fire", "Kindling Lv3, Mining Lv3"),
    "ThunderFluffyBird": ("Dynamoff", "#172", "Electric", None, "Electricity Lv2, Gathering Lv1"),
    "RedFlowerBird": ("Tropicaw", "#173", "Grass", None, "Planting Lv2, Gathering Lv2"),
    "FoxExorcist": ("Flaracle", "#174", "Fire", None, "Kindling Lv3, Handiwork Lv2"),
    "LotusDragon": ("Ophydia", "#175", "Grass", "Water", "Planting Lv2, Watering Lv3"),
    "ClownRabbit": ("Dupin", "#176", "Fire", None, "Kindling Lv2, Handiwork Lv2"),
    "ThiefBird": ("Roujay", "#177", "Dark", None, "Gathering Lv2"),
    "SnakeGirl": ("Venusa", "#178", "Dark", "Grass", "Planting Lv2, Medicine Lv2"),
    "MushroomLady": ("Mycora", "#179", "Grass", None, "Planting Lv2, Medicine Lv2"),
    "LanternButler": ("Loomen", "#180", "Dark", "Fire", "Kindling Lv2, Handiwork Lv2"),
    "MoonChild": ("Wistella", "#181", "Dark", None, "Handiwork Lv2, Gathering Lv2"),
    "MonochromeQueen": ("Solenne", "#182", "Dark", "Neutral", "Handiwork Lv3, Gathering Lv2"),
    "KabukiMan": ("Renjishi", "#183", "Fire", None, "Kindling Lv3, Handiwork Lv2"),
    "DomeArmorDragon": ("Aegidron", "#184", "Dragon", "Ground", "Mining Lv3"),
    "ElecPanda": ("Grizzbolt", "#185", "Electric", None, "Handiwork Lv2, Lumbering Lv2, Transporting Lv3, Electricity Lv3"),
    "LilyQueen": ("Lyleen", "#186", "Grass", None, "Planting Lv4, Handiwork Lv3, Medicine Lv3, Gathering Lv2"),
    "LilyQueen_Dark": ("LilyQueen Noct", "#186B", "Dark", None, "Handiwork Lv3, Medicine Lv3, Gathering Lv2"),
    "ThunderDragonMan": ("Orserk", "#187", "Dragon", "Electric", "Transporting Lv2, Electricity Lv4"),
    "Horus": ("Faleris", "#188", "Fire", None, "Kindling Lv3, Transporting Lv3"),
    "Horus_Water": ("Faleris Aqua", "#188B", "Water", None, "Watering Lv3, Transporting Lv3"),
    "Shadowbeak": ("Shadowbeak", "#189", "Dark", None, "Gathering Lv1"),
    "MoonQueen": ("Selyne", "#190", "Dark", "Neutral", "Handiwork Lv3, Transporting Lv3, Medicine Lv3"),
    "SnowTigerBeastman": ("Bastigor", "#191", "Ice", None, "Lumbering Lv3, Cooling Lv3"),
    "BlueSkyDragon": ("Shaolong", "#192", "Dragon", "Water", "Watering Lv3"),
    "Mothman": ("Silvance", "#193", "Grass", None, "Planting Lv3, Handiwork Lv2"),
    "FlowerPrince": ("Dandilord", "#194", "Dark", "Grass", "Planting Lv3, Handiwork Lv3"),
    "NightLady": ("Bellanoir", "#195", "Dark", None, "Handiwork Lv2, Medicine Lv4, Transporting Lv2"),
    "NightLady_Dark": ("Bellanoir Libero", "#195B", "Dark", None, "Handiwork Lv3, Medicine Lv4, Transporting Lv3"),
    "DarkMechaDragon": ("Xenolord", "#196", "Dark", "Dragon", "Mining Lv3, Transporting Lv2"),
    "LegendDeer": ("Hartalis", "#197", "Neutral", None, "Lumbering Lv3, Mining Lv2"),
    "SaintCentaur": ("Paladius", "#198", "Neutral", None, "Lumbering Lv2, Mining Lv2"),
    "BlackCentaur": ("Necromus", "#199", "Dark", None, "Lumbering Lv2, Mining Lv2"),
    "IceHorse": ("Frostallion", "#200", "Ice", None, "Cooling Lv4"),
    "IceHorse_Dark": ("Frostallion Noct", "#200B", "Dark", None, "Gathering Lv4"),
    "PoseidonOrca": ("Neptilius", "#201", "Water", None, "Watering Lv4"),
    "JetDragon": ("Jetragon", "#202", "Dragon", None, "Gathering Lv3"),
    "KingWhale": ("Panthalus", "#203", "Water", None, "Watering Lv4"),
    "WorldTreeDragon": ("Astralyn", "#204", "Neutral", None, "Planting Lv3, Handiwork Lv3, Lumbering Lv3, Mining Lv3"),
}


def get_pal_info(internal_id):
    if internal_id in PAL_MASTER_MAP:
        return PAL_MASTER_MAP[internal_id]

    clean_id = internal_id.replace("BOSS_", "").replace("Raid_", "").replace("NPC_", "").replace("SUMMON_", "")
    if clean_id in PAL_MASTER_MAP:
        return PAL_MASTER_MAP[clean_id]

    formatted_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", clean_id).replace("_", " ").title()
    return formatted_name, "-", "Neutral", None, "-"


def get_suitability_levels(base_work_str: str, chunk_bytes: bytes) -> str:
    """Returns compact non-zero work suitabilities string (e.g. '🔨 1, 📦 1, 🐣 1')."""
    items = []
    for col_name, aliases in WORK_SUITABILITY_ORDER:
        val = 0
        for alias in aliases:
            m = re.search(rf"{alias}\s*Lv(\d+)", base_work_str, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                break
        for alias in aliases:
            idx = chunk_bytes.find(alias.encode("ascii"))
            if idx != -1:
                sub = chunk_bytes[idx:idx + 35]
                for b in sub[len(alias):]:
                    if 1 <= b <= 5:
                        val = max(val, b)
                        break
        if val > 0:
            symbol = WORK_EMOJI_MAP.get(col_name, "★")
            items.append(f"{symbol} {val}")
    return ", ".join(items) if items else "-"



def find_target_save():
    if not SAVE_DIR.is_dir():
        print(f"[!] Save directory does not exist: {SAVE_DIR}")
        return None

    all_level_saves = glob.glob(str(SAVE_DIR / "**" / "Level.sav"), recursive=True)
    if not all_level_saves:
        print("[!] No Level.sav files found in SaveGames path.")
        return None

    live_saves = [s for s in all_level_saves if "\\backup\\" not in s and "/backup/" not in s]
    if not live_saves:
        live_saves = all_level_saves

    if PINNED_WORLD_SAVE_GUID:
        for s in live_saves:
            if PINNED_WORLD_SAVE_GUID.lower() in s.lower():
                return s

    live_saves.sort(key=lambda s: (os.path.getsize(s), os.path.getmtime(s)), reverse=True)
    return live_saves[0]


def decode_palworld_save(raw_bytes: bytes) -> bytes:
    """Decodes Palworld compressed Level.sav using palooz / ooz (Oodle PlM/PlM1) or standard zlib (PlZ)."""
    # 1. Direct uncompressed GVAS stream
    if raw_bytes.startswith(b"GVAS"):
        print(f"[OK] Direct uncompressed GVAS stream ({len(raw_bytes) // 1024 // 1024}MB).")
        return raw_bytes

    if len(raw_bytes) > 12:
        uncompressed_len = struct.unpack("<I", raw_bytes[0:4])[0]
        compressed_len = struct.unpack("<I", raw_bytes[4:8])[0]
        magic = raw_bytes[8:12]
        print(f"[*] PlM/PlZ Container: target={uncompressed_len // 1024 // 1024}MB, compressed={compressed_len // 1024 // 1024}MB, magic={magic}")

        payload = raw_bytes[12: 12 + compressed_len] if compressed_len > 0 and (12 + compressed_len) <= len(raw_bytes) else raw_bytes[12:]

        # Oodle (PlM / PlM1) decompression via palooz or ooz
        if b"PlM" in magic:
            decomp = None
            try:
                import palooz  # type: ignore
                decomp = palooz.decompress(payload, uncompressed_len)
            except Exception:
                try:
                    import ooz  # type: ignore
                    decomp = ooz.decompress(payload, uncompressed_len)
                except Exception as e:
                    print(f"[!] Oodle decompression attempt failed: {e}")

            if decomp and (decomp.startswith(b"GVAS") or b"GVAS" in decomp[:128]):
                g_idx = decomp.find(b"GVAS")
                print(f"[OK] Decompressed PlM/Oodle stream ({len(decomp) // 1024 // 1024}MB)!")
                return decomp[g_idx:]

        # Legacy zlib / double zlib / raw deflate
        for wbits in [-15, 15, 15 + 32]:
            try:
                decompressor = zlib.decompressobj(wbits)
                decomp = decompressor.decompress(payload)
                if decomp.startswith(b"GVAS") or b"GVAS" in decomp[:128]:
                    g_idx = decomp.find(b"GVAS")
                    print(f"[OK] Decompressed raw deflate stream (wbits={wbits}) -> {len(decomp) // 1024 // 1024}MB!")
                    return decomp[g_idx:]
            except Exception:
                continue

    # 2. Brute-force window search across early offsets
    print("[*] Performing sliding-window decompression search...")
    for offset in range(0, min(64, len(raw_bytes) - 10)):
        for wbits in [-15, 15, 15 + 32]:
            try:
                d = zlib.decompressobj(wbits)
                decomp = d.decompress(raw_bytes[offset:])
                if len(decomp) > 1000000 and (decomp.startswith(b"GVAS") or b"GVAS" in decomp[:128]):
                    g_idx = decomp.find(b"GVAS")
                    print(f"[OK] Decompressed stream found at offset {offset} (wbits={wbits}) -> {len(decomp) // 1024 // 1024}MB!")
                    return decomp[g_idx:]
            except Exception:
                continue

    raise ValueError("Could not decompress Palworld Level.sav. Unsupported container format.")


def extract_byte_prop(prop_name: str, chunk_bytes: bytes):
    """Extracts a ByteProperty uint8 value from Unreal Engine GVAS binary chunk."""
    key = prop_name.encode("ascii") + b"\x00"
    idx = chunk_bytes.find(key)
    if idx != -1:
        sub = chunk_bytes[idx:idx + 80]
        b_idx = sub.find(b"ByteProperty\x00")
        if b_idx != -1:
            n_idx = sub.find(b"None\x00", b_idx)
            if n_idx != -1 and n_idx + 6 < len(sub):
                return sub[n_idx + 6]
    return None


def extract_talent_val(stat_name: str, chunk_bytes: bytes):
    """Extracts IV Talent (0-100) for HP, Shot (Attack), Melee, Defense."""
    target_prop = f"Talent_{stat_name}"
    val = extract_byte_prop(target_prop, chunk_bytes)
    if val is not None and 0 <= val <= 100:
        return val

    # Fallback: Melee and Shot share Attack IV (Talent_Shot) in Palworld
    if stat_name in ("Melee", "Shot"):
        fallback = extract_byte_prop("Talent_Shot", chunk_bytes)
        if fallback is not None and 0 <= fallback <= 100:
            return fallback

    return "-"


def extract_level_val(chunk_bytes: bytes):
    """Extracts Pal Level from ByteProperty."""
    lvl = extract_byte_prop("Level", chunk_bytes)
    if lvl is not None and 1 <= lvl <= 100:
        return lvl
    return 1


PASSIVE_SKILL_NAME_MAP = {
    "PAL_ALLAttack_up2": "Musclehead",
    "PAL_rude": "Ferocious",
    "PAL_CorporateSlave": "Workslave",
    "CraftSpeed_up2": "Artisan",
    "CraftSpeed_up1": "Serious",
    "MoveSpeed_up_2": "Swift",
    "MoveSpeed_up_1": "Runner",
    "MoveSpeed_up_0": "Nimble",
    "Deffence_up2_2": "Burly Body",
    "Deffence_up2": "Burly Body",
    "Deffence_up1": "Hard Skin",
    "Nocturnal": "Nocturnal",
    "Legend": "Legend",
    "Rare": "Lucky",
    "PAL_FullStomach_Down_2": "Diet Lover",
    "PAL_Sanity_Up_1": "Positive Thinker",
    "AutoHPRegeneRate_Passive": "Vanguard",
    "CoolTimeReduction_Up_2": "Demon God",
    "Stamina_Up_2": "Infinite Stamina",
}


def clean_passive_name(p_id: str) -> str:
    """Maps internal Palworld passive skill ID to display name."""
    if not p_id or p_id == "-":
        return "-"
    s_key = p_id.strip()
    if s_key in PASSIVE_SKILL_NAME_MAP:
        return PASSIVE_SKILL_NAME_MAP[s_key]
    if s_key.lower() in PASSIVE_SKILL_NAME_MAP:
        return PASSIVE_SKILL_NAME_MAP[s_key.lower()]

    base_id = s_key.replace("Test_", "").replace("PASSIVE_", "").replace("_PAL", "")
    if base_id in PASSIVE_SKILL_NAME_MAP:
        return PASSIVE_SKILL_NAME_MAP[base_id]
    if base_id.lower() in PASSIVE_SKILL_NAME_MAP:
        return PASSIVE_SKILL_NAME_MAP[base_id.lower()]

    s_lower = s_key.lower()
    if "hatchingspeed" in s_lower:
        return "Philanthropist"
    if "deathadditemdrop" in s_lower:
        return "Abundant Drops"
    if "monsterfarm_1" in s_lower:
        return "Farmhand"
    if "monsterfarm_2" in s_lower:
        return "Ranch Master"

    name = re.sub(r"^(?:PAL_|APSE_|ElementBoost_|ElementResist_)", "", s_key)
    name = re.sub(r"_[0-9]+.*$", "", name)
    return name.replace("_", " ").title()


PAL_UNIQUE_WAZA_NAME_MAP = {
    # Pupperai / SamuraiDog
    "Unique_SamuraiDog_Bite": "Wild Fang",
    "Unique_SamuraiDog_BiteV2": "Double Fang",
    "Unique_SamuraiDog_Bite_V2": "Double Fang",
    "Unique_SamuraiDog_DashSlash": "Iai Slash",
    
    # Direhowl / Garm
    "Unique_Garm_Bite": "Fierce Fang",
    "Unique_Garm_BiteV2": "Fierce Fang II",
    "Unique_Garm_Bite_V2": "Fierce Fang II",

    # Chikipi / ChickenPal
    "Unique_ChickenPal_ChickenPeck": "Chicken Peck",

    # Rushoar / Boar
    "Unique_Boar_Tackle": "Rush",

    # Eikthyrdeer / Deer
    "Unique_Deer_PushupHorn": "Horn Charge",

    # Cattiva / PinkCat
    "Unique_PinkCat_CatPunch": "Cat Punch",

    # Lamball / SheepBall
    "Unique_SheepBall_Roll": "Rolly Polly",

    # Lifmunk / Carbunclo
    "Unique_Carbunclo_SubmachineGun": "Lifmunk Recoil",

    # Foxparks / Kitsunebi
    "Unique_Kitsunebi_FireThorn": "Flame Roar",

    # Fuack / BluePlatypus
    "Unique_BluePlatypus_Toboggan": "Surfing Slam",

    # Jolthog / Hedgehog
    "Unique_Hedgehog_ElecThorn": "Jolt Shock",

    # Pengullet / Penguin
    "Unique_Penguin_Rocket": "Penguin Cannon",

    # Grizzbolt / ElecPanda
    "Unique_ElecPanda_GatlingAttack": "Minigun Barrage",
    "Unique_ElecPanda_ElecScratch": "Lightning Claw",

    # Rayhound / ThunderDog
    "Unique_ThunderDog_Bite": "Wild Fang (Lightning)",
    "Unique_ThunderDog_BiteV2": "Double Fang (Lightning)",
    "Unique_ThunderDog_Ice_Bite": "Wild Fang (Ice)",
    "Unique_ThunderDog_Ice_BiteV2": "Double Fang (Ice)",

    # GuardianDog / BlackPuppy / GoldenHorse / AmaterasuWolf
    "Unique_GuardianDog_Bite": "Wild Fang",
    "Unique_GuardianDog_BiteV2": "Double Fang",
    "Unique_BlackPuppy_Bite": "Dark Fang",
    "Unique_BlackPuppy_BiteV2": "Double Dark Fang",
    "Unique_GoldenHorse_Bite": "Earth Fang",
    "Unique_GoldenHorse_BiteV2": "Double Earth Fang",
    "Unique_AmaterasuWolf_Bite": "Flame Fang",
    "Unique_AmaterasuWolf_BiteV2": "Double Flame Fang",
    "Unique_AmaterasuWolf_Dark_Bite": "Shadow Fang",
    "Unique_AmaterasuWolf_Dark_BiteV2": "Double Shadow Fang",

    # Common Active Move Cleanups
    "AirCanon": "Air Cannon",
    "AirCannon": "Air Cannon",
}


def clean_waza_name(w_id: str) -> str:
    """Maps internal Palworld EPalWazaID to clean English display name."""
    if not w_id or w_id == "-":
        return "-"
    s_key = w_id.strip()

    if s_key in PAL_UNIQUE_WAZA_NAME_MAP:
        return PAL_UNIQUE_WAZA_NAME_MAP[s_key]
    if s_key in ACTIVE_SKILL_NAME_MAP:
        return ACTIVE_SKILL_NAME_MAP[s_key]
    if s_key.lower() in ACTIVE_SKILL_NAME_MAP:
        return ACTIVE_SKILL_NAME_MAP[s_key.lower()]

    base_id = s_key.replace("EPalWazaID::", "").replace("Unique_", "").replace("_PAL", "")
    if base_id in PAL_UNIQUE_WAZA_NAME_MAP:
        return PAL_UNIQUE_WAZA_NAME_MAP[base_id]
    if base_id in ACTIVE_SKILL_NAME_MAP:
        return ACTIVE_SKILL_NAME_MAP[base_id]
    if base_id.lower() in ACTIVE_SKILL_NAME_MAP:
        return ACTIVE_SKILL_NAME_MAP[base_id.lower()]

    name = re.sub(r"^(?:Unique_[A-Za-z0-9]+_)", "", s_key)
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    return name.replace("_", " ").strip()


def extract_passive_skills_list(chunk_bytes: bytes) -> list:
    """Extracts up to 4 passive skills as a list of 4 clean string values."""
    idx = chunk_bytes.find(b"PassiveSkillList\x00")
    if idx == -1:
        return ["-", "-", "-", "-"]

    sub = chunk_bytes[idx:idx + 500]
    n_idx = sub.find(b"NameProperty\x00")
    if n_idx == -1:
        return ["-", "-", "-", "-"]

    post_idx = n_idx + 13 + 1
    if post_idx + 4 > len(sub):
        return ["-", "-", "-", "-"]

    count = struct.unpack("<I", sub[post_idx:post_idx + 4])[0]
    if count == 0 or count > 10:
        return ["-", "-", "-", "-"]

    curr = post_idx + 4
    passives = []
    for _ in range(count):
        if curr + 4 > len(sub):
            break
        s_len = struct.unpack("<I", sub[curr:curr + 4])[0]
        curr += 4
        if curr + s_len > len(sub):
            break
        s_val = sub[curr:curr + s_len - 1].decode("ascii", errors="ignore")
        curr += s_len
        if s_val and s_val != "None":
            passives.append(clean_passive_name(s_val))

    passives = passives[:4]
    while len(passives) < 4:
        passives.append("-")

    return passives


def extract_equipped_active_skills_list(chunk_bytes: bytes) -> list:
    """Extracts up to 3 equipped active skills as a list of 3 clean string values."""
    w_idx = chunk_bytes.find(b"EquipWaza\x00")
    if w_idx == -1:
        return ["-", "-", "-"]

    w_sub = chunk_bytes[w_idx:w_idx + 400]
    w_matches = re.findall(rb"EPalWazaID::([A-Za-z0-9_]+)", w_sub)
    if not w_matches:
        return ["-", "-", "-"]

    skills = [clean_waza_name(w.decode("ascii", errors="ignore")) for w in w_matches[:3]]
    while len(skills) < 3:
        skills.append("-")

    return skills


ACTIVE_SKILL_ELEMENT_MAP = {
    "Fire": ["fire", "flame", "flare", "burn", "ignis", "inferno", "blast", "heat", "scorch", "lava", "pyro", "cinder"],
    "Water": ["water", "hydro", "aqua", "bubble", "splash", "ocean", "tsunami", "river", "sea", "geyser", "stream", "cascade"],
    "Grass": ["grass", "plant", "leaf", "root", "seed", "vine", "botan", "brier", "flower", "bloom", "forest", "spore", "tangle"],
    "Electric": ["elec", "thunder", "spark", "lightning", "voltage", "lux", "bolt", "shock", "plasma", "charge", "static"],
    "Ice": ["ice", "frost", "blizzard", "glacier", "freeze", "icicle", "cryst", "cold", "snow", "hail", "chilling"],
    "Ground": ["ground", "rock", "stone", "mud", "sand", "earth", "terra", "tremor", "quake", "boulder", "dust", "clay"],
    "Dark": ["dark", "shadow", "ghost", "poison", "night", "demon", "apocalypse", "noct", "phantom", "curse", "void", "abyss", "wisp", "gloom", "venom"],
    "Dragon": ["dragon", "commet", "wyrm", "drake", "meteor", "beam", "draco", "scale"],
}

ELEMENT_HEX_MAP = {
    "Neutral": "#5A6577",
    "Fire": "#C5281C",
    "Water": "#0B5394",
    "Grass": "#55A630",
    "Electric": "#F1C40F",
    "Ice": "#74B9FF",
    "Ground": "#784212",
    "Dark": "#4C2E6A",
    "Dragon": "#BA55D3",
}

PASSIVE_HEATMAP_HEX_MAP = {
    -3: "#C0392B",
    -2: "#E74C3C",
    -1: "#F1948A",
     0: "#FFFFFF",
     1: "#C8E6C9",
     2: "#81C784",
     3: "#4CAF50",
     4: "#2E7D32",
     5: "#1B5E20",
}


MOD_HARVESTED_PASSIVES = {}


def harvest_installed_mod_passives():
    """Scans all installed Palworld mod directories (PalSchema / UE4SS / ManagedMods) for modded passives."""
    global MOD_HARVESTED_PASSIVES, PASSIVE_SKILL_NAME_MAP

    possible_mod_roots = [
        r"C:\Program Files (x86)\Steam\steamapps\common\Palworld\Mods\NativeMods\UE4SS\Mods\PalSchema\mods",
        r"C:\Program Files (x86)\Steam\steamapps\common\Palworld\Mods\ManagedMods",
        r"E:\SteamLibrary\steamapps\common\Palworld\Mods\NativeMods\UE4SS\Mods\PalSchema\mods",
        r"E:\SteamLibrary\steamapps\common\Palworld\Mods\ManagedMods",
    ]

    def clean_jsonc(text):
        lines = []
        for line in text.splitlines():
            if line.strip().startswith("//"):
                continue
            lines.append(line)
        cleaned = "\n".join(lines)
        cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
        return cleaned

    for root_dir in possible_mod_roots:
        if not os.path.exists(root_dir):
            continue
        for mdir in os.listdir(root_dir):
            full_m = os.path.join(root_dir, mdir)
            if not os.path.isdir(full_m):
                continue
            
            mod_ranks = {}
            mod_names = {}
            json_files = glob.glob(os.path.join(full_m, '**', '*.json*'), recursive=True)

            for jf in json_files:
                try:
                    with open(jf, 'r', encoding='utf-8-sig', errors='ignore') as f:
                        raw = f.read()
                    try:
                        data = json.loads(raw, strict=False)
                    except Exception:
                        data = json.loads(clean_jsonc(raw), strict=False)

                    if not isinstance(data, dict):
                        continue

                    def walk_dict(d):
                        for k, v in d.items():
                            if k in ['DT_PassiveSkill_Main', 'DT_PassiveSkill_Main_Common', 'DT_PassiveSkill'] and isinstance(v, dict):
                                for skill_id, skill_info in v.items():
                                    if isinstance(skill_info, dict) and 'Rank' in skill_info:
                                        mod_ranks[skill_id] = skill_info['Rank']
                            elif k in ['DT_SkillNameText'] and isinstance(v, dict):
                                for name_key, dname in v.items():
                                    if isinstance(dname, str):
                                        base_id = name_key.replace('_NAME', '').replace('_Name', '')
                                        mod_names[base_id] = dname
                                        mod_names[name_key] = dname
                            elif isinstance(v, dict):
                                walk_dict(v)

                            if isinstance(v, str) and ('NAME' in k or 'Name' in k):
                                base_id = k.replace('_NAME', '').replace('_Name', '')
                                mod_names[base_id] = v

                    walk_dict(data)

                except Exception:
                    pass

            for skill_id, rk in mod_ranks.items():
                disp_name = mod_names.get(skill_id, skill_id)
                entry = {
                    'skill_id': skill_id,
                    'rank': rk,
                    'display_name': disp_name,
                    'mod': mdir
                }
                MOD_HARVESTED_PASSIVES[skill_id] = entry
                MOD_HARVESTED_PASSIVES[skill_id.lower()] = entry
                if disp_name:
                    MOD_HARVESTED_PASSIVES[disp_name.lower()] = entry
                    if skill_id not in PASSIVE_SKILL_NAME_MAP:
                        PASSIVE_SKILL_NAME_MAP[skill_id] = disp_name

    unique_ids = len({v['skill_id'] for v in MOD_HARVESTED_PASSIVES.values()}) if MOD_HARVESTED_PASSIVES else 0
    print(f"[*] Harvested {unique_ids} modded passive skill definitions & ranks across installed mods.")


ACTIVE_SKILL_NAME_MAP = {}
ACTIVE_SKILL_ELEMENT_LOOKUP = {}


def harvest_json_exports():
    """Scans exported JSON DataTables in .json exports directory for active/passive skills and localization names."""
    global PASSIVE_SKILL_NAME_MAP, MOD_HARVESTED_PASSIVES, ACTIVE_SKILL_NAME_MAP, ACTIVE_SKILL_ELEMENT_LOOKUP

    if not EXPORTS_DIR.is_dir():
        return

    json_files = glob.glob(str(EXPORTS_DIR / "**" / "*.json*"), recursive=True)
    if not json_files:
        return

    def parse_enum(s):
        if not isinstance(s, str):
            return str(s)
        if "::" in s:
            return s.split("::")[-1]
        return s

    def clean_element(elem_str):
        e = parse_enum(elem_str)
        mapping = {
            "Fire": "Fire",
            "Water": "Water",
            "Leaf": "Grass",
            "Grass": "Grass",
            "Electricity": "Electric",
            "Electric": "Electric",
            "Ice": "Ice",
            "Earth": "Ground",
            "Ground": "Ground",
            "Dark": "Dark",
            "Dragon": "Dragon",
            "Normal": "Neutral",
            "Neutral": "Neutral",
        }
        return mapping.get(e, "Neutral")

    total_passives = 0
    total_wazas = 0
    total_names = 0

    for fpath in json_files:
        fname = os.path.basename(fpath)
        try:
            with open(fpath, 'r', encoding='utf-8-sig', errors='ignore') as f:
                data = json.load(f)

            def scan_obj(obj):
                nonlocal total_passives, total_wazas, total_names
                if not isinstance(obj, dict):
                    return
                
                rows = obj.get('Rows') or obj.get('Properties', {}).get('Rows')
                if isinstance(rows, dict):
                    for row_key, row_val in rows.items():
                        if not isinstance(row_val, dict):
                            continue

                        # 1. Passive Skill Ranks
                        if 'Rank' in row_val:
                            rk = row_val['Rank']
                            entry = {'skill_id': row_key, 'rank': rk, 'display_name': row_key, 'mod': fname}
                            MOD_HARVESTED_PASSIVES[row_key] = entry
                            MOD_HARVESTED_PASSIVES[row_key.lower()] = entry
                            total_passives += 1

                        # 2. Active Skill Elements (Waza)
                        if 'WazaType' in row_val or 'Element' in row_val:
                            w_type = parse_enum(row_val.get('WazaType', row_key))
                            w_elem = clean_element(row_val.get('Element', 'Neutral'))
                            if w_type:
                                ACTIVE_SKILL_ELEMENT_LOOKUP[w_type] = w_elem
                                ACTIVE_SKILL_ELEMENT_LOOKUP[w_type.lower()] = w_elem
                                ACTIVE_SKILL_ELEMENT_LOOKUP[row_key] = w_elem
                                ACTIVE_SKILL_ELEMENT_LOOKUP[row_key.lower()] = w_elem
                                total_wazas += 1

                        # 3. Text & Localizations
                        if 'TextData' in row_val and isinstance(row_val['TextData'], dict):
                            td = row_val['TextData']
                            loc_str = td.get('LocalizedString') or td.get('SourceString')
                            if loc_str and loc_str != '-' and not any(ord(c) > 0x3000 for c in loc_str[:5]):
                                base_id = row_key.replace('PASSIVE_', '').replace('WAZA_', '').replace('SKILL_', '').replace('ACTION_SKILL_', '')
                                PASSIVE_SKILL_NAME_MAP[row_key] = loc_str
                                PASSIVE_SKILL_NAME_MAP[base_id] = loc_str
                                PASSIVE_SKILL_NAME_MAP[base_id.lower()] = loc_str
                                ACTIVE_SKILL_NAME_MAP[row_key] = loc_str
                                ACTIVE_SKILL_NAME_MAP[base_id] = loc_str
                                ACTIVE_SKILL_NAME_MAP[base_id.lower()] = loc_str
                                total_names += 1

                for k, v in obj.items():
                    if isinstance(v, list):
                        for item in v:
                            scan_obj(item)
                    elif isinstance(v, dict) and k != 'Rows':
                        scan_obj(v)

            if isinstance(data, list):
                for d in data:
                    scan_obj(d)
            elif isinstance(data, dict):
                scan_obj(data)

        except Exception:
            pass

    print(f"[*] Harvested DataTables from .json exports: {total_passives} passive ranks, {total_wazas} active skill elements, {total_names} text localizations.")


def harvest_passives_and_implants_tab(workbook):
    """Harvests user-curated Passive Skill display names, internal keys, and ranks from the 'Passives and Implants' tab."""
    global PASSIVE_SKILL_NAME_MAP, MOD_HARVESTED_PASSIVES

    try:
        ws = workbook.worksheet(PASSIVE_REF_TAB_NAME)
        all_vals = ws.get_all_values()
        if not all_vals or len(all_vals) <= 1:
            return

        count = 0
        for r in all_vals[1:]:
            if len(r) >= 3:
                s_name = r[0].strip()
                int_key = r[1].strip()
                rank_str = r[2].strip()

                if not int_key and not s_name:
                    continue

                m = re.search(r"Rank\s*(-?\d+)", rank_str, re.IGNORECASE)
                if m:
                    rk = int(m.group(1))
                elif rank_str.lstrip("-").isdigit():
                    rk = int(rank_str)
                else:
                    rk = 0

                entry = {
                    "skill_id": int_key or s_name,
                    "rank": rk,
                    "display_name": s_name or int_key,
                    "mod": PASSIVE_REF_TAB_NAME,
                }

                if int_key:
                    MOD_HARVESTED_PASSIVES[int_key] = entry
                    MOD_HARVESTED_PASSIVES[int_key.lower()] = entry
                    if s_name:
                        PASSIVE_SKILL_NAME_MAP[int_key] = s_name
                        PASSIVE_SKILL_NAME_MAP[int_key.lower()] = s_name

                if s_name:
                    MOD_HARVESTED_PASSIVES[s_name] = entry
                    MOD_HARVESTED_PASSIVES[s_name.lower()] = entry
                    if int_key:
                        PASSIVE_SKILL_NAME_MAP[s_name] = s_name
                        PASSIVE_SKILL_NAME_MAP[s_name.lower()] = s_name

                count += 1

        print(f"[OK] Successfully loaded {count} passive skill overrides from '{PASSIVE_REF_TAB_NAME}' tab.")
    except Exception as e:
        print(f"[!] Info: Could not load '{PASSIVE_REF_TAB_NAME}' tab: {e}")


def harvest_skill_fruits_tab(workbook):
    """Harvests Active Skill display names and Element types from the 'Skill Fruits' tab."""
    global ACTIVE_SKILL_ELEMENT_LOOKUP

    try:
        ws = workbook.worksheet(SKILL_FRUITS_TAB_NAME)
        all_vals = ws.get_all_values()
        if not all_vals or len(all_vals) <= 1:
            return

        count = 0
        for r in all_vals[1:]:
            if len(r) >= 2:
                elem_raw = r[0].strip()
                s_name = r[1].strip()

                if not elem_raw or not s_name:
                    continue

                e_clean = elem_raw.capitalize()
                if e_clean in {"Neutral", "Fire", "Water", "Grass", "Electric", "Ice", "Ground", "Dark", "Dragon"}:
                    ACTIVE_SKILL_ELEMENT_LOOKUP[s_name] = e_clean
                    ACTIVE_SKILL_ELEMENT_LOOKUP[s_name.lower()] = e_clean
                    count += 1

        print(f"[OK] Successfully loaded {count} active skill elements from '{SKILL_FRUITS_TAB_NAME}' tab.")
    except Exception as e:
        print(f"[!] Info: Could not load '{SKILL_FRUITS_TAB_NAME}' tab: {e}")


# Run mod passive and JSON exports harvester at script import time
harvest_installed_mod_passives()
harvest_json_exports()


def get_active_skill_element(skill_name: str) -> str:
    """Categorizes Active Skill name into Palworld Element type."""
    if not skill_name or skill_name == "-":
        return "Neutral"
    s_key = skill_name.strip()
    if s_key in ACTIVE_SKILL_ELEMENT_LOOKUP:
        return ACTIVE_SKILL_ELEMENT_LOOKUP[s_key]
    if s_key.lower() in ACTIVE_SKILL_ELEMENT_LOOKUP:
        return ACTIVE_SKILL_ELEMENT_LOOKUP[s_key.lower()]
    s_lower = skill_name.lower()
    for elem, keywords in ACTIVE_SKILL_ELEMENT_MAP.items():
        if any(k in s_lower for k in keywords):
            return elem
    return "Neutral"


def get_passive_skill_level(skill_name: str) -> int:
    """Categorizes Passive Skill display name or internal ID into level rating (-3 to +5), incorporating modded passives."""
    if not skill_name or skill_name == "-":
        return 0

    p_key = skill_name.strip()
    if p_key in MOD_HARVESTED_PASSIVES:
        return MOD_HARVESTED_PASSIVES[p_key]['rank']
    if p_key.lower() in MOD_HARVESTED_PASSIVES:
        return MOD_HARVESTED_PASSIVES[p_key.lower()]['rank']

    p_lower = skill_name.lower()
    if any(k in p_lower for k in ["sirenofthevoid", "eternalflame", "holyknight", "darkknight", "prismatic"]):
        return 5
    if any(k in p_lower for k in ["emperor", "sireoflightning", "divinedragon", "lordofunderworld", "legend"]):
        return 4
    if any(k in p_lower for k in ["artisan", "swift", "lucky", "demongod", "infinitestamina", "rare"]):
        return 3
    if any(k in p_lower for k in ["clumsy", "slacker", "terrible", "devastated"]):
        return -3
    if any(k in p_lower for k in ["pacifist", "brittle", "distracted"]):
        return -2
    if any(k in p_lower for k in ["coward", "softskin", "soft skin", "unskilled", "slowpoke", "neurotic", "glutton"]):
        return -1
    if any(k in p_lower for k in ["musclehead", "ferocious", "workslave", "runner", "burly", "diet lover", "foreman"]):
        return 2
    if any(k in p_lower for k in ["serious", "hard skin", "brave", "nimble", "nocturnal", "vanguard", "stronghold", "positive thinker"]):
        return 1
    return 0


def hex_to_gspread_rgb(hex_str: str) -> dict:
    """Converts hex color code to gspread 0.0-1.0 RGB float dict."""
    hex_str = hex_str.lstrip("#")
    return {
        "red": int(hex_str[0:2], 16) / 255.0,
        "green": int(hex_str[2:4], 16) / 255.0,
        "blue": int(hex_str[4:6], 16) / 255.0,
    }


def extract_instance_guid(chunk_bytes: bytes) -> str:
    """Extracts 128-bit Pal InstanceId GUID as a formatted UUID string."""
    idx = chunk_bytes.find(b"InstanceId\x00")
    if idx != -1:
        sub = chunk_bytes[idx:idx + 90]
        g_pos = sub.find(b"Guid\x00")
        if g_pos != -1 and g_pos + 5 + 17 + 16 <= len(sub):
            raw_guid = sub[g_pos + 22:g_pos + 38]
            if raw_guid != b"\x00" * 16:
                try:
                    return str(uuid.UUID(bytes_le=raw_guid))
                except Exception:
                    pass
    return ""


def extract_gender_val(chunk_bytes: bytes):
    """Extracts Pal Gender from EnumProperty."""
    idx = chunk_bytes.find(b"Gender\x00")
    if idx != -1:
        sub = chunk_bytes[idx:min(len(chunk_bytes), idx + 120)]
        if b"EPalGenderType::Female" in sub or b"Female\x00" in sub:
            return "♀ Female"
        if b"EPalGenderType::Male" in sub or b"Male\x00" in sub:
            return "♂ Male"
    return "-"


def load_active_party_container_guids(save_folder: Path) -> set:
    """Reads player save files in Players/ directory to retrieve the Active Party container GUIDs."""
    container_guids = set()
    players_dir = save_folder.parent / "Players"
    if not players_dir.is_dir():
        players_dir = save_folder / "Players"

    if players_dir.is_dir():
        for pfile in players_dir.glob("*.sav"):
            try:
                with open(pfile, "rb") as f:
                    p_data = f.read()
                if len(p_data) > 12:
                    p_uncomp = struct.unpack("<I", p_data[0:4])[0]
                    p_comp = struct.unpack("<I", p_data[4:8])[0]
                    payload = p_data[12:12 + p_comp] if p_comp > 0 and (12 + p_comp) <= len(p_data) else p_data[12:]
                    decomp = None
                    try:
                        import palooz  # type: ignore
                        decomp = palooz.decompress(payload, p_uncomp)
                    except Exception:
                        try:
                            import ooz  # type: ignore
                            decomp = ooz.decompress(payload, p_uncomp)
                        except Exception:
                            pass
                    if decomp:
                        pos = decomp.find(b"OtomoCharacterContainerId\x00")
                        if pos != -1:
                            g_idx = decomp.find(b"Guid\x00", pos)
                            if g_idx != -1:
                                guid_bytes = decomp[g_idx + 21:g_idx + 37]
                                if guid_bytes != b"\x00" * 16:
                                    container_guids.add(guid_bytes)
            except Exception:
                pass
    return container_guids


BASE_CAMP_GUID_MAP = {
    bytes.fromhex("0024790dcc21054094b490b08ecf4fc4"): "Ranching Base",
    bytes.fromhex("8f621c3a417bbc49907a3e02e53400c8"): "Mining Base",
    bytes.fromhex("bacee1262e4b2540b226082153642f0e"): "Breeding Base",
    bytes.fromhex("8da0db3068ce924ca50230a3ae527061"): "Main Base",
    bytes.fromhex("52d151c4f56bc940b87eff08dec72ac3"): "Oil Base",
}


def extract_rank_val(chunk_bytes: bytes):
    """Extracts Pal Condensation Rank byte/int (1=0★, 2=1★, 3=2★, 4=3★, 5=4★ Max)."""
    rk_byte = extract_byte_prop("Rank", chunk_bytes)
    if rk_byte is not None:
        return rk_byte
    key = b"Rank\x00"
    idx = chunk_bytes.find(key)
    if idx != -1:
        sub = chunk_bytes[idx:idx + 80]
        i_idx = sub.find(b"IntProperty\x00")
        if i_idx != -1:
            n_idx = sub.find(b"None\x00", i_idx)
            if n_idx != -1 and n_idx + 8 < len(sub):
                return struct.unpack("<i", sub[n_idx + 5:n_idx + 9])[0]
    return 1


def format_rank_stars(rk_val):
    if not rk_val or rk_val <= 1:
        return "-"
    if rk_val == 2:
        return "★"
    if rk_val == 3:
        return "★★"
    if rk_val == 4:
        return "★★★"
    if rk_val >= 5:
        return "★★★★"
    return "-"


def format_favorite_str(fav_val):
    if not fav_val or fav_val == 0:
        return "-"
    if fav_val == 1:
        return "★I"
    if fav_val == 2:
        return "★II"
    if fav_val == 3:
        return "★III"
    return f"★{fav_val}"


def parse_local_data_global_pals(save_folder: Path):
    """Parses Global Palbox Pals from LocalData.sav if present."""
    global_pals = []
    local_data_path = save_folder / "LocalData.sav"
    if not local_data_path.is_file():
        local_data_path = save_folder.parent / "LocalData.sav"

    if not local_data_path.is_file():
        return global_pals

    try:
        with open(local_data_path, "rb") as f:
            f_bytes = f.read()

        decomp = decode_palworld_save(f_bytes)
        if not decomp:
            return global_pals

        sorted_names = sorted(PAL_MASTER_MAP.keys(), key=len, reverse=True)
        pal_id_regex = re.compile(
            rb"(?:BOSS_|Raid_|SUMMON_|NPC_)?("
            + rb"|".join(re.escape(k.encode("ascii")) for k in sorted_names)
            + rb")"
        )

        matches = list(pal_id_regex.finditer(decomp))
        seen_guids = set()

        for match in matches:
            raw_id = match.group(1).decode("ascii", errors="ignore")
            if not raw_id or raw_id == "None":
                continue

            start_pos = max(0, match.start() - 500)
            end_pos = min(len(decomp), match.end() + 3000)
            full_entry_chunk = decomp[max(0, start_pos - 1000):min(len(decomp), end_pos + 1000)]

            inst_guid = extract_instance_guid(full_entry_chunk)
            if inst_guid:
                if inst_guid in seen_guids:
                    continue
                seen_guids.add(inst_guid)
            else:
                anchor = match.start()
                if any(abs(anchor - s) < 48 for s in seen_guids if isinstance(s, int)):
                    continue
                seen_guids.add(anchor)

            display_name, paldeck_num, elem1, elem2, base_work = get_pal_info(raw_id)
            level = extract_level_val(full_entry_chunk)
            gender_str = extract_gender_val(full_entry_chunk)

            rank_val = extract_rank_val(full_entry_chunk)
            star_level = format_rank_stars(rank_val)

            hp_iv = extract_talent_val("HP", full_entry_chunk)
            melee_iv = extract_talent_val("Melee", full_entry_chunk)
            shot_iv = extract_talent_val("Shot", full_entry_chunk)
            def_iv = extract_talent_val("Defense", full_entry_chunk)

            is_boss = b"BOSS_" in match.group(0) or b"IsBoss" in full_entry_chunk or b"RarePal" in full_entry_chunk
            fav_val = extract_byte_prop("FavoriteIndex", full_entry_chunk)
            favorite_str = format_favorite_str(fav_val)

            origin_cell = f'=IMAGE("{GLOBAL_DNA_ICON_URL}")'
            location_preset = "Global Palbox"

            element_str = format_combined_element(elem1, elem2)
            elem1_cell = build_element_xlookup_formula(element_str, ELEMENT_ICON1_COL)
            elem2_cell = build_element_xlookup_formula(element_str, ELEMENT_ICON2_COL)

            work_str = get_suitability_levels(base_work, full_entry_chunk)

            active_skills_list = extract_equipped_active_skills_list(full_entry_chunk)
            passive_skills_list = extract_passive_skills_list(full_entry_chunk)

            row_data = [
                paldeck_num,
                display_name,
                "",  # Placeholder for Portrait formula
                elem1_cell,
                elem2_cell,
                raw_id,
                level,
                star_level,
                gender_str,
                favorite_str,
                location_preset,
                origin_cell,
                work_str,
                "Yes (Alpha)" if is_boss else "No",
                hp_iv,
                melee_iv,
                shot_iv,
                def_iv,
            ] + active_skills_list + passive_skills_list + [inst_guid]
            global_pals.append(row_data)

        print(f"[OK] Extracted {len(global_pals)} Global Palbox Pals from LocalData.sav.")
    except Exception as e:
        print(f"[!] Warning parsing LocalData.sav: {e}")

    return global_pals


def gvas_bytes_to_uuid_str(b: bytes) -> str:
    """Converts 16-byte raw Unreal Engine FGuid (A, B, C, D) to standard canonical UUID string."""
    if not b or len(b) != 16:
        return ""
    a, b_val, c = struct.unpack("<IHH", b[:8])
    big_bytes = struct.pack(">IHH", a, b_val, c) + b[8:]
    return str(uuid.UUID(bytes=big_bytes))


def parse_palworld_save(sav_path):
    print(f"[*] Reading: {sav_path}")
    harvest_installed_mod_passives()
    pals_data = []

    try:
        with open(sav_path, "rb") as f:
            file_bytes = f.read()

        raw_gvas = decode_palworld_save(file_bytes)

        # 1. Resolve Active Party Pal Instance GUIDs (Max 5 active party Pals)
        active_party_instance_guids = set()
        container_guids = load_active_party_container_guids(Path(sav_path).parent)
        cc_pos = raw_gvas.find(b"CharacterContainerSaveData\x00")
        if cc_pos != -1 and container_guids:
            for c_guid in container_guids:
                o_pos = raw_gvas.find(c_guid, cc_pos)
                if o_pos != -1:
                    c_header = raw_gvas[o_pos:o_pos + 1800]
                    for raw_m in re.finditer(rb"RawData\x00", c_header):
                        r_idx = raw_m.start()
                        sub = c_header[r_idx:r_idx + 120]
                        idx = sub.find(b"\x01\x00\x00\x00")
                        if idx != -1 and idx + 20 <= len(sub):
                            g_bytes = sub[idx + 4:idx + 20]
                            if g_bytes != b"\x00" * 16:
                                u_str = gvas_bytes_to_uuid_str(g_bytes)
                                if u_str:
                                    active_party_instance_guids.add(u_str)
                                    if len(active_party_instance_guids) == 5:
                                        break

        # 2. Scope extraction strictly to CharacterSaveParameterMap bounds (up to CharacterContainerSaveData)
        cs_pos = raw_gvas.find(b"CharacterSaveParameterMap\x00")
        if cs_pos != -1 and cc_pos != -1 and cc_pos > cs_pos:
            gvas_scope = raw_gvas[cs_pos:cc_pos]
            print(f"[*] Scoping Pal parsing to CharacterSaveParameterMap ({len(gvas_scope) // 1024 // 1024}MB)...")
        elif cs_pos != -1:
            map_size = int.from_bytes(raw_gvas[cs_pos + 38:cs_pos + 42], "little")
            gvas_scope = raw_gvas[cs_pos:cs_pos + map_size + 2000]
            print(f"[*] Scoping Pal parsing to CharacterSaveParameterMap ({len(gvas_scope) // 1024 // 1024}MB)...")
        else:
            gvas_scope = raw_gvas
            print("[*] Performing binary extraction across decompressed save stream...")

        sorted_names = sorted(PAL_MASTER_MAP.keys(), key=len, reverse=True)
        pal_id_regex = re.compile(
            rb"(?:BOSS_|Raid_|SUMMON_|NPC_)?("
            + rb"|".join(re.escape(k.encode("ascii")) for k in sorted_names)
            + rb")"
        )

        matches = list(pal_id_regex.finditer(gvas_scope))
        print(f"[*] Found {len(matches)} potential Pal name signatures in target map.")

        pal_indicators = [
            b"Level", b"Gender", b"Exp", b"Hp", b"ShotAttack", b"Defense",
            b"PassiveSkill", b"EquipWaza", b"CraftWork", b"Talen_", b"Talent_",
            b"SlotId", b"OwnerPlayerUId", b"SaveParameter", b"CharacterSaveParameter"
        ]

        seen_guids = set()

        for match in matches:
            raw_id = match.group(1).decode("ascii", errors="ignore")
            if not raw_id or raw_id == "None":
                continue

            start_pos = max(0, match.start() - 500)
            end_pos = min(len(gvas_scope), match.end() + 3000)
            chunk = gvas_scope[start_pos:end_pos]

            if not any(ind in chunk for ind in pal_indicators):
                continue

            full_entry_chunk = gvas_scope[max(0, start_pos - 1000):min(len(gvas_scope), end_pos + 1000)]

            inst_guid = extract_instance_guid(full_entry_chunk)
            if inst_guid:
                if inst_guid in seen_guids:
                    continue
                seen_guids.add(inst_guid)
            else:
                slot_anchor = match.start()
                if any(abs(slot_anchor - s) < 48 for s in seen_guids if isinstance(s, int)):
                    continue
                seen_guids.add(slot_anchor)

            display_name, paldeck_num, elem1, elem2, base_work = get_pal_info(raw_id)
            level = extract_level_val(full_entry_chunk)
            gender_str = extract_gender_val(full_entry_chunk)

            # Condensed Rank / Star Level (0★, 1★, 2★, 3★, 4★ Max)
            rank_val = extract_rank_val(full_entry_chunk)
            star_level = format_rank_stars(rank_val)

            # IVs / Talents (0-100 scale)
            hp_iv = extract_talent_val("HP", full_entry_chunk)
            melee_iv = extract_talent_val("Melee", full_entry_chunk)
            shot_iv = extract_talent_val("Shot", full_entry_chunk)
            def_iv = extract_talent_val("Defense", full_entry_chunk)

            is_boss = b"BOSS_" in match.group(0) or b"IsBoss" in full_entry_chunk or b"RarePal" in full_entry_chunk

            fav_val = extract_byte_prop("FavoriteIndex", full_entry_chunk)
            favorite_str = format_favorite_str(fav_val)

            is_imported = b"IsCrossWorld" in full_entry_chunk or b"Global" in chunk[:300]
            origin_cell = f'=IMAGE("{GLOBAL_DNA_ICON_URL}")' if is_imported else "🏠 Local"

            # Strict Location / Base Camp Detection
            is_active_party = bool(inst_guid and inst_guid in active_party_instance_guids)

            if is_active_party:
                location_preset = "Active Party"
            else:
                assigned_base = None
                for bg_bytes, b_name in BASE_CAMP_GUID_MAP.items():
                    if bg_bytes in full_entry_chunk:
                        assigned_base = b_name
                        break
                if assigned_base:
                    location_preset = assigned_base
                elif b"FriendshipBasecampSec" in chunk or b"PalBaseCamp" in chunk:
                    location_preset = "Assigned to Base"
                else:
                    location_preset = "Palbox Storage"

            element_str = format_combined_element(elem1, elem2)
            
            # Element Icon 1 (Column F) and Icon 2 (Column G) from Colors sheet
            elem1_cell = build_element_xlookup_formula(element_str, ELEMENT_ICON1_COL)
            elem2_cell = build_element_xlookup_formula(element_str, ELEMENT_ICON2_COL)

            # 12 Work Suitability Columns (Repeated Themed Symbols)
            work_str = get_suitability_levels(base_work, full_entry_chunk)

            active_skills_list = extract_equipped_active_skills_list(full_entry_chunk)
            passive_skills_list = extract_passive_skills_list(full_entry_chunk)

            row_data = [
                paldeck_num,
                display_name,
                "",  # Placeholder for Portrait formula
                elem1_cell,
                elem2_cell,
                raw_id,
                level,
                star_level,
                gender_str,
                favorite_str,
                location_preset,
                origin_cell,
                work_str,
                "Yes (Alpha)" if is_boss else "No",
                hp_iv,
                melee_iv,
                shot_iv,
                def_iv,
            ] + active_skills_list + passive_skills_list + [inst_guid]

            pals_data.append(row_data)

        # 3. Append Global Palbox entries from LocalData.sav if present
        global_pals = parse_local_data_global_pals(Path(sav_path).parent)
        if global_pals:
            pals_data.extend(global_pals)

        # Post-process Portrait formula (Col C / idx 2) for all rows
        for idx, row in enumerate(pals_data, start=2):
            row[2] = f'=XLOOKUP(A{idx}, PalsTable[Paldeck #], PalsTable[Portrait])'

        print(f"[OK] Extracted {len(pals_data)} total owned Pals with metadata.")
    except Exception as e:
        print(f"[!] Error during extraction: {e}")

    return pals_data


def upload_to_google_sheet(data, credentials_path):
    try:
        client = gspread.service_account(filename=str(credentials_path))
        
        if GOOGLE_SHEET_URL_OR_KEY.startswith("http"):
            workbook = client.open_by_url(GOOGLE_SHEET_URL_OR_KEY)
        elif len(GOOGLE_SHEET_URL_OR_KEY) > 25:
            workbook = client.open_by_key(GOOGLE_SHEET_URL_OR_KEY)
        else:
            workbook = client.open(GOOGLE_SHEET_NAME)

        harvest_passives_and_implants_tab(workbook)
        harvest_skill_fruits_tab(workbook)

        try:
            worksheet = workbook.worksheet(TARGET_SHEET_TAB_NAME)
        except gspread.exceptions.WorksheetNotFound:
            print(f"[+] Tab '{TARGET_SHEET_TAB_NAME}' not found. Creating it...")
            worksheet = workbook.add_worksheet(title=TARGET_SHEET_TAB_NAME, rows=3000, cols=37)

        # Clear data rows starting from Row 2 downwards, preserving Row 1 headers
        try:
            worksheet.batch_clear(["A2:Z3000"])
        except Exception:
            pass

        if data:
            worksheet.update(values=data, range_name="A2", value_input_option="USER_ENTERED")
            print(f"[OK] Success: Uploaded {len(data)} Pal entries to '{TARGET_SHEET_TAB_NAME}' (starting at row 2).")

            # Apply Center Justification & Skill Color formatting
            print("[*] Formatting alignment & Skill colors/heatmaps...")
            format_requests = []
            DARK_KEYS = {"Neutral", "Fire", "Water", "Ground", "Dark", "Dragon", -3, -2, 3, 4, 5}

            # Center Justification on specified columns across all data rows (Row 2 onwards)
            CENTER_COL_RANGES = [
                (0, 1),   # Col A (Paldeck #)
                (2, 5),   # Cols C, D, E (Portrait, Elem1, Elem2)
                (6, 10),  # Cols G, H, I, J (Level, Stars, Gender, Favorite)
                (11, 18), # Cols L, M, N, O, P, Q, R (Origin, Work, Alpha, IVs)
                (18, 21), # Cols S, T, U (Active Skills)
                (21, 25), # Cols V, W, X, Y (Passive Skills)
            ]

            for start_c, end_c in CENTER_COL_RANGES:
                format_requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": worksheet.id,
                            "startRowIndex": 1,
                            "endRowIndex": len(data) + 1,
                            "startColumnIndex": start_c,
                            "endColumnIndex": end_c,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "CENTER",
                            }
                        },
                        "fields": "userEnteredFormat.horizontalAlignment",
                    }
                })

            for row_idx, row_values in enumerate(data, start=2):
                if len(row_values) >= 25:
                    # Active Skills (Cols S, T, U -> index 18, 19, 20)
                    for col_offset, active_skill in enumerate(row_values[18:21]):
                        if active_skill and active_skill != "-":
                            elem = get_active_skill_element(active_skill)
                            hex_color = ELEMENT_HEX_MAP.get(elem, "#795548")
                            bg_rgb = hex_to_gspread_rgb(hex_color)
                            text_rgb = {"red": 1.0, "green": 1.0, "blue": 1.0} if elem in DARK_KEYS else {"red": 0.1, "green": 0.1, "blue": 0.1}
                            format_requests.append({
                                "repeatCell": {
                                    "range": {
                                        "sheetId": worksheet.id,
                                        "startRowIndex": row_idx - 1,
                                        "endRowIndex": row_idx,
                                        "startColumnIndex": 18 + col_offset,
                                        "endColumnIndex": 19 + col_offset,
                                    },
                                    "cell": {
                                        "userEnteredFormat": {
                                            "backgroundColor": bg_rgb,
                                            "textFormat": {"foregroundColor": text_rgb, "bold": True},
                                            "horizontalAlignment": "CENTER",
                                        }
                                    },
                                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                                }
                            })

                    # Passive Skills (Cols V, W, X, Y -> index 21, 22, 23, 24)
                    for col_offset, passive_skill in enumerate(row_values[21:25]):
                        if passive_skill and passive_skill != "-":
                            lvl = get_passive_skill_level(passive_skill)
                            hex_color = PASSIVE_HEATMAP_HEX_MAP.get(lvl, "#FFFFFF")
                            bg_rgb = hex_to_gspread_rgb(hex_color)
                            text_rgb = {"red": 1.0, "green": 1.0, "blue": 1.0} if lvl in DARK_KEYS else {"red": 0.1, "green": 0.1, "blue": 0.1}
                            format_requests.append({
                                "repeatCell": {
                                    "range": {
                                        "sheetId": worksheet.id,
                                        "startRowIndex": row_idx - 1,
                                        "endRowIndex": row_idx,
                                        "startColumnIndex": 21 + col_offset,
                                        "endColumnIndex": 22 + col_offset,
                                    },
                                    "cell": {
                                        "userEnteredFormat": {
                                            "backgroundColor": bg_rgb,
                                            "textFormat": {"foregroundColor": text_rgb, "bold": True if lvl != 0 else False},
                                            "horizontalAlignment": "CENTER",
                                        }
                                    },
                                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                                }
                            })

            # Execute format requests in chunks of 2,000 requests
            chunk_size = 2000
            for i in range(0, len(format_requests), chunk_size):
                sub_reqs = format_requests[i:i + chunk_size]
                workbook.batch_update({"requests": sub_reqs})
            print(f"[OK] Applied alignment & skill color formatting across {len(format_requests)} requests.")
        else:
            print("[!] No Pal data rows to upload.")

    except Exception as e:
        print(f"[!] Google Sheets upload failed: {e}")
        if hasattr(e, "response") and hasattr(e.response, "text"):
            print(f"[!] Server response details:\n{e.response.text[:500]}")
        traceback.print_exc()


def is_game_running():
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] and PROCESS_NAME.lower() in proc.info["name"].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


def export_pals_to_dashboard(pals_rows):
    """Formats raw parsed Pal rows into JSON and writes to Dashboard/pals.json and pals.js"""
    try:
        dashboard_dir = BASE_SCRIPT_DIR / "Dashboard"
        if not dashboard_dir.is_dir():
            return

        structured_pals = []
        for row in pals_rows:
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

            pal_info = get_pal_info(raw_id)
            elem1 = pal_info[2] if len(pal_info) > 2 else "Neutral"
            elem2 = pal_info[3] if len(pal_info) > 3 and pal_info[3] else None

            work_badges = []
            if work_str and work_str != "-":
                parts = [p.strip() for p in str(work_str).split(",")]
                for part in parts:
                    tokens = part.split()
                    if len(tokens) == 2:
                        emoji, lvl = tokens[0], tokens[1]
                        work_badges.append({"emoji": emoji, "level": lvl})

            passive_heatmap_map = {
                5: "#f59e0b",
                4: "#f59e0b",
                3: "#4CAF50",
                2: "#2196F3",
                1: "#9E9E9E",
                -1: "#ef4444",
                -2: "#dc2626",
                -3: "#b91c1c"
            }

            passive_objs = []
            for p_name in passive_skills:
                lvl = get_passive_skill_level(p_name)
                hex_color = passive_heatmap_map.get(lvl, "#2a2d34")
                passive_objs.append({
                    "name": p_name,
                    "tier": lvl,
                    "color": hex_color
                })

            gender_type = "male" if "♂" in str(gender_raw) else "female" if "♀" in str(gender_raw) else "unknown"

            name_slug = display_name.lower().replace(" ", "-").replace("'", "").replace(".", "")
            clean_id = raw_id.replace("BOSS_", "").replace("Raid_", "").replace("NPC_", "").replace("SUMMON_", "").lower()
            clean_id_dash = clean_id.replace("_", "-")

            slug_map = {
                "astralyn": "astralym.png",
                "lilyqueen-noct": "lyleen-noct.png",
                "worldtreedragon": "astralym.png",
                "lilyqueen_dark": "lyleen-noct.png"
            }

            img_base_dir = dashboard_dir / "Images" / "Everything Else" / "Palworld Complete Palpedia List"
            portrait_path = None
            if name_slug in slug_map:
                portrait_path = f"Images/Everything Else/Palworld Complete Palpedia List/{slug_map[name_slug]}"
            elif clean_id in slug_map:
                portrait_path = f"Images/Everything Else/Palworld Complete Palpedia List/{slug_map[clean_id]}"
            elif clean_id_dash in slug_map:
                portrait_path = f"Images/Everything Else/Palworld Complete Palpedia List/{slug_map[clean_id_dash]}"
            elif (img_base_dir / f"{name_slug}.png").exists():
                portrait_path = f"Images/Everything Else/Palworld Complete Palpedia List/{name_slug}.png"
            elif (img_base_dir / f"{clean_id}.png").exists():
                portrait_path = f"Images/Everything Else/Palworld Complete Palpedia List/{clean_id}.png"
            elif (img_base_dir / f"{clean_id_dash}.png").exists():
                portrait_path = f"Images/Everything Else/Palworld Complete Palpedia List/{clean_id_dash}.png"
            else:
                portrait_path = f"https://raw.githubusercontent.com/palworld-modding/icons/main/pals/{clean_id}.png"

            pal_obj = {
                "paldeck_num": paldeck_num,
                "name": display_name,
                "raw_id": raw_id,
                "portrait_url": portrait_path,
                "level": level,
                "stars": star_str,
                "gender": gender_type,
                "gender_symbol": gender_raw,
                "favorite": fav_str,
                "location": location,
                "is_imported": "IMAGE" in str(origin_str) or "Global" in str(location),
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

        json_out = dashboard_dir / "pals.json"
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(structured_pals, f, indent=2, ensure_ascii=False)

        js_out = dashboard_dir / "pals.js"
        with open(js_out, "w", encoding="utf-8") as f:
            f.write("window.PALS_DATA = ")
            json.dump(structured_pals, f, indent=2, ensure_ascii=False)
            f.write(";\n")

        print(f"[OK] Exported {len(structured_pals)} Pals to Dashboard ({json_out.name} and {js_out.name})")
    except Exception as e:
        print(f"[!] Error exporting Pals to Dashboard: {e}")


def run_single_sync():
    print("=" * 65)
    print("       PALWORLD SAVE -> GOOGLE SHEETS SYNC (ONE-SHOT)")
    print("=" * 65)

    try:
        if not GOOGLE_CREDENTIALS_JSON.is_file():
            print(f"[X] Google Credentials JSON not found at:\n    {GOOGLE_CREDENTIALS_JSON}")
            return

        if is_game_running():
            print(f"[+] Palworld is currently running. Waiting for process '{PROCESS_NAME}' to exit...")
            while is_game_running():
                time.sleep(POLL_INTERVAL_SECONDS)
            print(f"[!] Palworld closed at {time.strftime('%X')}.")
        else:
            print("[*] Palworld is not running. Syncing latest save on disk...")

        print("[*] Committing disk buffer (3s)...")
        time.sleep(3)

        # 1. Connect to Google Sheets & harvest Passives and Implants tab FIRST
        try:
            client = gspread.service_account(filename=str(GOOGLE_CREDENTIALS_JSON))
            if GOOGLE_SHEET_URL_OR_KEY.startswith("http"):
                workbook = client.open_by_url(GOOGLE_SHEET_URL_OR_KEY)
            elif len(GOOGLE_SHEET_URL_OR_KEY) > 25:
                workbook = client.open_by_key(GOOGLE_SHEET_URL_OR_KEY)
            else:
                workbook = client.open(GOOGLE_SHEET_NAME)
            harvest_passives_and_implants_tab(workbook)
            harvest_skill_fruits_tab(workbook)
        except Exception as e:
            print(f"[!] Info connecting to Google Sheets prior to save parse: {e}")

        target_save = find_target_save()
        if target_save:
            pals = parse_palworld_save(Path(target_save))
            if pals:
                upload_to_google_sheet(pals, GOOGLE_CREDENTIALS_JSON)
                export_pals_to_dashboard(pals)
            else:
                print("[!] No Pal data recovered from save.")
        else:
            print("[!] Could not locate a valid Level.sav file in SaveGames path.")

        print(f"\n[OK] [{time.strftime('%X')}] Sync complete. Exiting script.")

    except Exception as e:
        print(f"\n[!] Unexpected error during sync execution: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    transcript_handle = init_session_transcript()
    try:
        run_single_sync()
    except KeyboardInterrupt:
        print("\n[!] Operation cancelled by user. Exiting.")
    finally:
        transcript_handle.close()