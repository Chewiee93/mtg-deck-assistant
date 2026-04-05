import { API } from "./api.js";

// =========================
// SHARED HELPER
// =========================
function debounce(fn, delay = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

// =========================
// SINGLE INPUT AUTOSUGGEST
// =========================
export const AutoSuggest = {

    init() {
        this.input = document.getElementById("cardInput");
        this.box = document.getElementById("suggestionsBox");

        if (!this.input || !this.box) return;

        this.input.addEventListener("input",
            debounce(() => this.handle())
        );
    },

    async handle() {
        const query = this.input.value.trim();
        if (query.length < 2) return this.hide();

        const list = await API.suggest(query);
        this.render(list);
    },

    render(list) {
        this.box.innerHTML = "";

        if (!list.length) return this.hide();

        list.forEach(name => {
            const div = document.createElement("div");
            div.textContent = name;

            div.onclick = () => {
                this.input.value = name;
                this.hide();
            };

            this.box.appendChild(div);
        });

        this.box.classList.remove("hidden");
    },

    hide() {
        this.box.classList.add("hidden");
    }
};


// =========================
// IMPORT AUTOSUGGEST
// =========================
export const ImportSuggest = {

    init() {
        this.input = document.getElementById("deckInput");
        this.box = document.getElementById("importSuggestions");

        if (!this.input || !this.box) return;

        this.input.addEventListener("input",
            debounce(() => this.handle(), 250)
        );
    },

    getLine() {
        const pos = this.input.selectionStart;
        const text = this.input.value;

        const start = text.lastIndexOf("\n", pos - 1) + 1;
        const end = text.indexOf("\n", pos);

        return text.substring(start, end === -1 ? text.length : end);
    },

    async handle() {
        const line = this.getLine().trim();

        let name = line;
        const parts = line.split(" ");

        if (parts.length > 1 && !isNaN(parts[0])) {
            name = parts.slice(1).join(" ");
        }

        if (name.length < 2) return this.hide();

        const list = await API.suggest(name);
        this.render(list);
    },

    render(list) {
        this.box.innerHTML = "";

        if (!list.length) return this.hide();

        list.forEach(name => {
            const div = document.createElement("div");
            div.textContent = name;
            div.onclick = () => this.apply(name);
            this.box.appendChild(div);
        });

        this.box.classList.remove("hidden");
    },

    apply(name) {
        const pos = this.input.selectionStart;
        const text = this.input.value;

        const start = text.lastIndexOf("\n", pos - 1) + 1;
        const end = text.indexOf("\n", pos);

        const line = text.substring(start, end === -1 ? text.length : end);
        const parts = line.split(" ");

        let qty = "";
        if (parts.length > 1 && !isNaN(parts[0])) {
            qty = parts[0] + " ";
        }

        const newLine = `${qty}${name}`;

        this.input.value =
            text.substring(0, start) +
            newLine +
            text.substring(end === -1 ? text.length : end);

        this.hide();
    },

    hide() {
        this.box.classList.add("hidden");
    }
};