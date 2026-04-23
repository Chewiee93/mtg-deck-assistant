# PROJECT CONTEXT – MTG Deck Assistant

## 🔧 Environment

* Hosted on **Render**
* Uses **Flask + SQLite**
* Database is **ephemeral** (resets on deploy)
* No persistent storage yet

👉 IMPORTANT:

* Do NOT suggest solutions that rely on long-term DB storage unless explicitly asked
* Assume DB is temporary per deployment

---

## 🧱 Current Architecture

* Backend: Flask (single `app.py`)
* DB: SQLAlchemy models (Card, Deck, DeckCard, ImportSession, ImportCard)
* Frontend:

  * HTML templates
  * Modular JS (`main.js`, `api.js`, `autosuggest.js`, etc.)
  * CSS split into multiple files

👉 Rules:

* No inline JavaScript
* Keep JS, HTML, CSS separated
* Routes should stay thin
* Logic belongs in services

---

## ⚙️ Current Features

* Deck import (batch Scryfall API)
* Import review system with failed cards + suggestions
* Autosuggest (Scryfall autocomplete)
* Deck viewer with grouping + stats
* Commander support
* Collection tracking

---

## ⚠️ Known Constraints

* No persistent DB
* API-dependent for card data
* Import must be **fast (avoid many API calls)**
* Avoid heavy loops / repeated API calls
* Avoid over-engineering

---

## 🎯 Project Goal

Build a tool that can:

1. Store a user’s card collection
2. Understand MTG formats (Commander, Modern, etc.)
3. Enforce rules (deck size, copy limits, banned cards)
4. Automatically generate decks from a collection
5. Suggest improvements and upgrades

---

## 🧠 Development Level

* Developer is **learning / novice**
* Priorities:

  * Stability over cleverness
  * Clear structure over complexity
  * Step-by-step improvements

👉 DO NOT:

* Suggest overly complex patterns
* Introduce unnecessary abstractions
* Rewrite large sections without reason

---

## 🔁 How to Respond (IMPORTANT)

When helping:

* Be **consistent** (do not change approach mid-solution)
* Work with existing structure
* Give **exact placement instructions**
* Avoid multiple alternative solutions unless asked
* Fix root cause, not symptoms

---

## 🚫 Common Mistakes to Avoid

* Assuming persistent database
* Suggesting full rewrites
* Mixing frontend/backend responsibilities
* Adding unnecessary features before core stability

---

## ✅ Preferred Approach

* Small, targeted fixes
* Clear before/after code
* Minimal disruption to current system
* Build incrementally

---

## 📌 Summary

This is a **learning project becoming a real tool**.

Focus on:

* making it reliable
* keeping it understandable
* improving it step-by-step

NOT:

* making it “perfect” immediately

---
