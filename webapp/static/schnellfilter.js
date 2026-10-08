// Schnellfilter auf der Startseite: blendet Karten nur im Browser aus und ein.
// Kein neuer Abruf, keine Aenderung an den Einstellungen und bewusst kein
// Merken in localStorage - beim naechsten Oeffnen steht wieder alles da, damit
// nichts unbemerkt verborgen bleibt (Nutzerentscheidung).
(function () {
  var leiste = document.getElementById("schnellfilter");
  if (!leiste) return;

  var art = "alle"; // "alle" | "serie" | "film"
  var quellen = {}; // angeklickte Anbieter-Schluessel

  var artKnoepfe = leiste.querySelectorAll("[data-art]");
  var quellKnoepfe = leiste.querySelectorAll("[data-quelle]");
  var zuruecksetzen = document.getElementById("filter-zuruecksetzen");
  var leerHinweis = document.getElementById("filter-leer");

  function quellenGewaehlt() {
    return Object.keys(quellen);
  }

  function karteSichtbar(karte, inMerkliste) {
    if (art !== "alle" && karte.getAttribute("data-medientyp") !== art) return false;
    // Die Merkliste reagiert nur auf Serien/Filme, nicht auf die Anbieter:
    // gemerkt ist gemerkt.
    if (inMerkliste) return true;
    var gewaehlt = quellenGewaehlt();
    if (!gewaehlt.length) return true;
    // Eine Karte mit mehreren Anbietern bleibt, sobald einer davon gewaehlt ist.
    var eigene = (karte.getAttribute("data-quellen") || "").split(" ");
    return eigene.some(function (q) { return quellen[q]; });
  }

  function anwenden() {
    var aktiv = art !== "alle" || quellenGewaehlt().length > 0;
    var irgendwasSichtbar = false;

    document.querySelectorAll("section[data-abschnitt]").forEach(function (abschnitt) {
      var inMerkliste = abschnitt.getAttribute("data-abschnitt") === "merkliste";
      var sichtbare = 0;
      abschnitt.querySelectorAll(".karte").forEach(function (karte) {
        var zeigen = karteSichtbar(karte, inMerkliste);
        karte.hidden = !zeigen;
        if (zeigen) sichtbare++;
      });
      // Bei aktivem Filter verschwinden Abschnitte ohne Treffer ganz - sonst
      // stuende z.B. bei "nur Netflix" ein leerer Kino-Abschnitt herum.
      abschnitt.hidden = aktiv && sichtbare === 0;
      if (sichtbare > 0) irgendwasSichtbar = true;
    });

    artKnoepfe.forEach(function (k) {
      k.setAttribute("aria-pressed", String(k.getAttribute("data-art") === art));
    });
    quellKnoepfe.forEach(function (k) {
      k.setAttribute("aria-pressed", String(!!quellen[k.getAttribute("data-quelle")]));
    });
    zuruecksetzen.hidden = !aktiv;
    leerHinweis.hidden = !(aktiv && !irgendwasSichtbar);
  }

  function allesZuruecksetzen() {
    art = "alle";
    quellen = {};
    anwenden();
  }

  artKnoepfe.forEach(function (k) {
    k.addEventListener("click", function () {
      art = k.getAttribute("data-art");
      anwenden();
    });
  });
  quellKnoepfe.forEach(function (k) {
    k.addEventListener("click", function () {
      var q = k.getAttribute("data-quelle");
      if (quellen[q]) delete quellen[q];
      else quellen[q] = true;
      anwenden();
    });
  });
  zuruecksetzen.addEventListener("click", allesZuruecksetzen);
  document.getElementById("filter-leer-zuruecksetzen").addEventListener("click", function (e) {
    e.preventDefault();
    allesZuruecksetzen();
  });
})();
