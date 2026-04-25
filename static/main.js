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
    // SAVE IMPORT TEXT
    // =========================
    const importForm = document.querySelector("form[action='/import_deck']");
    if (importForm) {
        importForm.addEventListener("submit", () => {
            const input = document.getElementById("deckInput");
            if (input) {
                sessionStorage.setItem("last_import", input.value);
            }
        });
    }

    // =========================
    // RESTORE IMPORT TEXT
    // =========================
    const deckInput = document.getElementById("deckInput");
    if (deckInput) {
        const saved = sessionStorage.getItem("last_import");
        if (saved) {
            deckInput.value = saved;
        }
    }

    // =========================
    // CLEAR IMPORT LIST
    // =========================
    const clearBtn = document.getElementById("clearImportBtn");

    clearBtn?.addEventListener("click", () => {
        if (!deckInput) return;

        deckInput.value = "";
        sessionStorage.removeItem("last_import");

        // update UI immediately
        const event = new Event("input");
        deckInput.dispatchEvent(event);
    });

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
    // CARD PREVIEW (SMOOTH HOVER)
    // =========================
    let hoverTimer = null;
    let leaveTimer = null;

    document.querySelectorAll(".card, .grid-card").forEach(card => {

        // CLICK (mobile safe)
        card.addEventListener("click", (e) => {
            if (e.target.closest("button")) return;
            UI.preview(card);
        });

        // HOVER ENTER
        card.addEventListener("mouseenter", () => {

            // Cancel any closing
            clearTimeout(leaveTimer);

            // Start hover delay
            hoverTimer = setTimeout(() => {
                UI.preview(card);
            }, 150); // ⏱ delay before showing

        });

        // HOVER LEAVE
        card.addEventListener("mouseleave", () => {

            // Cancel hover if not triggered yet
            clearTimeout(hoverTimer);

            // Delay closing slightly (prevents flicker)
            leaveTimer = setTimeout(() => {
                UI.closeModal("previewModal");
            }, 120);

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
                if (res.quantity === 0) {
                    // DEV FIX: remove card from DOM
                    const cardEl = document.getElementById(`card-${id}`);
                    if (cardEl) cardEl.remove();
                    return;
                }

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

    // =========================
    // IMPORT FIX BUTTONS
    // =========================
    document.querySelectorAll(".fix-btn").forEach(btn => {
        btn.addEventListener("click", async () => {

            btn.disabled = true;
            btn.textContent = "Fixing...";

            const original = btn.dataset.original;
            const fix = btn.dataset.fix;
            const importId = btn.dataset.import;

            // =========================
            // CALL BACKEND FIX
            // =========================
            const res = await fetch("/api/fix_card", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    import_id: importId,
                    fixed: fix,
                    qty: btn.dataset.qty,
                    is_sideboard: btn.dataset.sideboard === "True" ? 1 : 0
                })
            });

            const data = await res.json();

            if (!data.success) {
                alert("Fix failed");
                return;
            }

            // =========================
            // CLEAN UX: reload review
            // =========================
            window.location.reload();
        });
    });

    // =========================
    // REMOVE IMPORT CARD
    // =========================
    document.querySelectorAll(".remove-import-btn").forEach(btn => {
        btn.addEventListener("click", async () => {

            const id = btn.dataset.id;

            const res = await fetch("/api/remove_import_card", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ card_id: id })
            });

            const data = await res.json();

            if (!data.success) {
                alert("Failed to remove");
                return;
            }

            // remove card from UI
            const cardEl = btn.closest(".grid-card");
            if (cardEl) cardEl.remove();
        });
    });

    // =========================
    // IMPORT QUANTITY BUTTONS
    // =========================
    document.querySelectorAll(".import-qty-btn").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();

            const id = btn.dataset.id;
            const change = parseInt(btn.dataset.change);

            const res = await fetch("/api/update_import_quantity", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    card_id: id,
                    change: change
                })
            });

            const data = await res.json();

            if (!data.success) return;

            // removed case
            if (data.removed) {
                const el = btn.closest(".grid-card");
                if (el) el.remove();
                updateImportTotals();
                return;
            }

            // update quantity
            const el = document.getElementById(`import-qty-${id}`);
            if (el) el.textContent = data.quantity;

            updateImportTotals();
        });
    });

    // =========================
    // SET COMMANDER
    // =========================
    document.querySelectorAll("[data-action='set-commander']").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();

            const deckId = btn.dataset.deck;
            const name = btn.dataset.card;

            await fetch(`/set_commander/${deckId}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ name })
            });

            // reload to reflect change
            window.location.reload();
        });
    });

    // =========================
    // LIVE CARD COUNT
    // =========================
    const deckInputEl = document.getElementById("deckInput");
    const cardCountEl = document.getElementById("cardCount");

    function updateCardCount() {
        if (!deckInputEl || !cardCountEl) return;

        const lines = deckInputEl.value.split("\n");

        let mainTotal = 0;
        let sideTotal = 0;
        let isSideboard = false;

        lines.forEach(line => {
            line = line.trim();
            if (!line) return;

            const lower = line.toLowerCase();

            // Detect sideboard start
            if (lower.match(/^(sideboard|sb:|\/\/ sideboard)/)) {
                isSideboard = true;
                return;
            }

            // Detect mainboard reset
            if (["mainboard", "// main", "deck"].includes(lower)) {
                isSideboard = false;
                return;
            }

            const match = line.match(/^(\d+)x?\s+/i);
            const qty = match ? parseInt(match[1]) : 1;

            if (isSideboard) {
                sideTotal += qty;
            } else {
                mainTotal += qty;
            }
        });

        const validation = getValidation(mainTotal);

        cardCountEl.textContent =
            `Main: ${mainTotal} ${getTarget()} ${validation} | Sideboard: ${sideTotal}`;

    }

    const formatSelect = document.querySelector("select[name='format']");

    deckInputEl?.addEventListener("input", updateCardCount);
    formatSelect?.addEventListener("change", updateCardCount);

    // run AFTER both exist
    updateCardCount();
    updateImportTotals();

    function getTarget() {
        if (!formatSelect) return "";

        const f = formatSelect.value;

        if (f === "commander") return "/ 100";
        if (f === "modern" || f === "standard") return "/ 60+";

        return "";
    }

    function getValidation(mainTotal) {
            if (!formatSelect) return "";

            const f = formatSelect.value;

            if (f === "commander") {
                if (mainTotal === 100) return "✅ Valid";
                if (mainTotal > 100) return "❌ Too many cards";
                return "❌ Too few cards";
            }

            if (f === "modern" || f === "standard") {
                if (mainTotal >= 60) return "✅ Valid";
                return "❌ Too small";
            }

            return ""; // casual = no rules
        }

    function updateImportTotals() {
        const qtyEls = document.querySelectorAll("[id^='import-qty-']");

        let total = 0;

        qtyEls.forEach(el => {
            total += parseInt(el.textContent) || 0;
        });

        const totalEl = document.getElementById("importTotals");
        if (totalEl) {
            totalEl.textContent = `Total cards: ${total}`;
        }
    }

});

// expose globally ONLY if needed
window.UI = UI;
window.API = API;