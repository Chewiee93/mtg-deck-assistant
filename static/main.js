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
    // SETS FILTER / SORT
    // =========================
    function initSetFilters() {

        const search = document.getElementById("searchInput");
        const year = document.getElementById("yearFilter");
        const sort = document.getElementById("setSort");
        const formatFilter = document.getElementById("formatFilter");
        const type = document.getElementById("typeFilter");

        if (!search || !year || !sort) return;

        const grid = document.querySelector(".grid");
        const cards = Array.from(document.querySelectorAll(".grid-card"));

        function apply() {

            const searchVal = search.value.toLowerCase();
            const yearVal = year.value;
            const formatVal = formatFilter?.value;
            const typeVal = type?.value;

            let filtered = cards.filter(card => {

                const name = card.dataset.name;
                const cardYear = card.dataset.year;
                const cardType = card.dataset.type;

                // SEARCH
                if (searchVal && !name.includes(searchVal)) return false;

                // YEAR
                if (yearVal && cardYear !== yearVal) return false;

                // TYPE
                if (typeVal && cardType !== typeVal) return false;

                // =========================
                // FORMAT FILTER (IMPROVED)
                // =========================
                if (formatVal === "modern") {
                    const yearNum = parseInt(cardYear || "0");

                    // Must be modern-era AND real playable set types
                    if (
                        !yearNum ||
                        yearNum < 2003 ||
                        !["core", "expansion"].includes(cardType)
                    ) {
                        return false;
                    }
                }

                if (formatVal === "standard") {
                    const yearNum = parseInt(cardYear || "0");
                    const currentYear = new Date().getFullYear();

                    // Only recent + standard-style sets
                    if (
                        !yearNum ||
                        yearNum < currentYear - 3 ||
                        !["core", "expansion"].includes(cardType)
                    ) {
                        return false;
                    }
                }

                return true;
            });

            // SORT
            if (sort.value === "az") {
                filtered.sort((a, b) =>
                    a.dataset.name.localeCompare(b.dataset.name)
                );
            } else {
                filtered.sort((a, b) =>
                    (b.dataset.year || "").localeCompare(a.dataset.year || "")
                );
            }

            // REBUILD GRID
            grid.innerHTML = "";
            filtered.forEach(card => grid.appendChild(card));
        }

        search.addEventListener("input", apply);
        year.addEventListener("change", apply);
        sort.addEventListener("change", apply);
        formatFilter?.addEventListener("change", apply);
        type?.addEventListener("change", apply);

    }

    initSetFilters();

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
    let currentPreview = null;

    document.querySelectorAll(".card img, .grid-card img").forEach(img => {

        let isTouchDevice = false;

        window.addEventListener("touchstart", () => {
            isTouchDevice = true;
        }, { once: true });

        card.addEventListener("click", (e) => {
            if (!isTouchDevice) return;
            if (e.target.closest("button")) return;

            const card = img.closest(".card, .grid-card");

            UI.preview(card);
            currentPreview = card;
        });

        // HOVER ENTER
        img.addEventListener("pointerenter", (e) => {

            if (card.contains(e.relatedTarget)) return;

            clearTimeout(leaveTimer);

            if (currentPreview === card) return;

            hoverTimer = setTimeout(() => {
                UI.preview(card);
                currentPreview = card;
            }, 250);
        });

        // HOVER LEAVE
        img.addEventListener("pointerleave", (e) => {

            if (card.contains(e.relatedTarget)) return;

            clearTimeout(hoverTimer);

            leaveTimer = setTimeout(() => {
                document.getElementById("previewModal")?.classList.add("hidden");
                currentPreview = null;
            }, 150);
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
                updateImportValidation();
                updateImportHighlights();
                return;
            }

            // update quantity
            const el = document.getElementById(`import-qty-${id}`);
            if (el) el.textContent = data.quantity;

            updateImportTotals();
            updateImportValidation();
            updateImportHighlights();
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

    // =========================
    // INIT IMPORT REVIEW STATE
    // =========================
    updateImportTotals();
    updateImportValidation();
    updateImportHighlights();

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
        const cards = document.querySelectorAll(".grid-card");

        let main = 0;
        let side = 0;

        cards.forEach(card => {
            const qtyEl = card.querySelector("[id^='import-qty-']");
            if (!qtyEl) return;

            const qty = parseInt(qtyEl.textContent) || 0;
            const isSideboard = card.dataset.sideboard === "1";

            if (isSideboard) {
                side += qty;
            } else {
                main += qty;
            }
        });

        // =========================
        // UPDATE TOTALS DISPLAY
        // =========================
        const totalEl = document.getElementById("importTotals");
        if (totalEl) {
            totalEl.textContent = `Main: ${main} | Sideboard: ${side}`;
        }

        // =========================
        // UPDATE SIDEBOARD HEADER
        // =========================
        const header = document.getElementById("sideboardHeader");
        if (header) {
            header.textContent = `Sideboard (${side} / 15)`;
        }

        // =========================
        // UPDATE MAIN HEADER
        // =========================
        const mainHeader = document.getElementById("mainHeader");
        if (mainHeader) {
            mainHeader.textContent = `Main Deck (${main})`;
        }
    }

    function updateImportValidation() {
        const cards = document.querySelectorAll(".grid-card");

        let total = 0;
        const counts = {};
        const issues = [];
        let sideTotal = 0;

        cards.forEach(card => {
            const qtyEl = card.querySelector("[id^='import-qty-']");
            if (!qtyEl) return;

            const qty = parseInt(qtyEl.textContent) || 0;
            const name = card.dataset.name;
            const isSideboard = card.dataset.sideboard === "1";

            // count ALL cards (main + sideboard for copy rules)
            counts[name] = (counts[name] || 0) + qty;

            // only mainboard affects deck size
            if (!isSideboard) {
                total += qty;
            } else {
                sideTotal += qty;
            }
        });

        // =========================
        // FORMAT RULES
        // =========================
        const formatEl = document.getElementById("importFormat");
        const format = formatEl?.textContent?.toLowerCase() || "casual";

        if (format === "commander") {
            if (total > 100) {
                issues.push(`Deck has too many cards (${total}/100)`);
            } else if (total < 100) {
                issues.push(`Deck has too few cards (${total}/100)`);
            }
        }

        if (format === "modern" || format === "standard") {
            if (total < 60) {
                issues.push(`Deck too small (${total}/60+)`);
            } else if (total > 90) {
                issues.push(`Deck unusually large (${total}/60+)`);
            }
        }

        // =========================
        // SIDEBBOARD SIZE RULE
        // =========================
        if (sideTotal > 15) {
            issues.push(`Sideboard too large (${sideTotal}/15)`);
        }

        // =========================
        // COPY LIMITS
        // =========================
        const maxCopies = format === "commander" ? 1 : 4;

        Object.entries(counts).forEach(([name, qty]) => {

            // basic land check (same as highlight)
            const lower = name.toLowerCase();

            const isBasic =
                lower === "plains" ||
                lower === "island" ||
                lower === "swamp" ||
                lower === "mountain" ||
                lower === "forest";

            if (isBasic) return;

            if (qty > maxCopies) {
                issues.push(`${name} exceeds copy limit (${qty}/${maxCopies})`);
            }
        });

        // =========================
        // UPDATE UI
        // =========================
        const panel = document.getElementById("liveValidationPanel");

        if (!panel) return;

        if (!issues.length) {
            panel.innerHTML = "<strong>✅ Deck is valid</strong>";
            return;
        }

        panel.innerHTML =
            "<strong>⚠ Deck Issues:</strong>" +
            issues.map(i => `<div>• ${i}</div>`).join("");
    }

    function updateImportHighlights() {
        const cards = document.querySelectorAll(".grid-card");

        const counts = {};
        let total = 0;

        cards.forEach(card => {
            const qtyEl = card.querySelector("[id^='import-qty-']");
            if (!qtyEl) return;

            const qty = parseInt(qtyEl.textContent) || 0;
            const name = card.dataset.name;
            const isSideboard = card.dataset.sideboard === "1";

            // count ALL for copy limits
            counts[name] = (counts[name] || 0) + qty;

            // only mainboard affects total
            if (!isSideboard) {
                total += qty;
            }
        });

        // detect format safely
        const formatEl = document.getElementById("importFormat");
        const format = formatEl?.textContent?.toLowerCase() || "casual";

        const maxCopies = format === "commander" ? 1 : 4;

        // =========================
        // APPLY HIGHLIGHTS
        // =========================
        cards.forEach(card => {
            const name = card.dataset.name;

            // remove existing dynamic highlight
            card.classList.remove("copy-invalid-live");

            // skip if backend already marked banned/restricted
            if (card.classList.contains("banned") ||
                card.classList.contains("restricted")) {
                return;
            }

            const qty = counts[name] || 0;

            // basic land check (simple)
            const lower = name.toLowerCase();

            const isBasic =
                lower === "plains" ||
                lower === "island" ||
                lower === "swamp" ||
                lower === "mountain" ||
                lower === "forest";

            if (isBasic) return;

            if (qty > maxCopies) {
                card.classList.add("copy-invalid-live");
            }
        });

        // =========================
        // DECK SIZE VISUAL
        // =========================
        const container = document.querySelector(".grid");

        if (container) {
            container.classList.remove("deck-invalid-live");

            const formatEl = document.getElementById("importFormat");
            const format = formatEl?.textContent?.toLowerCase() || "casual";

            if (format === "commander" && total !== 100) {
                container.classList.add("deck-invalid-live");
            }

            if ((format === "modern" || format === "standard") && total < 60) {
                container.classList.add("deck-invalid-live");
            }
        }
    }

    // =========================
    // ADD CARD FROM SET VIEW
    // =========================
    document.querySelectorAll(".add-set-card-btn").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();

            const name = btn.dataset.name;

            const res = await fetch("/api/add_card", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ name })
            });

            const data = await res.json();

            if (data.success) {
                btn.textContent = "✔";
                btn.disabled = true;
            } else {
                alert("Failed to add card");
            }
        });
    });

    // =========================
    // SET TYPE FILTER
    // =========================
    function initSetTypeFilter() {

        const filter = document.getElementById("typeFilter");
        if (!filter) return;

        const cards = document.querySelectorAll(".grid-card");

        filter.addEventListener("change", () => {
            const val = filter.value;

            cards.forEach(card => {
                const type = card.dataset.type || "";

                if (!val || type.includes(val)) {
                    card.style.display = "";
                } else {
                    card.style.display = "none";
                }
            });
        });
    }

    initSetTypeFilter();

    // =========================
    // LOAD MORE (SET VIEW)
    // =========================
    document.querySelectorAll(".load-more-btn").forEach(btn => {

        btn.addEventListener("click", async () => {

            const url = btn.dataset.next;
            if (!url) return;

            btn.disabled = true;
            btn.textContent = "Loading...";

            try {
                const res = await fetch(`/set/temp?page_url=${encodeURIComponent(url)}`);
                const html = await res.text();

                // parse returned HTML
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, "text/html");

                const newCards = doc.querySelectorAll(".grid-card");

                const grid = document.querySelector(".grid");

                // insert BEFORE button container
                const container = btn.parentElement;

                newCards.forEach(card => {
                    grid.appendChild(card);
                });

                // 🔥 RE-APPLY FILTERS AFTER ADDING NEW CARDS
                Filters.apply();

                // update next page
                const nextBtn = doc.querySelector(".load-more-btn");

                if (nextBtn) {
                    btn.dataset.next = nextBtn.dataset.next;

                    // keep button at bottom (no gap)
                    container.appendChild(btn);

                    btn.disabled = false;
                    btn.textContent = "Load More →";
                } else {
                    container.remove(); // remove whole section
                }

            } catch (err) {
                console.error("Load more failed:", err);
                btn.textContent = "Error";
            }

        });

    });
});

// expose globally ONLY if needed
window.UI = UI;
window.API = API;