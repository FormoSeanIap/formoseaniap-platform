(() => {
  const PAGE_KEYS = new Set(["eng-home", "eng-articles", "eng-projects"]);
  const VISITOR_STORAGE_KEY = "analytics-visitor-id";
  const sentKeys = new Set();

  const generateVisitorId = () => {
    if (window.crypto?.randomUUID) {
      return window.crypto.randomUUID();
    }

    const bytes = new Uint8Array(16);
    if (window.crypto?.getRandomValues) {
      window.crypto.getRandomValues(bytes);
    } else {
      for (let index = 0; index < bytes.length; index += 1) {
        bytes[index] = Math.floor(Math.random() * 256);
      }
    }

    return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  };

  const getVisitorId = () => {
    try {
      const existing = localStorage.getItem(VISITOR_STORAGE_KEY);
      if (existing) {
        return existing;
      }
      const created = generateVisitorId();
      localStorage.setItem(VISITOR_STORAGE_KEY, created);
      return created;
    } catch (error) {
      return generateVisitorId();
    }
  };

  const sendPayload = (payload) => {
    const body = JSON.stringify(payload);
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: "application/json" });
      navigator.sendBeacon("/analytics-api/collect", blob);
      return;
    }

    fetch("/analytics-api/collect", {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body,
      cache: "no-store",
      keepalive: true
    }).catch(() => {});
  };

  const trackOnce = (trackingKey, payload) => {
    if (!trackingKey || sentKeys.has(trackingKey)) {
      return;
    }

    sentKeys.add(trackingKey);
    sendPayload({
      ...payload,
      visitor_id: getVisitorId(),
      domain: "engineering"
    });
  };

  const trackPageView = (pageKey) => {
    if (!PAGE_KEYS.has(pageKey)) {
      return;
    }

    trackOnce(`page:${pageKey}`, {
      scope: "page",
      page_key: pageKey,
      article_id: null,
      lang: null
    });
  };

  const trackArticleView = ({ articleId, lang }) => {
    if (!articleId || !["en", "zh"].includes(lang)) {
      return;
    }

    trackOnce(`article:${articleId}:${lang}`, {
      scope: "article",
      page_key: null,
      article_id: articleId,
      lang
    });
  };

  const autoTrackPageView = () => {
    const pageKey = document.body?.dataset?.page;
    const isArticleDetail = Boolean(document.querySelector("[data-article-detail]"));
    if (!pageKey || isArticleDetail) {
      return;
    }

    trackPageView(pageKey);
  };

  window.SiteAnalytics = {
    getVisitorId,
    trackArticleView,
    trackPageView
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoTrackPageView, { once: true });
  } else {
    autoTrackPageView();
  }
})();
