// =========================
// UI CONTROLLER
// =========================
export const UI = {

    openModal(id) {
        document.getElementById("overlay")?.classList.remove("hidden");
        document.getElementById(id)?.classList.remove("hidden");
    },

    closeAll() {
        document.getElementById("overlay")?.classList.add("hidden");

        ["cardModal", "previewModal"].forEach(id => {
            document.getElementById(id)?.classList.add("hidden");
        });
    },

    closeModal(id) {
        document.getElementById(id)?.classList.add("hidden");
        document.getElementById("overlay")?.classList.add("hidden");
    },

    preview(cardEl) {
        const img = cardEl.dataset.preview || cardEl.dataset.image;
        if (!img) return;

        const preview = document.getElementById("previewImage");
        preview.src = img;

        this.openModal("previewModal");
    },

    async removeCard(deckId, cardId) {
        await API.removeFromDeck(deckId, cardId);

        const el = document.getElementById(`card-${cardId}`);
        if (el) el.remove();
    },

    async markOwned(cardId) {
        await API.markOwned(cardId);

        const el = document.getElementById(`card-${cardId}`);
        if (el) el.classList.remove("missing");
    },

    window.updateQty = async function(id, change) {
        const res = await API.updateQuantity(id, change);

        if (res.success) {
            const el = document.getElementById(`qty-${id}`);
            if (el) el.textContent = res.quantity;
        }
    }

};