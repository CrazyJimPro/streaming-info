// Merkliste/Ausblendliste: Live-Suche per TMDB waehrend des Tippens, Klick
// auf einen Treffer haengt eine Zeile mit versteckten Feldern
// <praefix>_tmdb_id/<praefix>_medientyp/<praefix>_titel an - beim Speichern
// liest webapp/app.py diese Tripel wieder aus (siehe _liste_aus_formular).
(function () {
  var formular = document.getElementById("einstellungen-formular");
  var leiste = document.getElementById("speichern-leiste");

  // Ungespeicherte Aenderungen: Vergleich mit dem Formularstand beim Laden.
  // Ueber den Stand statt ueber "irgendwas wurde angeklickt", damit die Leiste
  // wieder verschwindet, wenn man eine Aenderung von Hand zuruecknimmt.
  function formularStand() {
    return formular ? new URLSearchParams(new FormData(formular)).toString() : "";
  }
  var ausgangsStand = formularStand();
  var wirdGespeichert = false;

  function pruefeAenderungen() {
    if (!leiste) return;
    leiste.hidden = formularStand() === ausgangsStand;
  }

  if (formular) {
    formular.addEventListener("input", pruefeAenderungen);
    formular.addEventListener("change", pruefeAenderungen);
    formular.addEventListener("submit", function () { wirdGespeichert = true; });
  }
  window.addEventListener("beforeunload", function (ereignis) {
    if (wirdGespeichert || !leiste || leiste.hidden) return;
    ereignis.preventDefault();
    ereignis.returnValue = "";
  });
  var speichernKnopf = document.getElementById("leiste-speichern");
  if (speichernKnopf && formular) {
    speichernKnopf.addEventListener("click", function () { formular.requestSubmit(); });
  }
  var verwerfenKnopf = document.getElementById("leiste-verwerfen");
  if (verwerfenKnopf) {
    verwerfenKnopf.addEventListener("click", function () {
      wirdGespeichert = true;
      location.reload();
    });
  }

  function verstecktesFeld(name, wert) {
    var feld = document.createElement("input");
    feld.type = "hidden";
    feld.name = name;
    feld.value = wert;
    return feld;
  }

  // "Noch nichts gemerkt" / "Nichts ausgeblendet" unter einer leeren Liste.
  function leerHinweisAktualisieren(listeElement) {
    var hinweis = document.querySelector('[data-leer-fuer="' + listeElement.id + '"]');
    if (hinweis) hinweis.hidden = listeElement.querySelector("tr") !== null;
  }

  function steht(listeElement, tmdbId, medientyp) {
    return listeElement.querySelector(
      '[data-tmdb-id="' + tmdbId + '"][data-medientyp="' + medientyp + '"]'
    ) !== null;
  }

  function posterElement(posterUrl) {
    if (!posterUrl) {
      var leer = document.createElement("span");
      leer.className = "listen-poster-leer";
      return leer;
    }
    var bild = document.createElement("img");
    bild.src = posterUrl;
    bild.alt = "";
    return bild;
  }

  // Bewusst ohne innerHTML: ein Titel mit Anfuehrungszeichen hat dort das
  // value-Attribut abgeschnitten und wurde verstuemmelt gespeichert. Aufbau
  // wie das Makro listen_zeile in einstellungen.html.
  function zeileHinzufuegen(listeElement, praefix, t) {
    if (steht(listeElement, t.tmdb_id, t.medientyp)) return;

    var zeile = document.createElement("tr");
    zeile.setAttribute("data-tmdb-id", t.tmdb_id);
    zeile.setAttribute("data-medientyp", t.medientyp);

    var posterZelle = document.createElement("td");
    posterZelle.className = "listen-poster";
    posterZelle.appendChild(posterElement(t.poster_url));

    var titelZelle = document.createElement("td");
    titelZelle.className = "listen-titel";
    var link = document.createElement("a");
    link.href = "/details/" + t.medientyp + "/" + t.tmdb_id + "?zurueck=" + encodeURIComponent("/einstellungen");
    link.textContent = t.titel;
    titelZelle.appendChild(link);
    var art = document.createElement("span");
    art.className = "hinweis";
    art.textContent = (t.medientyp === "film" ? "Film" : "Serie") + (t.jahr ? " · " + t.jahr : "");
    titelZelle.appendChild(art);

    var knopfZelle = document.createElement("td");
    knopfZelle.className = "listen-aktion";
    var knopf = document.createElement("button");
    knopf.type = "button";
    knopf.className = "entfernen-knopf";
    knopf.textContent = "entfernen";
    knopfZelle.appendChild(knopf);

    zeile.appendChild(posterZelle);
    zeile.appendChild(titelZelle);
    zeile.appendChild(knopfZelle);
    zeile.appendChild(verstecktesFeld(praefix + "_tmdb_id", t.tmdb_id));
    zeile.appendChild(verstecktesFeld(praefix + "_medientyp", t.medientyp));
    zeile.appendChild(verstecktesFeld(praefix + "_titel", t.titel));
    listeElement.appendChild(zeile);
    leerHinweisAktualisieren(listeElement);
    pruefeAenderungen();
  }

  function sucheEinrichten(sucheInputId, ergebnisseId, listeId, praefix) {
    var input = document.getElementById(sucheInputId);
    var ergebnisse = document.getElementById(ergebnisseId);
    var liste = document.getElementById(listeId);
    if (!input || !ergebnisse || !liste) return;

    var timer = null;
    input.addEventListener("input", function (ereignis) {
      // Das Suchfeld selbst ist keine Einstellung (es hat keinen name) -
      // trotzdem nicht bis zur Speichern-Leiste durchreichen.
      ereignis.stopPropagation();
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
              eintrag.appendChild(posterElement(t.poster_url));
              var text = document.createElement("span");
              text.textContent = t.titel + (t.jahr ? " (" + t.jahr + ")" : "") + " — " + (t.medientyp === "film" ? "Film" : "Serie");
              eintrag.appendChild(text);
              // Schon in der Liste: markieren statt ein zweites Mal anbieten.
              if (steht(liste, t.tmdb_id, t.medientyp)) {
                eintrag.classList.add("schon-drin");
                var marke = document.createElement("span");
                marke.className = "hinweis";
                marke.textContent = "✓ gemerkt";
                eintrag.appendChild(marke);
              } else {
                eintrag.addEventListener("click", function () {
                  zeileHinzufuegen(liste, praefix, t);
                  ergebnisse.innerHTML = "";
                  input.value = "";
                });
              }
              ergebnisse.appendChild(eintrag);
            });
          })
          .catch(function () {});
      }, 300);
    });
  }

  // Ein Listener fuer alle Entfernen-Knoepfe, auch fuer spaeter angehaengte
  // Zeilen.
  document.addEventListener("click", function (ereignis) {
    var knopf = ereignis.target.closest(".entfernen-knopf");
    if (!knopf) return;
    var zeile = knopf.closest("tr");
    var liste = zeile.closest("table");
    zeile.remove();
    if (liste) leerHinweisAktualisieren(liste);
    pruefeAenderungen();
  });

  sucheEinrichten("merk-suche", "merk-ergebnisse", "merk-liste", "merk");

  // Abo-Adresse des Kalenders kopieren. navigator.clipboard gibt es nur in
  // "sicheren" Seiten (https oder localhost) - wer die App per Netzwerk-IP
  // aufruft, bekommt deshalb den alten execCommand-Weg.
  var kalenderFeld = document.getElementById("kalender-url");
  var kopierKnopf = document.getElementById("kalender-kopieren");
  if (kalenderFeld && kopierKnopf) {
    kopierKnopf.addEventListener("click", function () {
      function erledigt() {
        kopierKnopf.textContent = "Kopiert ✓";
        setTimeout(function () { kopierKnopf.textContent = "Kopieren"; }, 2000);
      }
      function altWeg() {
        kalenderFeld.focus();
        kalenderFeld.select();
        try {
          if (document.execCommand("copy")) erledigt();
        } catch (e) {}
      }
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(kalenderFeld.value).then(erledigt, altWeg);
      } else {
        altWeg();
      }
    });
  }
})();
