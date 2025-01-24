function toggleFilters() {
    var filters = document.getElementById("filters");
    if (filters.style.display === "none" || filters.style.display === "") {
        filters.style.display = "block";
    } else {
        filters.style.display = "none";
    }
}