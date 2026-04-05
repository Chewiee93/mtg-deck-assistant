// =========================
// API LAYER
// =========================
export const API = {

    async addCard() {
        const input = document.getElementById("cardInput");
        const name = input?.value?.trim();

        if (!name) return;

        const res = await fetch("/api/add_card", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ name })
        });

        input.value = ""; // clear after add

        return res.json();
         
    },

    async updateQuantity(id, change) {
        const res = await fetch("/api/update_quantity", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ card_id: id, change })
        });

        return res.json();
    },

    async suggest(query) {
        const res = await fetch(`/api/card_suggest?q=${query}`);
        return res.json();
    },

    async removeFromDeck(deckId, cardId) {
    const res = await fetch(`/api/remove_from_deck/${deckId}/${cardId}`);
    return res.json();
    },

    async markOwned(cardId) {
        const res = await fetch(`/api/mark_owned/${cardId}`);
        return res.json();
    },

};