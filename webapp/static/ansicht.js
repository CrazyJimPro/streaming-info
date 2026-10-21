// Umschalter "Nach Bereich | Nach Woche" auf der Startseite. Beide Ansichten
// sind fertig gerendert, sichtbar ist die, die html[data-ansicht] nennt (das
// setzt schon das Kopf-Skript aus localStorage, damit nichts aufblitzt).
// Anders als der Schnellfilter wird die Wahl gemerkt (Nutzerentscheidung):
// sie versteckt keine Inhalte, sondern ordnet sie nur anders.
(function () {
  var wurzel = document.documentElement;
  var knoepfe = document.querySelectorAll("[data-ansicht-wahl]");
  if (!knoepfe.length) return;

  function aktuelle() {
    return wurzel.getAttribute("data-ansicht") === "woche" ? "woche" : "bereich";
  }

  function anzeigen() {
    var ansicht = aktuelle();
    knoepfe.forEach(function (k) {
      k.setAttribute("aria-pressed", String(k.getAttribute("data-ansicht-wahl") === ansicht));
    });
  }

  knoepfe.forEach(function (k) {
    k.addEventListener("click", function () {
      var ansicht = k.getAttribute("data-ansicht-wahl");
      if (ansicht === aktuelle()) return;
      if (ansicht === "woche") wurzel.setAttribute("data-ansicht", "woche");
      else wurzel.removeAttribute("data-ansicht");
      try { localStorage.setItem("si-ansicht", ansicht); } catch (e) {}
      anzeigen();
      // Der Schnellfilter zaehlt nur die sichtbare Ansicht und muss deshalb
      // neu rechnen (Hinweis "Keine Treffer", leere Abschnitte).
      document.dispatchEvent(new CustomEvent("si-ansicht-gewechselt"));
    });
  });

  anzeigen();
})();
