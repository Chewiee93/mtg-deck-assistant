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

# =========================
# 6. IMPORT LOGIC
# =========================

def parse_deck_list(text):
    lines = text.split("\n")
    parsed = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parts = line.split(" ", 1)

        if len(parts) == 2 and parts[0].isdigit():
            qty = int(parts[0])
            name = parts[1]
        else:
            qty = 1
            name = line

        parsed.append((qty, name))

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

    parsed = parse_deck_list(request.form.get("deck_list", ""))

    for qty, name in parsed:
        data = get_card_data(name)

        if not data:
            continue

        g.db.add(ImportCard(
            import_id=import_session.id,
            name=data["name"],
            quantity=qty,
            data=json.dumps(data),
            image_url=data.get("image_uris", {}).get("normal")
        ))

    g.db.commit()

    return redirect(f"/import_review/{import_session.id}")

@main_bp.route("/import_review/<int:import_id>")
def import_review(import_id):

    session_data = g.db.get(ImportSession, import_id)
    cards = g.db.query(ImportCard).filter_by(import_id=import_id).all()

    return render_template(
        "import_review.html",
        cards=cards,
        import_id=import_id,
        all_owned=bool(session_data.all_owned)
    )

@main_bp.route("/confirm_import", methods=["POST"])
def confirm_import():

    import_id = int(request.form.get("import_id"))

    session_data = g.db.get(ImportSession, import_id)
    cards = g.db.query(ImportCard).filter_by(import_id=import_id).all()

    deck = Deck(
        name=session_data.deck_name,
        format=session_data.format
    )

    g.db.add(deck)
    g.db.flush()

    for c in cards:
        data = json.loads(c.data)

        card = Card(
            name=c.name,
            quantity=c.quantity,
            type_line=data.get("type_line", ""),
            cmc=int(data.get("cmc", 0))
        )

        g.db.add(card)
        g.db.flush()

        g.db.add(DeckCard(
            deck_id=deck.id,
            card_id=card.id,
            quantity=c.quantity
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
        d.image = "/static/placeholder.jpg"

    return render_template("decks.html", decks=decks)


@main_bp.route("/rules")
def rules():
    return render_template("rules.html")

# =========================
# 8. ROUTES (DECKS)
# =========================

deck_bp = Blueprint("deck", __name__)

@deck_bp.route("/deck/<int:deck_id>")
def view_deck(deck_id):
    deck = g.db.get(Deck, deck_id)

    return render_template(
        "deck.html",
        deck=deck,
        creatures=[],
        lands=[],
        others=[],
        sideboard=[],
        stats={"total": 0, "creatures": 0, "lands": 0, "others": 0},
        curve_labels=[],
        curve_values=[],
        commander_image=None,
        archetype_parts=[],
        identity={"title": "", "description": "", "strengths": [], "weaknesses": []},
        format_issues=[],
        warnings=[],
        recommended=[],
        suggestions=[]
    )

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

# =========================
# 10. INIT
# =========================

app.register_blueprint(main_bp)
app.register_blueprint(deck_bp)
app.register_blueprint(api_bp)

if __name__ == "__main__":
    app.run(debug=True)
