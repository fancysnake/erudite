// The box in the head of the book list ticks every book on the page.
document.getElementById("select-all")?.addEventListener("change", (event) => {
  for (const box of document.querySelectorAll('input[name="book"]')) {
    box.checked = event.target.checked;
  }
});
