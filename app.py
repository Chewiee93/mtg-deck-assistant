"""
MTG Deck Builder - CLEAN ARCHITECTURE VERSION
================================================

Key Improvements:
- Blueprint-based structure
- Scryfall API caching (DB-backed)
- Fixed SQLAlchemy issues (including cmc)
- Removed global state
- Separated logic into services

NOTE: This is written as a SINGLE FILE for readability,
but structured as if split across modules.
"""

# =========================
# IMPORTS
# =========================
from flask import Flask, Blueprint, render_template, request, redirect, jsonify, session, g
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base
import requests
import json
import time

# =========================
# DATABASE SETUP
# =========================
Base = declarative_base()

class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    quantity = Column(Integer, default=0)
    color_identity = Column(String)
    type_line = Column(String)
    oracle_text = Column(Text)
    image_url = Column(String)
    image_large = Column(String)
    set_name = Column(String)
    cmc = Column(Integer, default=0)  # ✅ FIXED
    owned = Column(Integer, default=1)

class Deck(Base):
    __tablename__ = "decks"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    format = Column(String, default="casual")
    commander = Column(String, nullable=True)  # ✅ NEW

from sqlalchemy import UniqueConstraint

class DeckCard(Base):
    __tablename__ = "deck_cards"

    id = Column(Integer, primary_key=True)
    deck_id = Column(Integer)
    card_id = Column(Integer)
    quantity = Column(Integer, default=1)
    # DEV: distinguish mainboard vs sideboard
    is_sideboard = Column(Integer, default=0)

    # =========================
    # PREVENT DUPLICATE CARDS IN SAME DECK
    # =========================
    __table_args__ = (
        UniqueConstraint('deck_id', 'card_id', name='uix_deck_card'),
    )

class CardCache(Base):
    """
    Stores raw Scryfall responses to avoid repeated API calls
    """
    __tablename__ = "card_cache"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    data = Column(Text)
    timestamp = Column(Integer)

    # =========================
    # TEMPORARY DATABASE SAVES
    # =========================

class ImportSession(Base):
    __tablename__ = "import_sessions"

    id = Column(Integer, primary_key=True)
    created_at = Column(Integer)
    invalid_lines = Column(Text)


class ImportCard(Base):
    __tablename__ = "import_cards"

    id = Column(Integer, primary_key=True)
    import_id = Column(Integer)
    name = Column(String)
    quantity = Column(Integer)
    data = Column(Text)  # store full card JSON
    # DEV: track sideboard during import
    is_sideboard = Column(Integer, default=0)


engine = create_engine("sqlite:///cards.db")
Base.metadata.create_all(engine)
from sqlalchemy.orm import scoped_session

Session = scoped_session(sessionmaker(bind=engine))

# =========================
# DECK FORMAT
# =========================
FORMAT_RULES = {
    "casual": {
        "deck_size": None,
        "sideboard": False,
        "max_copies": None
    },
    "standard": {
        "deck_size": 60,
        "sideboard": True,
        "max_copies": 4
    },
    "modern": {
        "deck_size": 60,
        "sideboard": True,
        "max_copies": 4
    },
    "commander": {
        "deck_size": 100,
        "sideboard": False,
        "max_copies": 1
    }
}

# =========================
# BANNED CARDS
# =========================
BANNED_CARDS = {
    "modern": ["Black Lotus"],
    "commander": ["Black Lotus"]
}

# =========================
# APP INIT
# =========================
app = Flask(__name__)
app.secret_key = "dev-secret-key"  # required for sessions

@app.before_request
def create_session():
    from flask import g
    g.db = Session()

@app.teardown_request
def remove_session(exception=None):
    Session.remove()

# =========================
# CACHE + API SERVICE
# =========================
def get_card_data(name: str, max_age=86400):
    """
    Fetch card data with caching
    max_age = 1 day default
    """

    cached = g.db.query(CardCache).filter_by(name=name.lower()).first()

    if cached and (time.time() - cached.timestamp < max_age):
        return json.loads(cached.data)

    url = f"https://api.scryfall.com/cards/named?fuzzy={name}"

    try:
        res = requests.get(url, timeout=5)
    except requests.RequestException:
        return None

    if res.status_code != 200:
        return None

    data = res.json()

    if cached:
        cached.data = json.dumps(data)
        cached.timestamp = int(time.time())
    else:
        g.db.add(CardCache(
            name=name.lower(),
            data=json.dumps(data),
            timestamp=int(time.time())
        ))

    g.db.commit()
    return data


# =========================
# SERVICES (LOGIC LAYER)
# =========================
def add_card_to_collection(name):
    data = get_card_data(name)
    if not data:
        return None

    card = g.db.query(Card).filter_by(name=data["name"]).first()

    if card:
        card.quantity += 1
    else:

        images = get_images(data)

        small = images.get("small")
        large = images.get("normal")

        # 🔥 HARD FAIL SAFE
        if not small:
            small = ""
        if not large:
            large = small   # fallback only if truly missing

        card = Card(
            name=data["name"],
            quantity=1,
            color_identity=",".join(data["color_identity"]),
            type_line=data["type_line"],
            oracle_text=data.get("oracle_text", ""),
            image_url=small,
            image_large=large,
            set_name=data.get("set_name", ""),
            cmc=int(data.get("cmc", 0)),
            owned=1
        )
        g.db.add(card)

    g.db.commit()
    return card

def chunked(lst, size=75):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

def get_cards_batch(names):
    url = "https://api.scryfall.com/cards/collection"

    result = {}

    for chunk in chunked(names, 75):
        payload = {
            "identifiers": [{"name": n} for n in chunk]
        }

        try:
            res = requests.post(url, json=payload, timeout=10)
        except requests.RequestException:
            continue

        if res.status_code != 200:
            continue

        data = res.json()

        for card in data.get("data", []):
            result[card["name"].lower()] = card

    return result

# =========================
# DECK IMAGE HELPER
# =========================
def get_deck_cover_image(deck_id):
    """
    Returns first card image in deck.
    Used for deck thumbnails.
    """
    first_dc = g.db.query(DeckCard)\
        .filter_by(deck_id=deck_id)\
        .order_by(DeckCard.id.asc())\
        .first()

    if first_dc:
        card = g.db.get(Card, first_dc.card_id)
        if card and card.image_url:
            return card.image_url
        
    # DEV FIX: fallback to ANY card in deck
    any_dc = g.db.query(DeckCard).filter_by(deck_id=deck_id).first()
    if any_dc:
        card = g.db.get(Card, any_dc.card_id)
        if card and card.image_url:
            return card.image_url

    # fallback image
    return "/static/placeholder.jpg"

def get_images(data):
    # Normal cards
    if "image_uris" in data:
        return data["image_uris"]

    # Multi-face cards
    if "card_faces" in data:
        for face in data["card_faces"]:
            if "image_uris" in face:
                return face["image_uris"]

    return {}

def get_card_prints(name):
    url = f"https://api.scryfall.com/cards/search?q=!\"{name}\""

    try:
        res = requests.get(url, timeout=5)
    except requests.RequestException:
        return []

    if res.status_code != 200:
        return []

    data = res.json()

    prints = []
    for card in data.get("data", []):
        images = get_images(card)

        prints.append({
            "set": card.get("set_name", ""),
            "code": card.get("set", ""),
            "image": images.get("small", ""),
            "id": card.get("id")
        })

    return prints[:10]  # limit for sanity

def analyze_deck(deck_id):
    deck = g.db.get(Deck, deck_id)

    commander_image = None

    if deck.commander:
        commander_card = g.db.query(Card).filter_by(name=deck.commander).first()
        if commander_card:
            commander_image = commander_card.image_large or commander_card.image_url

    rules = FORMAT_RULES.get(deck.format, {})

    deck_cards = g.db.query(DeckCard).filter_by(deck_id=deck_id).all()

    total_cards = sum(dc.quantity for dc in deck_cards)

    # =========================
    # OUTPUT STRUCTURE
    # =========================
    format_issues = []
    general_warnings = []
    warnings = []
    strengths = []

    # =========================
    # BASIC VALIDATION
    # =========================

    # Deck size
    if rules.get("deck_size") and total_cards != rules["deck_size"]:
        format_issues.append(f"Deck should have {rules['deck_size']} cards (currently {total_cards})")

    # Max copies
    if rules.get("max_copies"):
        for dc in deck_cards:
            if dc.quantity > rules["max_copies"]:
                card = g.db.get(Card, dc.card_id)
                format_issues.append(f"{card.name}: too many copies ({dc.quantity})")

    # Banned cards
    banned = BANNED_CARDS.get(deck.format, [])
    for dc in deck_cards:
        card = g.db.get(Card, dc.card_id)

        if not card:
            continue  # skip broken reference

        if card.name in banned:
            format_issues.append(f"{card.name} is banned in {deck.format}")

    # =========================
    # COMMANDER RULES
    # =========================
    if deck.format == "commander":

        if total_cards != 100:
            format_issues.append(f"Commander decks must have 100 cards (currently {total_cards})")

        # Singleton rule
        for dc in deck_cards:
            if dc.quantity > 1:
                card = g.db.get(Card, dc.card_id)
                format_issues.append(f"{card.name}: only 1 copy allowed in Commander")

        # Commander presence
        if not deck.commander:
            format_issues.append("No commander selected")

    # =========================
    # ROLE ANALYSIS
    # =========================

    role_counts = analyze_deck_roles(deck_cards)
    stats = calculate_deck_stats(deck_cards)
    archetype = detect_archetype(stats, role_counts)

    # =========================
    # SMART FEEDBACK (ROLE BASED)
    # =========================

    # Example thresholds (tweak later)
    if role_counts["card_draw"] < 5:
        warnings.append("Low card draw — deck may run out of gas")

    if role_counts["ramp"] < 5 and "Ramp" in archetype:
        warnings.append("Low ramp for a ramp-focused deck")

    if role_counts["removal"] < 4:
        warnings.append("Low removal — may struggle vs threats")

    if role_counts["board_wipe"] == 0 and "Control" in archetype:
        warnings.append("Control decks usually need board wipes")

    # =========================
    # STRENGTHS (positive feedback)
    # =========================

    if role_counts["card_draw"] >= 8:
        strengths.append("Strong card draw engine")

    if role_counts["removal"] >= 6:
        strengths.append("Strong removal suite")

    if role_counts["ramp"] >= 8:
        strengths.append("Excellent ramp package")

    return {
        "format_issues": format_issues,
        "warnings": warnings,
        "strengths": strengths,
        "archetype": archetype,
        "commander_image": commander_image
    }

def calculate_deck_stats(deck_cards):
    stats = {
        "total": 0,
        "creatures": 0,
        "lands": 0,
        "others": 0,
    }

    for dc in deck_cards:
        card = g.db.get(Card, dc.card_id)

        if not card:
            continue

        stats["total"] += dc.quantity

        if "Creature" in card.type_line:
            stats["creatures"] += dc.quantity
        elif "Land" in card.type_line:
            stats["lands"] += dc.quantity
        else:
            stats["others"] += dc.quantity

    return stats

def detect_archetype(stats, role_counts):
    if stats["total"] == 0:
        return "Unknown"

    scores = {}

    # =========================
    # AGGRO
    # =========================
    scores["Aggro"] = (
        stats["creatures"] * 2 +
        role_counts["tokens"] +
        role_counts["aristocrats"]
    )

    # =========================
    # CONTROL
    # =========================
    scores["Control"] = (
        role_counts["removal"] * 2 +
        role_counts["board_wipe"] * 3 +
        role_counts["card_draw"]
    )

    # =========================
    # MIDRANGE
    # =========================
    scores["Midrange"] = (
        stats["creatures"] +
        role_counts["removal"] +
        role_counts["card_draw"]
    )

    # =========================
    # RAMP
    # =========================
    scores["Ramp"] = (
        role_counts["ramp"] * 3
    )

    # =========================
    # ARISTOCRATS
    # =========================
    scores["Aristocrats"] = (
        role_counts["aristocrats"] * 3 +
        role_counts["recursion"]
    )

    # =========================
    # TOKENS
    # =========================
    scores["Tokens"] = (
        role_counts["tokens"] * 3
    )

    # =========================
    # STAX
    # =========================
    scores["Stax"] = (
        role_counts["stax"] * 4
    )

    # =========================
    # TOOLBOX
    # =========================
    scores["Toolbox"] = (
        role_counts["toolbox"] * 3
    )

    # =========================
    # PILLOWFORT
    # =========================
    scores["Pillowfort"] = (
        role_counts["pillowfort"] * 3
    )

    # =========================
    # CONVERT TO PERCENTAGES
    # =========================

    total_score = sum(scores.values())

    # Avoid divide-by-zero
    if total_score == 0:
        return "Unknown"

    percentages = {
        k: int((v / total_score) * 100)
        for k, v in scores.items()
    }

    # =========================
    # PICK TOP 2 ARCHETYPES
    # =========================
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    if len(sorted_scores) < 2:
        return sorted_scores[0][0]

    primary = sorted_scores[0][0]
    secondary = sorted_scores[1][0]

    primary_pct = percentages[primary]
    secondary_pct = percentages[secondary]

    # =========================
    # RETURN FORMATTED RESULT
    # =========================

    return f"{primary} ({primary_pct}%) / {secondary} ({secondary_pct}%)"

def classify_card_roles(card):
    text = (card.oracle_text or "").lower()
    type_line = (card.type_line or "").lower()

    roles = set()

    # ---- Ramp ----
    if any(x in text for x in [
        "add ", "search your library for a land",
        "create a treasure", "mana of any color"
    ]):
        roles.add("ramp")

    # ---- Removal ----
    if any(x in text for x in [
        "destroy target", "exile target",
        "damage to target", "target creature gets -"
    ]):
        roles.add("removal")

    # ---- Board Wipe ----
    if any(x in text for x in [
        "destroy all", "exile all", "each creature"
    ]):
        roles.add("board_wipe")

    # ---- Card Draw ----
    if any(x in text for x in [
        "draw", "scry"
    ]):
        roles.add("card_draw")

    # ---- Recursion ----
    if any(x in text for x in [
        "return from your graveyard", "from your graveyard to"
    ]):
        roles.add("recursion")

    # ---- Tokens ----
    if "create" in text and "token" in text:
        roles.add("tokens")

    # ---- Aristocrats (sacrifice/value death) ----
    if any(x in text for x in [
        "sacrifice", "dies", "whenever a creature dies"
    ]):
        roles.add("aristocrats")

    # ---- Pillowfort ----
    if any(x in text for x in [
        "can't attack you", "attacks you"
    ]):
        roles.add("pillowfort")

    # ---- Toolbox (tutors/search effects) ----
    if any(x in text for x in [
        "search your library for a card"
    ]):
        roles.add("toolbox")

    # ---- Stax ----
    if any(x in text for x in [
        "can't cast", "skip", "can't untap"
    ]):
        roles.add("stax")

    return roles

def analyze_deck_roles(deck_cards):
    role_counts = {
        "ramp": 0,
        "removal": 0,
        "card_draw": 0,
        "board_wipe": 0,
        "recursion": 0,
        "tokens": 0,
        "aristocrats": 0,
        "pillowfort": 0,
        "toolbox": 0,
        "stax": 0
    }

    for dc in deck_cards:
        card = g.db.get(Card, dc.card_id)

        if not card:
            continue

        roles = classify_card_roles(card)

        for role in roles:
            role_counts[role] += dc.quantity

    return role_counts

ROLE_TARGETS = {
    "ramp": 8,
    "removal": 6,
    "card_draw": 6
}

def find_missing_roles(role_counts):
    missing = {}

    for role, target in ROLE_TARGETS.items():
        current = role_counts.get(role, 0)

        if current < target:
            missing[role] = target - current

    return missing

RECOMMENDATION_POOL = {
    "ramp": [
        "Sol Ring",
        "Arcane Signet",
        "Cultivate",
        "Kodama's Reach"
    ],
    "removal": [
        "Swords to Plowshares",
        "Path to Exile",
        "Beast Within",
        "Chaos Warp"
    ],
    "card_draw": [
        "Rhystic Study",
        "Phyrexian Arena",
        "Harmonize",
        "Expressive Iteration"
    ]
}

def generate_recommendations(deck_cards):
    role_counts = analyze_deck_roles(deck_cards)
    missing_roles = find_missing_roles(role_counts)

    recommendations = []

    for role, deficit in missing_roles.items():
        pool = RECOMMENDATION_POOL.get(role, [])

        # Recommend up to deficit (but cap at 3 for UI sanity)
        for card_name in pool[:min(deficit, 3)]:
            # DEV: structured recommendation object
            recommendations.append({
                "name": card_name,
                "role": role,
                "owned": False
            })

    return recommendations, role_counts, missing_roles

def suggest_from_collection(missing_roles, deck_colors):
    suggestions = []

    owned_cards = g.db.query(Card).filter(Card.quantity > 0).all()

    for card in owned_cards:
        roles = classify_card_roles(card)

        card_colors = set((card.color_identity or "").split(","))

        # DEV: filter out off-colour cards
        if deck_colors and not card_colors.issubset(deck_colors):
            continue

        for role in roles:
            if role in missing_roles:
                suggestions.append({
                    "name": card.name,
                    "role": role,
                    "owned": True
                })

    return suggestions[:10]  # cap it

# =========================
# BLUEPRINT: MAIN
# =========================
main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def home():
    return render_template("home.html")

@main_bp.route("/collection", methods=["GET", "POST"])
def collection():

    if request.method == "POST":
        add_card_to_collection(request.form["card_name"])

    cards = g.db.query(Card).filter(Card.quantity > 0).all()
    deck_data = []

    decks = g.db.query(Deck).all()

    for deck in decks:
        first_dc = g.db.query(DeckCard)\
            .filter_by(deck_id=deck.id)\
            .order_by(DeckCard.id.asc())\
            .first()

        image = None

        # DEV: use helper instead of duplicating logic
        image = get_deck_cover_image(deck.id)

        deck_data.append({
            "id": deck.id,
            "name": deck.name,
            "image": image
        })

    return render_template(
        "index.html", 
        cards=cards, 
        decks=deck_data,
        added=None
        )



# =========================
# IMPORT: STEP 1 (PARSE + PREVIEW)
# =========================
@main_bp.route("/import")
def import_page():
    return render_template("import.html")

@main_bp.route("/import_deck", methods=["POST"])
def import_deck():
    """
    Takes raw deck list input and converts it into structured card data.

    Does NOT write to database yet.
    Instead:
    - Parses input
    - Fetches card data from Scryfall
    - Stores results in temporary memory
    - Sends to review page for confirmation
    """
    
    session["imported_deck_name"] = request.form.get("deck_name", "Imported Deck")
    session["import_all_owned"] = request.form.get("all_owned") == "1"
    session["import_format"] = request.form.get("format", "casual")

    import_session = ImportSession(created_at=int(time.time()))
    g.db.add(import_session)
    g.db.flush()

    import_id = import_session.id

    text = request.form.get("deck_list", "")
    lines = text.split("\n")

    invalid_lines = []

    commander_name = None
    in_commander_section = False
    # DEV: track sideboard section
    in_sideboard_section = False
    
    parsed_lines = []
    names = []

    for line in lines:
        line = line.strip()

        # =========================
        # BLANK LINE = SIDEBOARD SPLIT
        # =========================
        if not line:
            in_sideboard_section = True
            continue

        # =========================
        # SECTION DETECTION
        # =========================
        if line.lower() == "commander":
            in_commander_section = True
            continue

        if line.lower() == "sideboard":
            in_sideboard_section = True
            continue

        if line.lower() == "deck":
            in_commander_section = False
            in_sideboard_section = False
            continue

        parts = line.split(" ", 1)

        if len(parts) == 1:
            qty = 1
            name = parts[0]

        elif len(parts) == 2:
            try:
                qty = int(parts[0])
                name = parts[1]
            except ValueError:
                qty = 1
                name = line

        else:
            invalid_lines.append(line)
            continue

        name = name.strip()

        # 🎯 Capture commander
        if in_commander_section and not commander_name:
            commander_name = name

        parsed_lines.append((qty, name, in_sideboard_section))

    from collections import defaultdict

    merged = {}

    for qty, name, is_sideboard in parsed_lines:
        if name not in merged:
            merged[name] = {"qty": 0, "sideboard": is_sideboard}

        merged[name]["qty"] += qty

    parsed_lines = [
        (data["qty"], name, data["sideboard"])
        for name, data in merged.items()
    ]
    names = list(merged.keys())

    # =========================
    # FORMAT DETECTION (FIXED)
    # =========================
    # DEV FIX: parsed_lines now has 3 values
    total_cards = sum(qty for qty, _, _ in parsed_lines)

    detected_format = "casual"

    # 1. Commander explicitly defined
    if commander_name:
        detected_format = "commander"

    # 2. Heuristic: 100 cards + mostly singleton
    elif total_cards == 100:
        # DEV FIX: unpack 3 values
        duplicate_count = sum(1 for qty, _, _ in parsed_lines if qty > 1)

        if duplicate_count <= 5:  # allow some flexibility
            detected_format = "commander"

    # 3. 60+ cards → likely constructed
    elif total_cards >= 60:
        detected_format = "modern"

    # Save for later use
    session["detected_format"] = detected_format
    session["commander_name"] = commander_name

    # Fetch card data (cached API call)
    card_map = get_cards_batch(names)

    for qty, name, is_sideboard in parsed_lines:
        clean_name = name.strip()

        # 1. Try batch result first (fast)
        data = card_map.get(clean_name.lower())

        # 2. Fallback to fuzzy search (reliable)
        if not data:
            data = get_card_data(clean_name)

        # 3. Still nothing? Track it
        if not data:
            invalid_lines.append(clean_name)
            continue

        images = get_images(data)

        g.db.add(ImportCard(
            import_id=import_id,
            name=data["name"],  # IMPORTANT: use canonical name
            quantity=qty,
            is_sideboard=1 if is_sideboard else 0,  # DEV: mark sideboard
            data=json.dumps({
                "color_identity": data.get("color_identity", []),
                "type_line": data.get("type_line", ""),
                "oracle_text": data.get("oracle_text", ""),
                "image_url": images.get("small", ""),
                "image_large": images.get("normal", ""),
                "set_name": data.get("set_name", ""),
                "cmc": int(data.get("cmc", 0))
            })
        ))

    import_all_owned = session.get("import_all_owned", False)
    imported_cards = session.get("imported_cards", [])

    if not import_all_owned:
        for card in imported_cards:
            card["prints"] = get_card_prints(card["name"])

    # After processing all cards
    import_session.invalid_lines = json.dumps(invalid_lines)

    # Send to review screen
    g.db.commit()
    return redirect(f"/import_review/{import_id}")

# =========================
# IMPORT: STEP 1.5 (REVIEW FROM DB)
# =========================
@main_bp.route("/import_review/<int:import_id>")
def import_review(import_id):
    """
    Displays imported cards for user confirmation.

    Flow:
    - Load temporary import data from database
    - Rebuild card structure expected by template
    - Render review screen

    NOTE:
    This replaces session-based import storage.
    """

    # =========================
    # LOAD IMPORTED CARDS FROM DB
    # =========================
    import_cards = g.db.query(ImportCard).filter_by(import_id=import_id).all()

    parsed_cards = []

    import_session = g.db.get(ImportSession, import_id)

    detected_format = session.get("detected_format", "casual")
    commander_name = session.get("commander_name")

    invalid_lines = []
    if import_session and import_session.invalid_lines:
        invalid_lines = json.loads(import_session.invalid_lines)

    # =========================
    # REBUILD CARD STRUCTURE
    # =========================
    for c in import_cards:
        data = json.loads(c.data)

        parsed_cards.append({
            "name": c.name,
            "quantity": c.quantity,

            # Core card info
            "color_identity": ",".join(data.get("color_identity", [])),
            "type_line": data.get("type_line", ""),
            "oracle_text": data.get("oracle_text", ""),

            # Images
            "image_url": data.get("image_url", ""),
            "image_large": data.get("image_large", ""),

            # Metadata
            "set_name": data.get("set_name", ""),
            "cmc": data.get("cmc", 0)
        })

    # =========================
    # OWNERSHIP FLAG (TEMPORARY SESSION USE)
    # =========================
    import_all_owned = session.get("import_all_owned", False)

    # =========================
    # LOAD PRINT OPTIONS (IF NEEDED)
    # =========================
    if not import_all_owned:
        for card in parsed_cards:
            card["prints"] = get_card_prints(card["name"])

    # =========================
    # RENDER REVIEW TEMPLATE
    # =========================
    return render_template(
        "import_review.html",
        cards=parsed_cards,
        invalid_lines=invalid_lines,
        all_owned=import_all_owned,
        import_id=import_id,
        detected_format=detected_format,
        commander_name=commander_name,
    )

# =========================
# IMPORT: STEP 2 (CONFIRM + SAVE)
# =========================
@main_bp.route("/confirm_import", methods=["POST"])
def confirm_import():
    """
    Finalises the import after user review.

    For each card:
    - Checks ownership (checkbox)
    - Adds/updates collection
    - Adds card to deck

    Then redirects to deck view.
    """
    import_id = request.form.get("import_id")

    import_cards = g.db.query(ImportCard).filter_by(import_id=import_id).all()
    import_all_owned = session.get("import_all_owned", False)
    deck_name = session.get("imported_deck_name", "Imported Deck")
    format_type = session.get("detected_format")

    if not format_type:
        format_type = session.get("import_format", "casual")
    commander_name = request.form.get("commander_override")

    if not commander_name:
        commander_name = session.get("commander_name")

    # Create deck
    deck = Deck(
        name=deck_name,
        format=format_type,
        commander=commander_name
    )

    g.db.add(deck)
    g.db.flush()  # get deck.id before commit

    for i, c in enumerate(import_cards):
        card_data = json.loads(c.data)

        selected_set = request.form.get(f"print_{i}")

        # Check if user marked as owned
        if import_all_owned:
            owned = True
        else:
            owned = request.form.get(f"owned_{i}") == "on"

        # Check if card already exists in collection
        card = g.db.query(Card).filter_by(name=c.name).first()

        if not card:
            # Create new card entry
            set_name = selected_set if selected_set else card_data["set_name"]

            card = Card(
                name=c.name,
                quantity=c.quantity if owned else 0,
                color_identity=",".join(card_data.get("color_identity", [])),
                type_line=card_data["type_line"],
                oracle_text=card_data["oracle_text"],
                image_url=card_data["image_url"],
                image_large=card_data.get("image_large", ""),
                set_name=set_name,
                cmc=card_data["cmc"],
                owned=1 if owned else 0
            )

            g.db.add(card)
            g.db.flush()

        else:
            # Update existing collection if owned
            if owned:
                card.quantity += c.quantity
                card.owned = 1

            if selected_set:
                card.set_name = selected_set

        # =========================
        # ADD OR UPDATE CARD IN DECK
        # =========================

        # Check if this card is already in the deck
        existing = g.db.query(DeckCard).filter_by(
            deck_id=deck.id,
            card_id=card.id
        ).first()

        if existing:
            # If it exists, increase quantity instead of duplicating
            existing.quantity += c.quantity
        else:
            # If not, create new entry
            g.db.add(DeckCard(
                deck_id=deck.id,
                card_id=card.id,
                quantity=c.quantity,
                is_sideboard=c.is_sideboard  # DEV: carry sideboard flag
            ))

    g.db.query(ImportCard).filter_by(import_id=import_id).delete()
    g.db.query(ImportSession).filter_by(id=import_id).delete()
    g.db.commit()
    session.pop("import_all_owned", None)
    session.pop("imported_deck_name", None)

    return redirect(f"/deck/{deck.id}")

# =========================
# BLUEPRINT: DECKS
# =========================
@main_bp.route("/decks")
def decks_page():
    decks = g.db.query(Deck).all()

    deck_data = []

    for deck in decks:
        first_dc = g.db.query(DeckCard)\
            .filter_by(deck_id=deck.id)\
            .order_by(DeckCard.id.asc())\
            .first()

        image = None

        # DEV: use shared helper for consistency
        image = get_deck_cover_image(deck.id)

        deck_data.append({
            "id": deck.id,
            "name": deck.name,
            "image": image
        })

    return render_template("decks.html", decks=deck_data)


# =========================
# BLUEPRINT: DECK
# =========================
deck_bp = Blueprint("deck", __name__)

@deck_bp.route("/deck/<int:deck_id>")
def view_deck(deck_id):
    deck = g.db.get(Deck, deck_id)
    deck_cards = g.db.query(DeckCard).filter_by(deck_id=deck_id).all()

    analysis = analyze_deck(deck_id)

    commander_image = analysis.get("commander_image")

    if not commander_image:
        commander_image = "/static/placeholder.jpg"

    # =========================
    # DETERMINE DECK COLOURS (FROM COMMANDER)
    # =========================
    deck_colors = set()

    if deck.commander:
        commander_card = g.db.query(Card).filter_by(name=deck.commander).first()
        if commander_card and commander_card.color_identity:
            deck_colors = set(commander_card.color_identity.split(","))

    # =========================
    # SPLIT MAINBOARD / SIDEBOARD
    # =========================
    mainboard = []
    sideboard = []

    for dc in deck_cards:
        card = g.db.get(Card, dc.card_id)

        if not card:
            continue

        entry = {
            "id": card.id,
            "name": card.name,
            "quantity": dc.quantity,
            "image_url": card.image_url,
            "image_large": card.image_large,
            "owned": card.owned,
            "cmc": card.cmc or 0
        }

        # DEV FIX: MUST be inside loop
        if dc.is_sideboard:
            sideboard.append(entry)
        else:
            mainboard.append(entry)

    creatures = []
    lands = []
    others = []

    for c in mainboard:
        card_obj = g.db.get(Card, c["id"])

        if not card_obj:
            continue

        type_line = (card_obj.type_line or "").lower()

        if "land" in type_line:
            lands.append(c)
        elif "creature" in type_line:
            creatures.append(c)
        else:
            others.append(c)

    creatures.sort(key=lambda c: (c["cmc"], c["name"]))
    lands.sort(key=lambda c: (c["cmc"], c["name"]))
    others.sort(key=lambda c: (c["cmc"], c["name"]))

    stats = calculate_deck_stats(deck_cards)
    role_counts = analyze_deck_roles(deck_cards)

    recommendations, role_counts, missing_roles = generate_recommendations(deck_cards)
    suggestions = suggest_from_collection(missing_roles, deck_colors)

    from collections import defaultdict

    curve = defaultdict(int)

    for dc in deck_cards:
        card = g.db.get(Card, dc.card_id)

        if not card:
            continue

        cmc = card.cmc or 0
        curve[cmc] += dc.quantity

    # Convert to sorted lists for chart
    grouped_curve = {}

    for cmc, count in curve.items():
        if cmc >= 7:
            grouped_curve["7+"] = grouped_curve.get("7+", 0) + count
        else:
            grouped_curve[cmc] = count

    # Sort properly (numbers first, then "7+")
    curve_labels = sorted([k for k in grouped_curve if k != "7+"])
    if "7+" in grouped_curve:
        curve_labels.append("7+")

    curve_values = [grouped_curve[k] for k in curve_labels]

    return render_template(
        "deck.html",
        deck=deck,
        deck_id=deck.id,
        commander_name=deck.commander,
        creatures=creatures,
        lands=lands,
        others=others,
        sideboard=sideboard,
        stats=stats,

        format_issues=analysis["format_issues"],
        warnings=analysis["warnings"],
        strengths=analysis["strengths"],
        archetype=analysis["archetype"],

        recommended=recommendations,
        suggestions=suggestions,
        ramp=role_counts["ramp"],
        removal=role_counts["removal"],
        card_draw=role_counts["card_draw"],
        board_wipe=role_counts["board_wipe"],
        recursion=role_counts["recursion"],
        tokens=role_counts["tokens"],
        aristocrats=role_counts["aristocrats"],
        pillowfort=role_counts["pillowfort"],
        toolbox=role_counts["toolbox"],
        stax=role_counts["stax"],
        curve_labels=curve_labels,
        curve_values=curve_values,
        commander_image=commander_image,
        
    )

@deck_bp.route("/create_deck", methods=["POST"])
def create_deck():
    name = request.form["deck_name"]
    format_type = request.form.get("format", "casual")

    if name:
        g.db.add(Deck(name=name, format=format_type))
        g.db.commit()
    return redirect("/decks")

@deck_bp.route("/delete_deck/<int:deck_id>")
def delete_deck(deck_id):
    deck = g.db.get(Deck, deck_id)

    if deck:
        # Remove linked cards first
        g.db.query(DeckCard).filter_by(deck_id=deck_id).delete()

        g.db.delete(deck)
        g.db.commit()

    return redirect("/decks")

@deck_bp.route("/rename_deck/<int:deck_id>", methods=["POST"])
def rename_deck(deck_id):
    deck = g.db.get(Deck, deck_id)

    if deck:
        new_name = request.form.get("new_name")
        if new_name:
            deck.name = new_name
            g.db.commit()

    return redirect(f"/deck/{deck_id}")

# =========================
# BLUEPRINT: SET COMMANDER
# =========================
@deck_bp.route("/set_commander/<int:deck_id>", methods=["POST"])
def set_commander(deck_id):
    deck = g.db.get(Deck, deck_id)

    name = request.json.get("name")
    deck.commander = name

    g.db.commit()
    return jsonify({"success": True})

# =========================
# BLUEPRINT: RULES
# =========================

@main_bp.route("/rules")
def rules_page():
    return render_template("rules.html")

# =========================
# API ROUTES
# =========================
# - add_card
# - update_quantity
# - remove_card (future)
# - remove_card_from_deck
# - mark_owned
# - card_suggest

# =========================
# ADD CARD
#==========================
api_bp = Blueprint("api", __name__)

@api_bp.route("/api/add_card", methods=["POST"])
def api_add_card():
    data = request.json
    print("ADD CARD API HIT:", data)  # DEV DEBUG

    card = add_card_to_collection(data.get("name"))

    if not card:
        print("Card fetch failed")  # DEV DEBUG
        return jsonify({"success": False})

    return jsonify({
        "success": True,
        "card": {
            "id": card.id,
            "name": card.name,
            "quantity": card.quantity
        }
    })

# =========================
# UPDATE QUANTITY
# =========================
@api_bp.route("/api/update_quantity", methods=["POST"])
def api_update_quantity():
    data = request.get_json()  # safer than request.json

    if not data:
        return jsonify({"success": False, "error": "No JSON received"})

    card_id = data.get("card_id")
    change = data.get("change")

    if card_id is None or change is None:
        return jsonify({"success": False, "error": "Missing fields"})

    card = g.db.get(Card, card_id)

    if not card:
        return jsonify({"success": False, "error": "Card not found"})

    # Update quantity safely
    card.quantity = max(0, card.quantity + change)

    # Update quantity safely
    card.quantity = max(0, card.quantity + change)

    if card.quantity == 0:
        g.db.delete(card)
        g.db.commit()

        return jsonify({
            "success": True,
            "quantity": 0
        })

    # DEV FIX: must return for normal updates
    g.db.commit()

    return jsonify({
        "success": True,
        "quantity": card.quantity
    })

@api_bp.route("/api/remove_from_deck/<int:deck_id>/<int:card_id>")
def remove_from_deck(deck_id, card_id):
    g.db.query(DeckCard).filter_by(
        deck_id=deck_id,
        card_id=card_id
    ).delete()

    g.db.commit()
    return jsonify({"success": True})


@api_bp.route("/api/mark_owned/<int:card_id>")
def mark_owned(card_id):
    card = g.db.get(Card, card_id)
    if card:
        card.owned = 1
        card.quantity = max(1, card.quantity)
        g.db.commit()

    return jsonify({"success": True})

# =========================
# CARD SUGGEST
# =========================
@api_bp.route("/api/card_suggest")
def card_suggest():
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify([])

    url = f"https://api.scryfall.com/cards/autocomplete?q={query}"

    try:
        res = requests.get(url, timeout=3)
    except requests.RequestException:
        return jsonify([])

    if res.status_code != 200:
        return jsonify([])

    data = res.json()

    return jsonify(data.get("data", [])[:10])  # limit results


# =========================
# REGISTER BLUEPRINTS
# =========================
app.register_blueprint(main_bp)
app.register_blueprint(deck_bp)
app.register_blueprint(api_bp)

# =========================
# DEBUG
# =========================
@app.route("/debug/deck/<int:deck_id>")
def debug_deck(deck_id):
    rows = g.db.query(DeckCard).filter_by(deck_id=deck_id).all()

    output = []
    for r in rows:
        output.append(f"Deck {r.deck_id} | Card {r.card_id} | Qty {r.quantity}")

    return "<br>".join(output)

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True)
