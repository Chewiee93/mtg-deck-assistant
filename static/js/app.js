// =========================
// APP CONFIG (FROM BACKEND)
// =========================
// Injected via Jinja in HTML
// Example:
// window.APP_CONFIG = { added: "{{ added }}" }
const CONFIG = window.APP_CONFIG || {};


// =========================
// UI CONTROLLER
// Handles visual interactions only
// =========================
const UI = {

    openModal(id) {
        const modal = document.getElementById(id);
        const overlay = document.getElementById("overlay");

        if (overlay) overlay.classList.remove("hidden");
        if (modal) modal.classList.remove("hidden");
    },

    closeAll() {
        const overlay = document.getElementById("overlay");

        // Close modals safely
        ["cardModal", "previewModal"].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add("hidden");
        });

        if (overlay) overlay.classList.add("hidden");
    },

    preview(cardEl) {
        const previewImg = cardEl.dataset.preview;
        const fallback = cardEl.dataset.image;

        const img = previewImg || fallback;
        if (!img) return;

        const preview = document.getElementById("previewImage");
        preview.src = img;

        this.openModal("previewModal");
    }
};

// =========================
// AUTOSUGGEST SYSTEM
// =========================
const AutoSuggest = {

    init() {
        this.input = document.getElementById("cardInput");
        this.box = document.getElementById("suggestionsBox");

        if (!this.input || !this.box) return;

        this.input.addEventListener("input", () => {
            clearTimeout(this.timer);

            this.timer = setTimeout(() => {
                this.handleInput();
            }, 300); // 300ms delay
        });
    },

    async handleInput() {
        const query = this.input.value.trim();

        // Hide if too short
        if (query.length < 2) {
            this.box.innerHTML = "";
            this.box.classList.add("hidden");
            return;
        }

        try {
            const res = await fetch(`/api/card_suggest?q=${query}`);
            const data = await res.json();

            this.render(data);

        } catch (err) {
            console.error("Autosuggest failed:", err);
        }
    },

    render(list) {
        this.box.innerHTML = "";

        if (!list.length) {
            this.box.classList.add("hidden");
            return;
        }

        list.forEach(name => {
            const div = document.createElement("div");
            div.textContent = name;

            div.onclick = () => {
                this.input.value = name;
                this.box.classList.add("hidden");
            };

            this.box.appendChild(div);
        });

        this.box.classList.remove("hidden");
    }
};

// =========================
// API LAYER
// Handles ALL server communication
// =========================
const API = {

    // ---- Add Card ----
    async addCard() {
        const input = document.getElementById("cardInput");
        const name = input.value.trim();

        if (!name) {
            alert("Enter a card name");
            return;
        }

        try {
            const res = await fetch("/api/add_card", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name })
            });

            const data = await res.json();

            if (!data.success) {
                alert("Card not found");
                return;
            }

            // Simple approach for now
            location.reload();

        } catch (err) {
            console.error("Add card failed:", err);
            alert("Network error");
        }
    },


    // ---- Update Quantity ----
    async updateQuantity(id, change) {
        console.log("CLICKED", id, change);

        try {
            const res = await fetch("/api/update_quantity", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    card_id: id,
                    change: change
                })
            });

            const data = await res.json();

            if (!data.success) {
                console.error("Update failed:", data);
                alert("Update failed");
                return;
            }

            const qtyEl = document.getElementById(`qty-${id}`);
            if (qtyEl) {
                qtyEl.textContent = data.quantity;
            }

            // Remove card visually if quantity hits 0
            if (data.quantity === 0) {
                const cardEl = document.getElementById(`card-${id}`);
                if (cardEl) {
                    cardEl.style.opacity = "0";
                    setTimeout(() => cardEl.remove(), 200);
                }
            }

        } catch (err) {
            console.error("Quantity update failed:", err);
        }
    }
};


// =========================
// FILTERING SYSTEM
// Handles search + color filtering
// =========================
const Filters = {

    init() {
        const searchInput = document.getElementById("searchInput");
        const colorFilter = document.getElementById("colorFilter");

        if (searchInput) searchInput.addEventListener("input", this.apply);
        if (colorFilter) colorFilter.addEventListener("change", this.apply);
    },

    apply() {
        const search = document.getElementById("searchInput").value.toLowerCase();
        const color = document.getElementById("colorFilter").value;

        document.querySelectorAll(".card").forEach(card => {

            const name = card.dataset.name || "";
            const cardColors = card.dataset.color || "";

            const matchesSearch = name.includes(search);
            const matchesColor = !color || cardColors.includes(color);

            card.style.display = (matchesSearch && matchesColor)
                ? "block"
                : "none";
        });
    }
};

// =========================
// IMPORT AUTOSUGGEST
// =========================
const ImportSuggest = {

    init() {
        this.input = document.getElementById("deckInput");
        this.box = document.getElementById("importSuggestions");

        if (!this.input || !this.box) return;

        this.input.addEventListener("input", () => this.handleInput());
    },

    getCurrentLine() {
        const pos = this.input.selectionStart;
        const text = this.input.value;

        const start = text.lastIndexOf("\n", pos - 1) + 1;
        const end = text.indexOf("\n", pos);

        return text.substring(start, end === -1 ? text.length : end);
    },

    async handleInput() {
        const line = this.getCurrentLine().trim();

        // Expect format: "4 Lightning Bolt"
        const parts = line.split(" ", 2);

        if (parts.length < 2) {
            this.hide();
            return;
        }

        const namePart = parts[1];

        if (namePart.length < 2) {
            this.hide();
            return;
        }

        try {
            const res = await fetch(`/api/card_suggest?q=${namePart}`);
            const data = await res.json();

            this.render(data);

        } catch (err) {
            console.error("Import suggest failed:", err);
        }
    },

    render(list) {
        this.box.innerHTML = "";

        if (!list.length) {
            this.hide();
            return;
        }

        list.forEach(name => {
            const div = document.createElement("div");
            div.textContent = name;

            div.onclick = () => this.applySuggestion(name);

            this.box.appendChild(div);
        });

        this.show();
    },

    applySuggestion(name) {
        const pos = this.input.selectionStart;
        const text = this.input.value;

        const start = text.lastIndexOf("\n", pos - 1) + 1;
        const end = text.indexOf("\n", pos);

        const line = text.substring(start, end === -1 ? text.length : end);
        const parts = line.split(" ", 2);

        if (parts.length < 2) return;

        const qty = parts[0];

        const newLine = `${qty} ${name}`;

        this.input.value =
            text.substring(0, start) +
            newLine +
            text.substring(end === -1 ? text.length : end);

        this.hide();
    },

    show() {
        this.box.classList.remove("hidden");
    },

    hide() {
        this.box.classList.add("hidden");
    }
};


// =========================
// INITIALISATION
// Runs once DOM is ready
// =========================
document.addEventListener("DOMContentLoaded", () => {

    AutoSuggest.init();

    ImportSuggest.init();

    // Init filters
    Filters.init();

    // Example: react to backend flags
    if (CONFIG.added === "True") {
        UI.closeModal("cardModal");
    }

});

window.API = API;
window.UI = UI;