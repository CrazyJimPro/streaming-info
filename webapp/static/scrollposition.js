// Rueckkehr an die alte Stelle der Startseite: nach Details -> Zurueck und
// nach Merken/Entmerken/Ausblenden/Rueckgaengig (alle laden die Startseite neu)
// stand man sonst immer ganz oben.
//
// Gemerkt wird nicht die Pixelposition, sondern die angeklickte KARTE samt
// ihrem Abstand zum oberen Fensterrand: beim Merken waechst die Merkliste oben
// um eine Karte, beim Ausblenden verschwindet eine - eine reine Pixelposition
// laege danach um eine Kartenreihe daneben. Ist die Karte selbst weg
// (ausgeblendet), dient die naechste im selben Abschnitt als Anker.
(function () {
  var SCHLUESSEL = "si-rueckkehr";
  var GUELTIG_MS = 30 * 60 * 1000;

  function lesen() {
    try {
      return JSON.parse(sessionStorage.getItem(SCHLUESSEL) || "null");
    } catch (e) {
      return null;
    }
  }

  function loeschen() {
    try { sessionStorage.removeItem(SCHLUESSEL); } catch (e) {}
  }

  function merken(karte) {
    var abschnitt = karte.closest("section[data-abschnitt]");
    var anker = [karte.getAttribute("data-kennung")];
    // Nachfolger als Ersatzanker, falls die Karte gleich verschwindet.
    var nachbar = karte.nextElementSibling;
    while (nachbar && anker.length < 4) {
      if (nachbar.classList.contains("karte")) anker.push(nachbar.getAttribute("data-kennung"));
      nachbar = nachbar.nextElementSibling;
    }
    // Letzte Karte im Abschnitt: dann eben der Vorgaenger.
    var vorgaenger = karte.previousElementSibling;
    if (vorgaenger && vorgaenger.classList.contains("karte")) anker.push(vorgaenger.getAttribute("data-kennung"));
    var stand = {
      abschnitt: abschnitt ? abschnitt.getAttribute("data-abschnitt") : null,
      anker: anker,
      abstand: karte.getBoundingClientRect().top,
      y: window.scrollY,
      zeit: Date.now()
    };
    try { sessionStorage.setItem(SCHLUESSEL, JSON.stringify(stand)); } catch (e) {}
  }

  function karteFinden(stand) {
    var bereich = stand.abschnitt
      ? document.querySelector('section[data-abschnitt="' + stand.abschnitt + '"]')
      : document;
    if (!bereich) return null;
    for (var i = 0; i < stand.anker.length; i++) {
      var karte = bereich.querySelector('.karte[data-kennung="' + stand.anker[i] + '"]');
      if (karte && !karte.hidden) return karte;
    }
    return null;
  }

  function hinrollen(stand) {
    var karte = karteFinden(stand);
    var ziel = karte
      ? karte.getBoundingClientRect().top + window.scrollY - stand.abstand
      : stand.y;
    window.scrollTo(0, Math.max(0, ziel));
  }

  function wiederherstellen() {
    var stand = lesen();
    loeschen();
    if (!stand || Date.now() - stand.zeit > GUELTIG_MS) return;
    hinrollen(stand);
    // Die Webschrift kann erst danach fertig laden und Titel anders umbrechen
    // lassen - dann einmal nachjustieren, aber nur, solange der Nutzer nicht
    // schon selbst weitergescrollt hat.
    if (document.fonts && document.fonts.ready) {
      var gerollt = window.scrollY;
      document.fonts.ready.then(function () {
        if (Math.abs(window.scrollY - gerollt) < 2) hinrollen(stand);
      });
    }
  }

  // Klick auf Poster/Titel (-> Details) oder Absenden eines Karten-Formulars.
  document.addEventListener("click", function (e) {
    var link = e.target.closest && e.target.closest(".karte a");
    if (link) merken(link.closest(".karte"));
  });
  document.addEventListener("submit", function (e) {
    var karte = e.target.closest(".karte");
    if (karte) {
      merken(karte);
    } else if (e.target.closest(".rueckgaengig-leiste")) {
      // Rueckgaengig: dorthin zurueck, wo man beim Ausblenden war - der Stand
      // davon wurde beim Laden schon verbraucht, deshalb die aktuelle Stelle.
      try {
        sessionStorage.setItem(SCHLUESSEL, JSON.stringify({ abschnitt: null, anker: [], y: window.scrollY, zeit: Date.now() }));
      } catch (err) {}
    }
  });

  // Aus dem Browser-Cache (Zurueck-Taste des Browsers) kommt die Seite samt
  // Scrollstand zurueck, ohne dieses Skript neu auszufuehren - dann den alten
  // Stand nur wegwerfen, damit er nicht beim naechsten frischen Aufruf greift.
  window.addEventListener("pageshow", function (e) {
    if (e.persisted) loeschen();
  });

  wiederherstellen();
})();
