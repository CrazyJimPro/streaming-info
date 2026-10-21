// Blaettern im Banner "Highlights der Woche": Pfeile, Punkte, Pfeiltasten
// (wenn der Fokus im Banner liegt) und Wischen auf dem Handy. Bewusst kein
// automatisches Weiterblaettern - das Banner soll nicht dauernd zappeln.
(function () {
  var banner = document.getElementById("highlights");
  if (!banner) return;
  var folien = banner.querySelectorAll(".highlight-folie");
  var punkte = banner.querySelectorAll(".highlight-punkt");
  if (folien.length < 2) return;
  var aktuell = 0;

  // Die Bilder der verdeckten Folien laden "lazy", also erst beim Aufdecken -
  // dann waere die Folie kurz leer. Sobald die Seite fertig ist, holen wir sie
  // deshalb im Hintergrund nach; den Seitenaufbau bremst das nicht mehr.
  function vorladen() {
    banner.querySelectorAll('.highlight-bild[loading="lazy"]').forEach(function (bild) {
      bild.loading = "eager";
    });
  }
  if (document.readyState === "complete") vorladen();
  else window.addEventListener("load", vorladen);

  function zeigen(index) {
    aktuell = (index + folien.length) % folien.length;
    folien.forEach(function (folie, i) { folie.hidden = i !== aktuell; });
    punkte.forEach(function (punkt, i) { punkt.setAttribute("aria-current", String(i === aktuell)); });
  }

  banner.querySelectorAll(".highlight-pfeil").forEach(function (pfeil) {
    pfeil.addEventListener("click", function () {
      zeigen(aktuell + Number(pfeil.getAttribute("data-richtung")));
    });
  });
  punkte.forEach(function (punkt) {
    punkt.addEventListener("click", function () {
      zeigen(Number(punkt.getAttribute("data-ziel")));
    });
  });
  banner.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") { zeigen(aktuell - 1); e.preventDefault(); }
    if (e.key === "ArrowRight") { zeigen(aktuell + 1); e.preventDefault(); }
  });

  // Wischen: nur waagerechte Bewegungen ab 40px zaehlen, damit normales
  // Scrollen der Seite nicht versehentlich blaettert.
  var startX = null, startY = null;
  banner.addEventListener("touchstart", function (e) {
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
  }, { passive: true });
  banner.addEventListener("touchend", function (e) {
    if (startX === null) return;
    var dx = e.changedTouches[0].clientX - startX;
    var dy = e.changedTouches[0].clientY - startY;
    startX = null;
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy) * 1.5) zeigen(aktuell + (dx < 0 ? 1 : -1));
  });
})();
