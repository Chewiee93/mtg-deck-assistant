export const Filters = {

    init() {
        const search = document.getElementById("searchInput");
        const color = document.getElementById("colorFilter");

        search?.addEventListener("input", this.apply);
        color?.addEventListener("change", this.apply);
    },

    apply() {
        const search = document.getElementById("searchInput").value.toLowerCase();
        const color = document.getElementById("colorFilter").value;

        document.querySelectorAll(".card, .grid-card").forEach(card => {
            const name = card.dataset.name || "";
            const cardColor = card.dataset.color || "";

            const show =
                name.includes(search) &&
                (!color || cardColor.includes(color));

            card.style.display = show ? "block" : "none";
        });
    }
};