import { UI } from "./ui.js";
import { API } from "./api.js";
import { AutoSuggest, ImportSuggest } from "./autosuggest.js";
import { Filters } from "./filters.js";

document.addEventListener("DOMContentLoaded", () => {

    AutoSuggest.init();
    ImportSuggest.init();
    Filters.init();

});

// expose globally ONLY if needed
window.UI = UI;
window.API = API;