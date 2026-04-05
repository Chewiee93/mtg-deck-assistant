import { UI } from "./ui.js";
import { API } from "./api.js";
import { AutoSuggest, ImportSuggest } from "./autosuggest.js";
import { Filters } from "./filters.js";

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

});

// expose globally ONLY if needed
window.UI = UI;
window.API = API;