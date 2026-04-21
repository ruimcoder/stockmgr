// Category-aware field visibility (#125)

function updateCategoryVisibility() {
  var catEls = document.querySelectorAll('[name="item_category"]');
  var catVal = "food";
  catEls.forEach(function (el) {
    if (el.checked) catVal = el.value;
  });
  var isNonFood = catVal === "non_food";
  document.querySelectorAll(".food-only-field").forEach(function (el) {
    el.classList.toggle("d-none", isNonFood);
  });
  document.querySelectorAll(".non-food-only-field").forEach(function (el) {
    el.classList.toggle("d-none", !isNonFood);
  });
  updateExpiryRequired();
}

function updateExpiryRequired() {
  var catEls = document.querySelectorAll('[name="item_category"]');
  var catVal = "food";
  catEls.forEach(function (el) {
    if (el.checked) catVal = el.value;
  });
  var nfcEl = document.querySelector('[name="non_food_category"]');
  var nfcVal = nfcEl ? nfcEl.value : "";
  var needsExpiry = catVal !== "non_food" || ["medicine", "seeds", "energy"].includes(nfcVal);
  document.querySelectorAll(".expiry-input").forEach(function (inp) {
    inp.required = needsExpiry;
  });
  document.querySelectorAll(".expiry-required-star").forEach(function (star) {
    star.classList.toggle("d-none", !needsExpiry);
  });
  document.querySelectorAll(".expiry-optional-hint").forEach(function (hint) {
    hint.classList.toggle("d-none", needsExpiry);
  });
}

document.addEventListener("DOMContentLoaded", function () {
  updateCategoryVisibility();
  document.querySelectorAll('[name="item_category"]').forEach(function (el) {
    el.addEventListener("change", updateCategoryVisibility);
  });
  var nfcEl = document.querySelector('[name="non_food_category"]');
  if (nfcEl) nfcEl.addEventListener("change", updateExpiryRequired);
});
