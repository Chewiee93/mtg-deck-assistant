// =========================
// API LAYER
// =========================
export const API = {

    // DEV FIX: add logging + force reload so we SEE result
    async addCard() {
        const input = document.getElementById("cardInput");
        const name = input?.value?.trim();

        if (!name) {
            alert("Enter a card name");
            return;
        }

        console.log("Adding card:", name);

        try {
            const res = await fetch("/api/add_card", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ name })
            });

            console.log("Response status:", res.status);

            const data = await res.json();
            console.log("Response data:", data);

            if (data.success) {
                // 🔥 FORCE UI UPDATE (simple + reliable)
                window.location.reload();
            } else {
                alert("Card not found");
            }

        } catch (err) {
            console.error("Add card failed:", err);
            alert("Error adding card");
        }
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