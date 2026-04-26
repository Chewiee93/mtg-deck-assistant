// =========================
// UI CONTROLLER
// =========================
import { API } from "./api.js";

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
        let img = cardEl.dataset.preview || cardEl.dataset.image;

        // ✅ HARD FALLBACK
        if (!img || img === "" || img === "null") {
            img = "/static/placeholder.jpg";
        }

        const preview = document.getElementById("previewImage");

        // 🚫 STOP if preview modal doesn't exist
        if (!preview) return;

        preview.onerror = () => {
            preview.src = "/static/placeholder.jpg";
        };

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
    }
};

// =========================
// QUANTITY UPDATE (SEPARATE EXPORT)
// =========================
export function updateQty(id, change) {
    return API.updateQuantity(id, change).then(res => {
        if (res.success) {
            const el = document.getElementById(`qty-${id}`);
            if (el) el.textContent = res.quantity;
        }
    });
}