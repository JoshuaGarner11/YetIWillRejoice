// Yet I Will Rejoice — small progressive enhancements. Everything works without this file.
(function () {
  // Mobile menu
  var btn = document.querySelector(".menu-btn");
  var nav = document.getElementById("site-nav");
  if (btn && nav) {
    btn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      btn.setAttribute("aria-expanded", open);
      btn.textContent = open ? "Close" : "Menu";
    });
    nav.addEventListener("click", function (e) {
      if (e.target.closest("a")) { nav.classList.remove("open"); btn.setAttribute("aria-expanded", false); btn.textContent = "Menu"; }
    });
  }

  // Click-to-play YouTube: no YouTube scripts load until someone presses play.
  document.querySelectorAll(".video[data-youtube] button").forEach(function (b) {
    b.addEventListener("click", function () {
      var box = b.parentElement;
      var f = document.createElement("iframe");
      f.src = "https://www.youtube-nocookie.com/embed/" + box.dataset.youtube + "?autoplay=1&rel=0";
      f.title = b.getAttribute("aria-label") || "Episode video";
      f.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
      f.allowFullscreen = true;
      box.replaceChildren(f);
    });
  });

  // Episode library: search + series filter, with the series kept in the URL hash.
  var lib = document.querySelector("[data-library]");
  if (lib) {
    var input = lib.querySelector("[data-search-input]");
    var chips = lib.querySelectorAll("[data-filter]");
    var cards = lib.querySelectorAll(".ep");
    var empty = lib.querySelector("[data-empty]");
    var series = "all";
    var apply = function () {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      cards.forEach(function (c) {
        var ok = (series === "all" || c.dataset.series === series) && (!q || c.dataset.search.indexOf(q) > -1);
        c.hidden = !ok;
        if (ok) shown++;
      });
      empty.hidden = shown > 0;
    };
    var pick = function (key) {
      series = key;
      chips.forEach(function (c) { c.setAttribute("aria-pressed", c.dataset.filter === key); });
      apply();
    };
    chips.forEach(function (c) {
      c.addEventListener("click", function () {
        pick(c.dataset.filter);
        history.replaceState(null, "", c.dataset.filter === "all" ? location.pathname : "#" + c.dataset.filter);
      });
    });
    input.addEventListener("input", apply);
    var start = location.hash.slice(1);
    if (start && lib.querySelector('[data-filter="' + start + '"]')) pick(start);
  }

  // Share buttons
  var share = document.querySelector("[data-share]");
  if (share) {
    var url = share.dataset.url, title = share.dataset.title;
    var nativeBtn = share.querySelector("[data-share-native]");
    if (navigator.share && nativeBtn) {
      nativeBtn.hidden = false;
      nativeBtn.addEventListener("click", function () { navigator.share({ title: title, url: url }).catch(function () {}); });
    }
    var copy = share.querySelector("[data-copy]");
    copy.addEventListener("click", function () {
      var done = function () { copy.textContent = "Link copied"; setTimeout(function () { copy.textContent = "Copy link"; }, 2000); };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, function () { prompt("Copy this link:", url); });
      else prompt("Copy this link:", url);
    });
  }
})();
