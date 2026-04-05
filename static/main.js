import { UI } from "./ui.js";
import { API } from "./api.js";
import { AutoSuggest, ImportSuggest } from "./autosuggest.js";
import { Filters } from "./filters.js";
import { updateQty } from "./ui.js";

document.addEventListener("DOMContentLoaded", () => {

    AutoSuggest.init();
    ImportSuggest.init();
    Filters.init();

    // DEV FIX: attach add card button safely (no inline JS)
    const addBtn = document.getElementById("addCardBtn");
    if (addBtn) {
        addBtn.addEventListener("click", () => {
            API.addCard();
        });
    }

    // =========================
    // COLLECTION ACTIONS
    // =========================

    // Quantity buttons
    document.querySelectorAll("[data-action='qty']").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();

            const id = btn.dataset.id;
            const change = parseInt(btn.dataset.change);

            updateQty(id, change);
        });
    });

    // Card preview
    document.querySelectorAll(".card").forEach(card => {
        card.addEventListener("click", () => {
            UI.preview(card);
        });
    });

    // Remove card
    document.querySelectorAll("[data-action='remove']").forEach(btn => {
        btn.addEventListener("click", () => {
            const deckId = btn.dataset.deck;
            const cardId = btn.dataset.card;

            UI.removeCard(deckId, cardId);
        });
    });

    // Mark owned
    document.querySelectorAll("[data-action='owned']").forEach(btn => {
        btn.addEventListener("click", () => {
            const cardId = btn.dataset.card;
            UI.markOwned(cardId);
        });
    });

});

// expose globally ONLY if needed
window.UI = UI;
window.API = API;