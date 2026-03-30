# Import SQLAlchemy tools to define database structure
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

# Base class that all database models inherit from
Base = declarative_base()


# -------------------------
# CARD MODEL
# -------------------------
class Card(Base):
    __tablename__ = "cards"  # Name of the table in the database

    id = Column(Integer, primary_key=True)  # Unique ID for each card
    name = Column(String)  # Card name (e.g. Lightning Bolt)
    quantity = Column(Integer)  # How many copies you own

    color_identity = Column(String)  # e.g. "R", "U,B"
    type_line = Column(String)  # e.g. "Creature — Elf"

    oracle_text = Column(String)  # Full card rules text (used for role detection)

    image_url = Column(String)  # URL for card image (from Scryfall)
    set_name = Column(String)  # Set the card is from
    image_large = Column(String)

    owned = Column(Integer, default=1)  
    # 1 = you own it
    # 0 = you don’t (used for “missing cards” system)

    cmc = Column(Integer)


# -------------------------
# DECK MODEL
# -------------------------
class Deck(Base):
    __tablename__ = "decks"

    id = Column(Integer, primary_key=True)  # Unique deck ID
    name = Column(String)  # Deck name