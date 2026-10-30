// Follow the page colours picked on the site's other pages. The viewer itself has light
// and dark, and under Auto it shows the document's theme that matches.
// Runs in the head, so the colours are set before the page is drawn.
try {
  const picked = localStorage.getItem("pdf-themes-page-colours");
  if (picked && picked !== "auto") document.documentElement.setAttribute("data-theme", picked.startsWith("dark") ? "dark" : "light");
} catch (e) { /* storage blocked: follow the device */ }
