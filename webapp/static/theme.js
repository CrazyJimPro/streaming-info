// Manueller Hell/Dunkel-Umschalter. Die eigentliche Farbwahl passiert per
// CSS ueber :root[data-theme="..."] (siehe style.css) - hier wird nur der
// Knopf verdrahtet und die Wahl in localStorage gemerkt.
(function () {
  function effektivesTheme() {
    var explizit = document.documentElement.getAttribute("data-theme");
    if (explizit === "dark" || explizit === "light") return explizit;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function beschrifte(button) {
    var aktuell = effektivesTheme();
    button.textContent = aktuell === "dark" ? "☀️" : "🌙";
    button.setAttribute(
      "aria-label",
      aktuell === "dark" ? "Helles Design aktivieren" : "Dunkles Design aktivieren"
    );
  }

  function init() {
    var button = document.getElementById("theme-toggle");
    if (!button) return;
    beschrifte(button);

    button.addEventListener("click", function () {
      var neu = effektivesTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", neu);
      try {
        localStorage.setItem("si-theme", neu);
      } catch (e) {
        // localStorage kann z.B. im privaten Modus fehlschlagen - dann
        // wirkt der Umschalter nur fuer die aktuelle Seitenansicht.
      }
      beschrifte(button);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
