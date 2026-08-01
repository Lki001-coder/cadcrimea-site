(() => {
  const consentKey = "mycad_analytics_consent";
  const counterId = 111170926;

  function loadMetrica() {
    if (window.ym) return;
    window.ym =
      window.ym ||
      function () {
        (window.ym.a = window.ym.a || []).push(arguments);
      };
    window.ym.l = Date.now();
    const script = document.createElement("script");
    script.async = true;
    script.src = "https://mc.yandex.ru/metrika/tag.js";
    document.head.appendChild(script);
    window.ym(counterId, "init", {
      clickmap: true,
      trackLinks: true,
      accurateTrackBounce: true,
      webvisor: false,
      sendTitle: false,
    });
  }

  function askForConsent() {
    if (localStorage.getItem(consentKey) === "accepted") {
      loadMetrica();
      return;
    }
    if (localStorage.getItem(consentKey) === "declined") return;

    const notice = document.createElement("aside");
    notice.className = "analytics-consent";
    notice.setAttribute("aria-label", "Настройка аналитики");
    notice.innerHTML =
      "<p>Метрика без Вебвизора помогает улучшать полезные страницы.</p>" +
      '<a href="/privacy">Подробнее</a>' +
      '<div class="consent-actions">' +
      '<button type="button" data-consent="declined">Не сейчас</button>' +
      '<button class="consent-accept" type="button" data-consent="accepted">Разрешить</button>' +
      "</div>";
    notice.addEventListener("click", (event) => {
      const button = event.target.closest("[data-consent]");
      if (!button) return;
      const value = button.dataset.consent;
      localStorage.setItem(consentKey, value);
      notice.remove();
      if (value === "accepted") loadMetrica();
    });
    document.body.appendChild(notice);
  }

  function metricGoals(link) {
    const href = link.getAttribute("href") || "";
    const goals = [];
    if (/^https?:\/\/t\.me\//i.test(href)) {
      goals.push("telegram_click");
      if (location.pathname.startsWith("/materialy/")) {
        goals.push("material_telegram_click");
      }
    }
    if (/^tel:/i.test(href)) goals.push("phone_click");
    if (link.dataset.metric) goals.push(link.dataset.metric);
    try {
      if (new URL(href, location.origin).pathname.startsWith("/uslugi/")) {
        goals.push("service_open");
      }
    } catch {}
    return [...new Set(goals)];
  }

  function enableMetrics() {
    document.addEventListener(
      "click",
      (event) => {
        if (!(event.target instanceof Element)) return;
        const link = event.target.closest("a[href]");
        if (!link || !window.ym) return;
        for (const goal of metricGoals(link)) {
          window.ym(counterId, "reachGoal", goal, {
            source_url: location.href,
            target_url: link.href,
            placement: link.dataset.metric || "default",
          });
        }
      },
      true,
    );
  }

  function enableMobileContact() {
    const dock = document.querySelector(".mobile-contact-dock");
    if (!dock) return;
    const update = () => {
      dock.dataset.visible = window.scrollY > 420 ? "true" : "false";
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("touchmove", update, { passive: true });
  }

  enableMetrics();
  enableMobileContact();
  askForConsent();
})();
