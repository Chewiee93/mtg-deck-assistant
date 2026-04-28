"""
MTG Deck Builder - CLEAN START VERSION
=====================================

GOAL:
- Fully structured
- Easy to read
- Easy to extend
- No mixed state (NO session-based logic for imports)

RULES:
- DB = single source of truth
- Routes are thin
- Logic lives in services

-------------------------------------
SECTION INDEX
-------------------------------------
1. Imports
2. App + DB Setup
3. Models
4. Constants
5. Services (Logic Layer)
6. Import System (DB-driven)
7. Routes (Main)
8. Routes (Decks)
9. Routes (API)
10. App Init
"""

# =========================
# 1. IMPORTS
# =========================
from flask import Flask, Blueprint, render_template, request, redirect, jsonify, g
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
import requests
import json
import time
import difflib

# =========================
# 2. APP + DB SETUP
# =========================
app = Flask(__name__)

engine = create_engine("sqlite:///cards.db")
Session = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()

@app.before_request
def create_session():
    g.db = Session()

@app.teardown_request
def remove_session(exception=None):
    Session.remove()

# =========================
# 3. MODELS
# =========================

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
    cmc = Column(Integer, default=0)
    owned = Column(Integer, default=1)

class Deck(Base):
    __tablename__ = "decks"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    format = Column(String, default="casual")
    commander = Column(String)

class DeckCard(Base):
    __tablename__ = "deck_cards"

    id = Column(Integer, primary_key=True)
    deck_id = Column(Integer)
    card_id = Column(Integer)
    quantity = Column(Integer, default=1)
    is_sideboard = Column(Integer, default=0)

# =========================
# IMPORT SYSTEM (CLEAN)
# =========================

class ImportSession(Base):
    __tablename__ = "import_sessions"

    id = Column(Integer, primary_key=True)
    created_at = Column(Integer)

    deck_name = Column(String)
    format = Column(String)
    detected_format = Column(String)
    commander_name = Column(String)
    all_owned = Column(Integer, default=0)

    invalid_lines = Column(Text)

class ImportCard(Base):
    __tablename__ = "import_cards"

    id = Column(Integer, primary_key=True)
    import_id = Column(Integer)
    name = Column(String)
    quantity = Column(Integer)
    data = Column(Text)
    image_url = Column(String)
    is_sideboard = Column(Integer, default=0)

Base.metadata.create_all(engine)

# =========================
# 4. CONSTANTS
# =========================

FORMAT_RULES = {
    "commander": {"deck_size": 100, "max_copies": 1},
    "modern": {"deck_size": 60, "max_copies": 4},
    "standard": {"deck_size": 60, "max_copies": 4},
    "casual": {}
}

BANNED = {
    "modern": ["Black Lotus"],
    "standard": [],
    "commander": [],
}

RESTRICTED = {
    "modern": [],
    "standard": [],
    "commander": [],
}

# =========================
# 5. SERVICES
# =========================

def get_card_data(name):
    url = f"https://api.scryfall.com/cards/named?fuzzy={name}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code != 200:
            return None
        return res.json()
    except:
        return None
    
def search_card(name):
    try:
        # =========================
        # 1. FUZZY SEARCH
        # =========================
        url = f"https://api.scryfall.com/cards/search?q={name}~"
        res = requests.get(url, timeout=5)

        if res.status_code == 200:
            data = res.json().get("data", [])
            if data:
                return {"name": data[0]["name"]}

        # =========================
        # 2. AUTOCOMPLETE
        # =========================
        url = f"https://api.scryfall.com/cards/autocomplete?q={name}"
        res = requests.get(url, timeout=5)

        if res.status_code == 200:
            names = res.json().get("data", [])
            if names:
                return {"name": names[0]}

    except:
        pass

    return None
    
def clean_card_name(name):
    name = name.strip()

    # remove weird characters
    name = name.replace("*", "")
    name = name.replace("•", "")

    # =========================
    # DEV: FIX SPLIT CARD FORMAT
    # =========================
    # convert "Card/Card" → "Card // Card"
    if "/" in name and "//" not in name:
        parts = [p.strip() for p in name.split("/")]
        if len(parts) == 2:
            name = f"{parts[0]} // {parts[1]}"

    # normalize spacing
    name = " ".join(name.split())

    return name

def is_confident_match(input_name, result_name):
    input_name = input_name.lower().strip()
    result_name = result_name.lower().strip()

    return difflib.SequenceMatcher(None, input_name, result_name).ratio() > 0.75

def get_local_suggestion(name):
    # get known card names from DB
    cards = g.db.query(Card.name).all()
    names = [c[0] for c in cards]

    matches = difflib.get_close_matches(name, names, n=1, cutoff=0.6)

    return matches[0] if matches else None

# =========================
# BATCH FETCH (DEV: PERFORMANCE FIX)
# =========================

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
# 6. IMPORT LOGIC
# =========================

import re

def parse_deck_list(text):
    lines = text.split("\n")
    parsed = []

    is_sideboard = False

    for raw in lines:
        line = raw.strip()

        if not line:
            continue

        # Detect sideboard
        if re.match(r"^(sideboard|sb:|// sideboard)", line.lower()):
            is_sideboard = True
            continue

        if line.lower() in ["mainboard", "// main", "deck"]:
            is_sideboard = False
            continue

        # Remove comments
        line = re.sub(r"#.*", "", line)

        # Patterns:
        # "4 Lightning Bolt"
        # "4x Lightning Bolt"
        # "Lightning Bolt x4"
        # "Lightning Bolt"

        qty = 1
        name = line

        # 4x Card
        m = re.match(r"^(\d+)x?\s+(.+)", line)
        if m:
            qty = int(m.group(1))
            name = m.group(2)

        # Card x4
        m = re.match(r"^(.+?)\s+x(\d+)$", line)
        if m:
            name = m.group(1)
            qty = int(m.group(2))

        # Clean set codes
        name = re.sub(r"\(.*?\)", "", name)

        parsed.append((qty, name.strip(), is_sideboard))

    return parsed

# =========================
# 7. ROUTES (MAIN)
# =========================

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def home():
    return render_template("home.html")

@main_bp.route("/import")
def import_page():
    return render_template("import.html")

@main_bp.route("/import_deck", methods=["POST"])
def import_deck():

    import_session = ImportSession(
        created_at=int(time.time()),
        deck_name=request.form.get("deck_name"),
        format=request.form.get("format"),
        all_owned=1 if request.form.get("all_owned") == "1" else 0
    )

    g.db.add(import_session)
    g.db.flush()

    invalid_lines = []

    parsed = parse_deck_list(request.form.get("deck_list", ""))

    # =========================
    # DEV: PREPARE BATCH REQUEST
    # =========================
    names = [clean_card_name(name) for _, name, _ in parsed]

    card_map = get_cards_batch(names)

    MAX_CARDS = 120  # safety limit

    for i, (qty, name, is_sideboard) in enumerate(parsed):
        if i > MAX_CARDS:
            break

        clean_name = clean_card_name(name)

        # =========================
        # DEV: USE BATCH FIRST (FAST)
        # =========================
        data = card_map.get(clean_name.lower())

        # =========================
        # DEV: FALLBACK ONLY IF MISSING
        # =========================
        if not data:
            data = get_card_data(clean_name)

        # =========================
        # DEV: VALIDATE MATCH
        # =========================
        if data and not is_confident_match(clean_name, data.get("name", "")):
            data = None

        # =========================
        # DEV: FINAL FAIL
        # =========================
        if not data:
            suggestion = search_card(clean_name)

            # 🔥 fallback if Scryfall fails
            if not suggestion:
                local = get_local_suggestion(clean_name)
                if local:
                    suggestion = {"name": local}

            if suggestion:
                invalid_lines.append({
                    "original": name,
                    "suggestion": suggestion["name"],
                    "qty": qty,
                    "is_sideboard": is_sideboard
                })
            else:
                invalid_lines.append({
                    "original": name,
                    "suggestion": None
                })
            continue

        image_data = data.get("image_uris") or {}

        g.db.add(ImportCard(
            import_id=import_session.id,
            name=data["name"],
            quantity=qty,
            data=json.dumps(data),
            image_url=image_data.get("normal"),
            is_sideboard=1 if is_sideboard else 0
        ))

    import_session.invalid_lines = json.dumps(invalid_lines)
    
    g.db.commit()

    return redirect(f"/import_review/{import_session.id}")

@main_bp.route("/import_review/<int:import_id>")
def import_review(import_id):

    session_data = g.db.get(ImportSession, import_id)

    if not session_data:
        return redirect("/import")

    cards = g.db.query(ImportCard).filter_by(import_id=import_id).all()

    # =========================
    # FORMAT VALIDATION
    # =========================
    rules = FORMAT_RULES.get(session_data.format, {})

    main_cards = [c for c in cards if not c.is_sideboard]
    total_main = sum(c.quantity for c in main_cards)

    issues = []

    sideboard_cards = [c for c in cards if c.is_sideboard]
    total_side = sum(c.quantity for c in sideboard_cards)
    
    if total_side > 15:
        issues.append(f"Sideboard exceeds 15 cards ({total_side}/15)")

    for c in main_cards:
        c.copy_invalid = False

    # Deck size check
    if "deck_size" in rules:
        if session_data.format == "commander":
            if total_main != 100:
                issues.append(f"Deck must have exactly 100 cards (currently {total_main})")
        else:
            if total_main < rules["deck_size"]:
                issues.append(f"Deck must have at least {rules['deck_size']} cards (currently {total_main})")

    # Copy limit check (ignore basic lands + special rules)
    if "max_copies" in rules:
        for c in main_cards:
            c.copy_invalid = False

            try:
                data = json.loads(c.data)
            except:
                data = {}

            type_line = data.get("type_line", "").lower()
            oracle_text = data.get("oracle_text", "").lower()

            if "basic land" in type_line:
                continue

            if session_data.format == "commander":
                if "any number of" in oracle_text:
                    continue

            if c.quantity > rules["max_copies"]:
                issues.append(f"{c.name} exceeds copy limit ({c.quantity}/{rules['max_copies']})")
                c.copy_invalid = True
            else:
                c.copy_invalid = False

    # ✅ ALWAYS DEFINE invalid_lines
    try:
        invalid_lines = json.loads(session_data.invalid_lines or "[]")
    except:
        invalid_lines = []

    return render_template(
        "import_review.html",
        cards=cards,
        import_id=import_id,
        all_owned=bool(session_data.all_owned),
        detected_format=session_data.format,
        commander_name=session_data.commander_name,
        invalid_lines=invalid_lines,
        validation_issues=issues or [],
        banned=BANNED,
        restricted=RESTRICTED
    )

@main_bp.route("/confirm_import", methods=["POST"])
def confirm_import():

    import_id = int(request.form.get("import_id"))

    session_data = g.db.get(ImportSession, import_id)
    cards = g.db.query(ImportCard).filter_by(import_id=import_id).all()

    commander_name = request.form.get("commander_override")

    deck = Deck(
        name=session_data.deck_name,
        format=session_data.format,
        commander=commander_name
    )

    g.db.add(deck)
    g.db.flush()

    for c in cards:
        data = json.loads(c.data)

        card = g.db.query(Card).filter_by(name=c.name).first()

        if not card:
            image_data = data.get("image_uris") or {}

            card = Card(
                name=c.name,
                quantity=0,
                type_line=data.get("type_line", ""),
                cmc=int(data.get("cmc", 0)),
                color_identity="".join(data.get("color_identity", [])),
                image_url=image_data.get("normal"),
                image_large=image_data.get("large")
            )

            g.db.add(card)
            g.db.flush()

        g.db.add(DeckCard(
            deck_id=deck.id,
            card_id=card.id,
            quantity=c.quantity,
            is_sideboard=c.is_sideboard
        ))

    g.db.commit()

    return redirect(f"/deck/{deck.id}")

@main_bp.route("/collection")
def collection():
    cards = g.db.query(Card).all()
    return render_template("index.html", cards=cards, added=None)


@main_bp.route("/decks")
def decks():
    decks = g.db.query(Deck).all()

    # TEMP: no image logic yet
    for d in decks:

        # commander deck → use commander image
        if d.format == "commander" and d.commander:
            card = g.db.query(Card).filter_by(name=d.commander).first()
            if card:
                d.image = card.image_url or "/static/placeholder.jpg"
                continue

        # fallback → first card in deck
        dc = g.db.query(DeckCard).filter_by(deck_id=d.id).first()

        if dc:
            card = g.db.get(Card, dc.card_id)
            if card and card.image_url:
                d.image = card.image_url
                continue

        # final fallback
        d.image = "/static/placeholder.jpg"

    return render_template("decks.html", decks=decks)


@main_bp.route("/game_formats")
def rules():
    return render_template("game_formats.html")

@main_bp.route("/sets")
def sets_page():
    try:
        res = requests.get("https://api.scryfall.com/sets", timeout=5)
        data = res.json().get("data", [])
    except:
        data = []

    # sort newest first (optional but nicer)
    data = sorted(data, key=lambda x: x.get("released_at", ""), reverse=True)

    return render_template("sets.html", sets=data)

@main_bp.route("/set/<set_code>")
def view_set(set_code):

    try:
        url = f"https://api.scryfall.com/cards/search?q=e:{set_code}&unique=cards"
        res = requests.get(url, timeout=5)
        data = res.json()
        cards = data.get("data", [])
    except:
        cards = []

    return render_template(
        "set_view.html",
        cards=cards,
        set_code=set_code.upper()
    )

# =========================
# 8. ROUTES (DECKS)
# =========================

deck_bp = Blueprint("deck", __name__)

@deck_bp.route("/deck/<int:deck_id>")
def view_deck(deck_id):

    deck = g.db.get(Deck, deck_id)

    # =========================
    # LOAD DECK CARDS
    # =========================
    deck_cards = g.db.query(DeckCard).filter_by(deck_id=deck_id).all()

    # =========================
    # PRELOAD CARDS (card_map)
    # =========================
    card_ids = [dc.card_id for dc in deck_cards]

    if card_ids:
        cards = g.db.query(Card).filter(Card.id.in_(card_ids)).all()
    else:
        cards = []

    card_map = {c.id: c for c in cards}

    # =========================
    # SIDEBOARD
    # =========================
    sideboard = []

    # =========================
    # CARD GROUPS
    # =========================
    groups = {
        "creatures": [],
        "lands": [],
        "instants": [],
        "sorceries": [],
        "artifacts": [],
        "enchantments": [],
        "planeswalkers": [],
        "battles": [],
        "others": []
    }

    for dc in deck_cards:
        card = card_map.get(dc.card_id)

        if not card:
            continue

        card.quantity = dc.quantity

        # =========================
        # SIDEBOARD SPLIT
        # =========================
        if dc.is_sideboard:
            sideboard.append(card)
            continue

        type_line = card.type_line or ""

        if "Creature" in type_line:
            groups["creatures"].append(card)

        elif "Land" in type_line:
            groups["lands"].append(card)

        elif "Instant" in type_line:
            groups["instants"].append(card)

        elif "Sorcery" in type_line:
            groups["sorceries"].append(card)

        elif "Artifact" in type_line:
            groups["artifacts"].append(card)

        elif "Enchantment" in type_line:
            groups["enchantments"].append(card)

        elif "Planeswalker" in type_line:
            groups["planeswalkers"].append(card)

        elif "Battle" in type_line:
            groups["battles"].append(card)

        else:
            groups["others"].append(card)

    total_cards = sum(
        card.quantity for group in groups.values() for card in group
    )

    stats = {
        "total": total_cards,
        "creatures": sum(card.quantity for card in groups["creatures"]),
        "lands": sum(card.quantity for card in groups["lands"]),
        "others": total_cards - (
            sum(card.quantity for card in groups["creatures"]) +
            sum(card.quantity for card in groups["lands"])
        )
    }

    # =========================
    # MANA CURVE
    # =========================
    curve = {}

    # include ALL non-land cards
    for group_name, group_cards in groups.items():
        if group_name == "lands":
            continue

        for card in group_cards:
            cmc = int(card.cmc or 0)

            # cap high values into "7+"
            key = cmc if cmc < 7 else "7+"

            curve[key] = curve.get(key, 0) + card.quantity

    # sort keys properly
    ordered_keys = list(range(0, 7)) + ["7+"]

    curve_labels = []
    curve_values = []

    for key in ordered_keys:
        if key in curve:
            curve_labels.append(str(key))
            curve_values.append(curve[key])

    # =========================
    # COMMANDER IMAGE
    # =========================
    commander_image = None

    if deck.format == "commander" and deck.commander:
        commander_card = g.db.query(Card).filter_by(name=deck.commander).first()

        if commander_card:
            commander_image = commander_card.image_large or commander_card.image_url

    commander_name = deck.commander

    return render_template(
        "deck.html",
        deck=deck,
        creatures=groups["creatures"],
        lands=groups["lands"],
        instants=groups["instants"],
        sorceries=groups["sorceries"],
        artifacts=groups["artifacts"],
        enchantments=groups["enchantments"],
        planeswalkers=groups["planeswalkers"],
        battles=groups["battles"],
        others=groups["others"],
        sideboard=sideboard,
        stats=stats,
        curve_labels=curve_labels,
        curve_values=curve_values,
        commander_name=commander_name,
        commander_image=commander_image,
        archetype_parts=[],
        identity={"title": "", "description": "", "strengths": [], "weaknesses": []},
        format_issues=[],
        warnings=[],
        recommended=[],
        suggestions=[]
    )

@deck_bp.route("/set_commander/<int:deck_id>", methods=["POST"])
def set_commander(deck_id):

    data = request.get_json()
    name = data.get("name")

    deck = g.db.get(Deck, deck_id)

    if not deck:
        return jsonify({"success": False, "error": "Deck not found"}), 404

    # only allow for commander decks
    if deck.format != "commander":
        return jsonify({"success": False, "error": "Not a commander deck"}), 400

    deck.commander = name

    g.db.commit()

    return jsonify({"success": True})

# =========================
# 9. API ROUTES
# =========================

api_bp = Blueprint("api", __name__)

@api_bp.route("/api/card_suggest")
def suggest():
    query = request.args.get("q", "")

    if not query:
        return jsonify([])

    url = f"https://api.scryfall.com/cards/autocomplete?q={query}"
    res = requests.get(url)

    return jsonify(res.json().get("data", []))

@api_bp.route("/api/fix_card", methods=["POST"])
def fix_card():
    data = request.get_json()

    import_id = data.get("import_id")
    fixed = data.get("fixed")
    qty = int(data.get("qty", 1))
    raw = data.get("is_sideboard", 0)
    is_sideboard = 1 if str(raw) in ["1", "True", "true"] else 0

    # =========================
    # FETCH CORRECT DATA
    # =========================
    new_data = get_card_data(fixed)

    if not new_data:
        return jsonify({"success": False})

    image_data = new_data.get("image_uris") or {}

    # =========================
    # CHECK FOR EXISTING CARD
    # =========================
    existing = g.db.query(ImportCard).filter_by(
        import_id=import_id,
        name=new_data["name"],
        is_sideboard=is_sideboard
    ).first()

    if existing:
        existing.quantity += qty
    else:
        g.db.add(ImportCard(
            import_id=import_id,
            name=new_data["name"],
            quantity=qty,
            data=json.dumps(new_data),
            image_url=image_data.get("normal"),
            is_sideboard=is_sideboard
        ))

    # =========================
    # REMOVE FROM INVALID LIST
    # =========================
    session = g.db.get(ImportSession, import_id)

    if not session:
        return jsonify({"success": False})

    try:
        invalid = json.loads(session.invalid_lines or "[]")
    except:
        invalid = []

    invalid = [
        i for i in invalid
        if isinstance(i, dict) and i.get("suggestion") != fixed
    ]

    session.invalid_lines = json.dumps(invalid)

    # =========================
    # COMMIT + RETURN (FIX)
    # =========================
    g.db.commit()

    return jsonify({"success": True})

@api_bp.route("/api/remove_import_card", methods=["POST"])
def remove_import_card():
    data = request.get_json()

    card_id = data.get("card_id")

    card = g.db.get(ImportCard, card_id)

    if not card:
        return jsonify({"success": False})

    g.db.delete(card)
    g.db.commit()

    return jsonify({"success": True})

@api_bp.route("/api/update_import_quantity", methods=["POST"])
def update_import_quantity():
    data = request.get_json()

    card_id = data.get("card_id")
    change = int(data.get("change", 0))

    card = g.db.get(ImportCard, card_id)

    if not card:
        return jsonify({"success": False})

    card.quantity += change

    # prevent negative
    if card.quantity <= 0:
        g.db.delete(card)
        g.db.commit()
        return jsonify({"success": True, "removed": True})

    g.db.commit()

    return jsonify({
        "success": True,
        "quantity": card.quantity
    })

# =========================
# 10. INIT
# =========================

app.register_blueprint(main_bp)
app.register_blueprint(deck_bp)
app.register_blueprint(api_bp)

if __name__ == "__main__":
    app.run(debug=True)
