import { UI } from "./ui.js";
import { API } from "./api.js";
import { AutoSuggest, ImportSuggest } from "./autosuggest.js";
import { Filters } from "./filters.js";
import { updateQty } from "./ui.js";

document.addEventListener("DOMContentLoaded", () => {

    AutoSuggest.init();
    ImportSuggest.init();
    Filters.init();

    // =========================
    // DECK NAVIGATION
    // ========================

    document.querySelectorAll(".deck-card").forEach(card => {
        card.addEventListener("click", () => {
            const id = card.dataset.id;
            window.location = `/deck/${id}`;
        });
    });

    // =========================
    // ADD CARD BUTTON
    // =========================
    const addBtn = document.getElementById("addCardBtn");
    if (addBtn) {
        addBtn.addEventListener("click", () => {
            API.addCard();
        });
    }

    // =========================
    // CARD PREVIEW (NO INLINE JS)
    // =========================
    document.querySelectorAll(".card").forEach(card => {
        card.addEventListener("click", () => {
            UI.preview(card);
        });
    });

    // =========================
    // QUANTITY BUTTONS
    // =========================
    document.querySelectorAll(".qty-btn").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();

            const id = btn.dataset.id;
            const change = parseInt(btn.dataset.change);

            const res = await API.updateQuantity(id, change);

            if (res.success) {
                const el = document.getElementById(`qty-${id}`);
                if (el) el.textContent = res.quantity;
            }
        });
    });

    // =========================
    // MODALS (NO INLINE JS)
    // =========================
    const overlay = document.getElementById("overlay");
    if (overlay) {
        overlay.addEventListener("click", () => UI.closeAll());
    }

    document.querySelectorAll("[data-open-modal]").forEach(btn => {
        btn.addEventListener("click", () => {
            UI.openModal(btn.dataset.openModal);
        });
    });

    document.querySelectorAll("[data-close-modal]").forEach(btn => {
        btn.addEventListener("click", () => {
            UI.closeModal(btn.dataset.closeModal);
        });
    });

    const canvas = document.getElementById("manaChart");

    if (canvas) {
        const ctx = canvas.getContext("2d");

        new Chart(ctx, {
            type: "bar",
            data: {
                labels: window.curveLabels,
                datasets: [{
                    label: "Cards",
                    data: window.curveValues,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }

});

// expose globally ONLY if needed
window.UI = UI;
window.API = API;