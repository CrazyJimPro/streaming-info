// Merkliste/Ausblendliste: Live-Suche per TMDB waehrend des Tippens, Klick
// auf einen Treffer haengt eine Zeile mit versteckten Feldern
// <praefix>_tmdb_id/<praefix>_medientyp/<praefix>_titel an - beim Speichern
// liest webapp/app.py diese Tripel wieder aus (siehe _liste_aus_formular).
(function () {
  function zeileHinzufuegen(listeElement, praefix, tmdbId, medientyp, titel) {
    var vorhanden = listeElement.querySelector(
      '[data-tmdb-id="' + tmdbId + '"][data-medientyp="' + medientyp + '"]'
    );
    if (vorhanden) return;

    var zeile = document.createElement("tr");
    zeile.setAttribute("data-tmdb-id", tmdbId);
    zeile.setAttribute("data-medientyp", medientyp);
    zeile.innerHTML =
      '<td>' + titel + ' <span class="hinweis">(' + (medientyp === "film" ? "Film" : "Serie") + ')</span></td>' +
      '<td><button type="button" class="entfernen-knopf">entfernen</button></td>' +
      '<input type="hidden" name="' + praefix + '_tmdb_id" value="' + tmdbId + '">' +
      '<input type="hidden" name="' + praefix + '_medientyp" value="' + medientyp + '">' +
      '<input type="hidden" name="' + praefix + '_titel" value="' + titel + '">';
    zeile.querySelector(".entfernen-knopf").addEventListener("click", function () {
      zeile.remove();
    });
    listeElement.appendChild(zeile);
  }

  function sucheEinrichten(sucheInputId, ergebnisseId, listeId, praefix) {
    var input = document.getElementById(sucheInputId);
    var ergebnisse = document.getElementById(ergebnisseId);
    var liste = document.getElementById(listeId);
    if (!input || !ergebnisse || !liste) return;

    var timer = null;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      var text = input.value.trim();
      if (text.length < 2) {
        ergebnisse.innerHTML = "";
        return;
      }
      timer = setTimeout(function () {
        fetch("/titel-suche?q=" + encodeURIComponent(text))
          .then(function (r) { return r.json(); })
          .then(function (treffer) {
            ergebnisse.innerHTML = "";
            treffer.forEach(function (t) {
              var eintrag = document.createElement("div");
              eintrag.className = "suchtreffer";
              eintrag.textContent = t.titel + (t.jahr ? " (" + t.jahr + ")" : "") + " — " + (t.medientyp === "film" ? "Film" : "Serie");
              eintrag.addEventListener("click", function () {
                zeileHinzufuegen(liste, praefix, t.tmdb_id, t.medientyp, t.titel);
                ergebnisse.innerHTML = "";
                input.value = "";
              });
              ergebnisse.appendChild(eintrag);
            });
          })
          .catch(function () {});
      }, 300);
    });
  }

  document.querySelectorAll(".entfernen-knopf").forEach(function (knopf) {
    knopf.addEventListener("click", function () {
      knopf.closest("tr").remove();
    });
  });

  sucheEinrichten("merk-suche", "merk-ergebnisse", "merk-liste", "merk");
})();
