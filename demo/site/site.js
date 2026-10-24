// The page colours the reader picked, and the demo on the "Why themes" page.
// Runs in the head, so a picked theme is set before the page is drawn.
(function () {
  const KEY = "pdf-themes-page-colours";
  const root = document.documentElement;
  const THEMES = ["light", "dark", "light-contrast", "dark-contrast", "cream", "peach", "yellow", "turquoise"];

  function show(mode) {
    if (THEMES.includes(mode)) root.setAttribute("data-theme", mode);
    else root.removeAttribute("data-theme");
  }

  function remembered() {
    try {
      const value = localStorage.getItem(KEY);
      return THEMES.includes(value) ? value : null;
    } catch (e) {
      return null;  // a private window or blocked storage: follow the device
    }
  }

  // A link can ask for a theme, such as ?colours=peach, without changing what is remembered.
  const params = new URLSearchParams(location.search);
  const asked = THEMES.includes(params.get("colours")) ? params.get("colours") : null;
  show(asked || remembered());

  const NOTES = {
    themed: "The author's version for these page colours. Its text and lines are checked for contrast against this page, the lines also under three simulations of colour blindness. The grid is kept faint on purpose, except in the more contrast themes, and the picture is left as it was.",
    inverted: "Inverted, as a PDF app's dark mode or the screen's colour inversion can do it. Site A's line is now orange and Site B's blue, so a caption that names the blue line now points at the wrong one, and the picture is a negative.",
    recoloured: "Recoloured, as a high-contrast setting can do it: every line takes the colour of the text. With the markers, dashes and labels you can still tell the sites apart. Without them you can't.",
  };

  function syncSelect() {
    const select = document.getElementById("page-colours");
    if (select) select.value = asked || remembered() || "auto";
  }

  document.addEventListener("DOMContentLoaded", function () {
    const select = document.getElementById("page-colours");
    if (select) {
      syncSelect();
      select.addEventListener("change", function () {
        show(select.value);
        try { localStorage.setItem(KEY, select.value); } catch (e) { /* not remembered, but still shown */ }
      });
    }

    const demo = document.getElementById("demo");
    if (!demo) return;
    const note = document.getElementById("demo-note");
    const cues = document.getElementById("cues");

    function describe() {
      if (!note) return;
      note.textContent = NOTES[demo.dataset.view] +
        (demo.dataset.cues === "off" ? " The markers, dashes and labels are off." : "");
    }

    demo.querySelectorAll("button[data-view]").forEach(function (button) {
      button.addEventListener("click", function () {
        demo.dataset.view = button.dataset.view;
        demo.querySelectorAll("button[data-view]").forEach(function (b) {
          b.setAttribute("aria-pressed", String(b === button));
        });
        describe();
      });
    });
    if (cues) {
      cues.addEventListener("change", function () {
        demo.dataset.cues = cues.checked ? "on" : "off";
        describe();
      });
    }

    // ?view=inverted and ?cues=off open the demo that way.
    const wanted = params.get("view");
    if (Object.prototype.hasOwnProperty.call(NOTES, wanted)) {
      const view = demo.querySelector('button[data-view="' + wanted + '"]');
      if (view) view.click();
    }
    if (cues && params.get("cues") === "off") {
      cues.checked = false;
      demo.dataset.cues = "off";
      describe();
    }
  });

  // A page restored from the back and forward cache picks up colours chosen on another page.
  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    show(asked || remembered());
    syncSelect();
  });
})();
