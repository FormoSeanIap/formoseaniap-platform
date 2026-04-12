(() => {
  const root = document.querySelector("[data-analytics-admin]");
  if (!root) {
    return;
  }

  const CONFIG_PATH = "../data/analytics.config.json";
  const ARTICLES_INDEX_PATH = "../data/articles.index.json";
  const LOCAL_HOSTNAMES = new Set(["127.0.0.1", "localhost"]);
  const MOCK_PAGE_KEYS = ["home", "articles", "projects", "podcasts", "about", "artworks"];
  const STORAGE_KEYS = {
    accessToken: "analytics-admin-access-token",
    idToken: "analytics-admin-id-token",
    expiresAt: "analytics-admin-access-token-expires-at",
    mockSession: "analytics-admin-mock-session",
    pkceState: "analytics-admin-pkce-state",
    pkceVerifier: "analytics-admin-pkce-verifier"
  };

  const els = {
    authPanel: document.querySelector("#analytics-auth-panel"),
    authSummary: document.querySelector("#analytics-auth-summary"),
    authActions: document.querySelector("#analytics-auth-actions"),
    dashboard: document.querySelector("#analytics-dashboard"),
    signedInMeta: document.querySelector("#analytics-signed-in-meta"),
    summaryCards: document.querySelector("#analytics-summary-cards"),
    rangeForm: document.querySelector("#analytics-range-form"),
    presetButtons: [...document.querySelectorAll("[data-range-preset]")],
    startInput: document.querySelector("#analytics-range-start"),
    endInput: document.querySelector("#analytics-range-end"),
    trendChart: document.querySelector("#analytics-trend-chart"),
    trendCaption: document.querySelector("#analytics-trend-caption"),
    topArticlesModeButtons: [...document.querySelectorAll("[data-articles-group]")],
    topArticlesTable: document.querySelector("#analytics-top-articles"),
    topArticlesMeta: document.querySelector("#analytics-top-articles-meta"),
    articleSearchInput: document.querySelector("#analytics-article-search"),
    articleSearchResults: document.querySelector("#analytics-article-search-results"),
    articleDetailMeta: document.querySelector("#analytics-article-detail-meta"),
    articleDetailChart: document.querySelector("#analytics-article-detail-chart"),
    signOutButton: document.querySelector("#analytics-sign-out")
  };

  const state = {
    articleGroups: [],
    articleLookup: new Map(),
    config: null,
    mockCache: new Map(),
    rangePreset: "30d",
    signedIn: false,
    topArticlesGroup: "combined",
    activeArticleId: null
  };

  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const fetchJson = async (path, options = {}) => {
    const response = await fetch(path, {
      cache: "no-store",
      ...options
    });

    if (!response.ok) {
      throw new Error(`Failed to load ${path}: HTTP ${response.status}`);
    }

    return response.json();
  };

  const formatNumber = (value) => new Intl.NumberFormat("en-US").format(Number(value || 0));

  const formatDateLabel = (value) =>
    new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "2-digit",
      year: "numeric"
    }).format(new Date(`${value}T00:00:00Z`));

  const utcToday = () => new Date().toISOString().slice(0, 10);

  const buildRangePreset = (days) => {
    const end = new Date();
    const start = new Date();
    start.setUTCDate(start.getUTCDate() - (days - 1));
    return {
      start: start.toISOString().slice(0, 10),
      end: end.toISOString().slice(0, 10)
    };
  };

  const isLocalhost = () => LOCAL_HOSTNAMES.has(window.location.hostname);

  const isMockModeEnabled = () => Boolean(state.config?.mock?.enabled) && isLocalhost();

  const getStoredToken = () => {
    try {
      const accessToken = sessionStorage.getItem(STORAGE_KEYS.accessToken);
      const idToken = sessionStorage.getItem(STORAGE_KEYS.idToken) || "";
      const expiresAt = Number(sessionStorage.getItem(STORAGE_KEYS.expiresAt) || "0");
      if (!accessToken || !expiresAt || Date.now() >= expiresAt) {
        return null;
      }
      return {
        accessToken,
        idToken,
        expiresAt
      };
    } catch (error) {
      return null;
    }
  };

  const storeToken = ({ access_token: accessToken, expires_in: expiresIn, id_token: idToken }) => {
    const expiresAt = Date.now() + Math.max(0, Number(expiresIn || 0) * 1000 - 5000);
    sessionStorage.setItem(STORAGE_KEYS.accessToken, accessToken);
    if (idToken) {
      sessionStorage.setItem(STORAGE_KEYS.idToken, idToken);
    } else {
      sessionStorage.removeItem(STORAGE_KEYS.idToken);
    }
    sessionStorage.setItem(STORAGE_KEYS.expiresAt, String(expiresAt));
  };

  const clearToken = () => {
    try {
      sessionStorage.removeItem(STORAGE_KEYS.accessToken);
      sessionStorage.removeItem(STORAGE_KEYS.idToken);
      sessionStorage.removeItem(STORAGE_KEYS.expiresAt);
      sessionStorage.removeItem(STORAGE_KEYS.pkceState);
      sessionStorage.removeItem(STORAGE_KEYS.pkceVerifier);
    } catch (error) {}
  };

  const getMockUsername = () => String(state.config?.mock?.username || "local-admin").trim() || "local-admin";
  const toTitleCase = (value) =>
    String(value || "")
      .split(/[\s._-]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ")
      .trim();
  const getMockDisplayName = () =>
    String(state.config?.mock?.name || "").trim() || toTitleCase(getMockUsername()) || "Local Admin";
  const getMockEmail = () =>
    String(state.config?.mock?.email || "").trim() || "local-admin@example.test";

  const getMockSession = () => {
    if (!isMockModeEnabled()) {
      return null;
    }

    try {
      const raw = sessionStorage.getItem(STORAGE_KEYS.mockSession);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") {
        return null;
      }
      return {
        email: String(parsed.email || getMockEmail()),
        name: String(parsed.name || getMockDisplayName()),
        sub: String(parsed.sub || "local-mock-admin"),
        username: String(parsed.username || getMockUsername())
      };
    } catch (error) {
      return null;
    }
  };

  const storeMockSession = () => {
    sessionStorage.setItem(
      STORAGE_KEYS.mockSession,
      JSON.stringify({
        email: getMockEmail(),
        name: getMockDisplayName(),
        sub: "local-mock-admin",
        username: getMockUsername()
      })
    );
  };

  const clearMockSession = () => {
    try {
      sessionStorage.removeItem(STORAGE_KEYS.mockSession);
    } catch (error) {}
  };

  const toBase64Url = (arrayBuffer) =>
    btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)))
      .replaceAll("+", "-")
      .replaceAll("/", "_")
      .replaceAll("=", "");

  const randomToken = () => {
    const bytes = new Uint8Array(32);
    window.crypto.getRandomValues(bytes);
    return toBase64Url(bytes.buffer);
  };

  const buildPkceChallenge = async (verifier) => {
    const data = new TextEncoder().encode(verifier);
    return toBase64Url(await window.crypto.subtle.digest("SHA-256", data));
  };

  const isConfigUsable = () => {
    if (isMockModeEnabled()) {
      return true;
    }
    if (!state.config?.admin?.enabled || !state.config?.admin?.site_base_url) {
      return false;
    }

    try {
      return window.location.origin === new URL(state.config.admin.site_base_url).origin;
    } catch (error) {
      return false;
    }
  };

  const setAuthState = ({ title, message, actions = "" }) => {
    state.signedIn = false;
    els.dashboard.hidden = true;
    els.dashboard.setAttribute("aria-busy", "false");
    els.authPanel.hidden = false;
    els.signOutButton.hidden = true;
    els.signedInMeta.textContent = isMockModeEnabled() ? "Local mock mode" : "Signed out";
    els.authSummary.innerHTML = `
      <h2>${escapeHtml(title)}</h2>
      <p>${escapeHtml(message)}</p>
    `;
    els.authActions.innerHTML = actions;
  };

  const decodeBase64Url = (value) => {
    const normalized = String(value || "").replaceAll("-", "+").replaceAll("_", "/");
    const padding = "=".repeat((4 - (normalized.length % 4)) % 4);
    const binary = window.atob(`${normalized}${padding}`);
    return Uint8Array.from(binary, (character) => character.charCodeAt(0));
  };

  const decodeJwtPayload = (token) => {
    try {
      const [, payload] = String(token || "").split(".");
      if (!payload) {
        return {};
      }
      const decoded = new TextDecoder().decode(decodeBase64Url(payload));
      const claims = JSON.parse(decoded);
      return claims && typeof claims === "object" ? claims : {};
    } catch (error) {
      return {};
    }
  };

  const normalizeIdentityValue = (value) => {
    const normalized = String(value || "").trim();
    return normalized || "";
  };

  const resolveSignedInLabel = () => {
    if (isMockModeEnabled()) {
      const session = getMockSession();
      return (
        normalizeIdentityValue(session?.name) ||
        normalizeIdentityValue(session?.email) ||
        ""
      );
    }

    const token = getStoredToken();
    const claims = decodeJwtPayload(token?.idToken || "");
    return (
      normalizeIdentityValue(claims.name) ||
      normalizeIdentityValue(claims.email) ||
      ""
    );
  };

  const formatSignedInMeta = (label) => {
    if (isMockModeEnabled()) {
      return label ? `Local mock mode as ${label}` : "Local mock mode";
    }
    return label ? `Signed in as ${label}` : "Signed in";
  };

  const setSignedInShell = () => {
    state.signedIn = true;
    els.authPanel.hidden = true;
    els.dashboard.hidden = false;
    els.signOutButton.hidden = false;
    els.signedInMeta.textContent = formatSignedInMeta(resolveSignedInLabel());
  };

  const createDashboardError = (
    message,
    {
      action = null,
      clearMockSession = false,
      clearToken = false,
      title = ""
    } = {}
  ) => {
    const error = new Error(message);
    error.analyticsAction = action;
    error.analyticsClearMockSession = clearMockSession;
    error.analyticsClearToken = clearToken;
    error.analyticsTitle = title;
    return error;
  };

  const defaultAuthActionMarkup = () =>
    isMockModeEnabled()
      ? authActionMarkup("mock-signin", "Open mock dashboard")
      : state.config?.admin?.enabled && isConfigUsable()
        ? authActionMarkup("signin", "Sign in again")
        : "";

  const resolveErrorActions = (error) => {
    if (error && typeof error.analyticsAction === "string") {
      if (error.analyticsAction === "mock-signin") {
        return authActionMarkup("mock-signin", "Open mock dashboard");
      }
      if (error.analyticsAction === "signin" && state.config?.admin?.enabled && isConfigUsable()) {
        return authActionMarkup("signin", "Sign in again");
      }
      return "";
    }
    return defaultAuthActionMarkup();
  };

  const presentDashboardError = (
    error,
    {
      fallbackMessage = "Failed to load analytics.",
      fallbackTitle = "Analytics unavailable",
      mockFallbackTitle = "Mock analytics unavailable"
    } = {}
  ) => {
    if (error?.analyticsClearToken) {
      clearToken();
    }
    if (error?.analyticsClearMockSession) {
      clearMockSession();
    }
    setAuthState({
      title:
        error?.analyticsTitle ||
        (isMockModeEnabled() ? mockFallbackTitle : fallbackTitle),
      message: error instanceof Error ? error.message : fallbackMessage,
      actions: resolveErrorActions(error)
    });
  };

  const getAuthHeaders = () => {
    const token = getStoredToken();
    if (!token) {
      throw createDashboardError("Sign in to access the private analytics dashboard.", {
        action: "signin",
        clearToken: true,
        title: "Sign-in required"
      });
    }
    return {
      authorization: `Bearer ${token.accessToken}`
    };
  };

  const hashString = (value) => {
    let hash = 2166136261;
    for (const character of String(value || "")) {
      hash ^= character.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  };

  const buildDateSpan = (start, end) => {
    const rows = [];
    const startDate = new Date(`${start}T00:00:00Z`);
    const endDate = new Date(`${end}T00:00:00Z`);
    const cursor = new Date(startDate);

    while (cursor <= endDate) {
      rows.push({
        date: new Date(cursor),
        iso: cursor.toISOString().slice(0, 10)
      });
      cursor.setUTCDate(cursor.getUTCDate() + 1);
    }

    return rows;
  };

  const sortArticleRows = (items) =>
    [...items].sort(
      (left, right) =>
        Number(right.views || 0) - Number(left.views || 0) ||
        Number(right.unique_visitors || 0) - Number(left.unique_visitors || 0) ||
        String(left.article_id || "").localeCompare(String(right.article_id || "")) ||
        String(left.lang || "").localeCompare(String(right.lang || ""))
    );

  const buildEmptyArticleDetail = (articleId, span) => ({
    article_id: articleId,
    from: span[0]?.iso || utcToday(),
    to: span.at(-1)?.iso || utcToday(),
    combined: {
      views: 0,
      unique_visitors: 0
    },
    by_language: {
      en: { views: 0, unique_visitors: 0 },
      zh: { views: 0, unique_visitors: 0 }
    },
    daily: span.map((day) => ({
      date: day.iso,
      combined: { views: 0, unique_visitors: 0 },
      by_language: {
        en: { views: 0, unique_visitors: 0 },
        zh: { views: 0, unique_visitors: 0 }
      }
    }))
  });

  const buildMockArticleDetail = (group, span) => {
    const articleId = group.id;
    const languages = Object.keys(group.pageUrlsByLang || {});
    const hasEnglish = languages.includes("en");
    const hasChinese = languages.includes("zh");
    const seed = hashString(articleId);
    const popularity = 0.35 + ((((seed % 1000) / 1000) ** 2) * 4.6);
    const baseViews = 2 + popularity * 5;
    const cadence = 4 + (seed % 7);
    const phase = ((seed % 360) * Math.PI) / 180;
    const ratioSeed = hashString(`${articleId}:ratio`);
    const englishRatioBase = 0.32 + ((ratioSeed % 36) / 100);
    const byLanguage = {
      en: { views: 0, unique_visitors: 0 },
      zh: { views: 0, unique_visitors: 0 }
    };
    const combined = { views: 0, unique_visitors: 0 };

    const daily = span.map((day, index) => {
      const weekdayBoost = [0.88, 1.01, 1.08, 1.12, 1.16, 1.08, 0.93][day.date.getUTCDay()];
      const seasonal =
        0.72 + (((Math.sin(index / cadence + phase) + 1) / 2) * 0.94);
      const pulse =
        0.86 + (((Math.cos(index / (cadence + 2) + phase / 2) + 1) / 2) * 0.36);
      const recencyBoost = index >= span.length - 7 ? 1.08 : 1;
      const totalViews = Math.max(0, Math.round(baseViews * weekdayBoost * seasonal * pulse * recencyBoost));
      const englishRatio = hasEnglish && hasChinese
        ? Math.min(
            0.85,
            Math.max(
              0.15,
              englishRatioBase + ((((Math.sin(index / 9 + phase * 1.5) + 1) / 2) - 0.5) * 0.12)
            )
          )
        : hasEnglish
          ? 1
          : 0;
      const englishViews = hasEnglish
        ? hasChinese
          ? Math.round(totalViews * englishRatio)
          : totalViews
        : 0;
      const chineseViews = hasChinese ? Math.max(0, totalViews - englishViews) : 0;
      const englishUniqueRatio = 0.43 + ((hashString(`${articleId}:en:unique`) % 17) / 100);
      const chineseUniqueRatio = 0.46 + ((hashString(`${articleId}:zh:unique`) % 15) / 100);
      const englishUnique = Math.min(
        englishViews,
        Math.round(englishViews * (englishUniqueRatio + ((((Math.cos(index / 7 + phase) + 1) / 2) - 0.5) * 0.05)))
      );
      const chineseUnique = Math.min(
        chineseViews,
        Math.round(chineseViews * (chineseUniqueRatio + ((((Math.sin(index / 8 + phase / 3) + 1) / 2) - 0.5) * 0.04)))
      );
      const combinedViews = englishViews + chineseViews;
      const combinedUnique = englishUnique + chineseUnique;

      byLanguage.en.views += englishViews;
      byLanguage.en.unique_visitors += englishUnique;
      byLanguage.zh.views += chineseViews;
      byLanguage.zh.unique_visitors += chineseUnique;
      combined.views += combinedViews;
      combined.unique_visitors += combinedUnique;

      return {
        date: day.iso,
        combined: {
          views: combinedViews,
          unique_visitors: combinedUnique
        },
        by_language: {
          en: {
            views: englishViews,
            unique_visitors: englishUnique
          },
          zh: {
            views: chineseViews,
            unique_visitors: chineseUnique
          }
        }
      };
    });

    return {
      article_id: articleId,
      from: span[0]?.iso || utcToday(),
      to: span.at(-1)?.iso || utcToday(),
      combined,
      by_language: byLanguage,
      daily
    };
  };

  const buildMockPageMetrics = (day, dayIndex) =>
    MOCK_PAGE_KEYS.reduce(
      (totals, pageKey, pageIndex) => {
        const seed = hashString(`${pageKey}:${day.iso}`);
        const pageBase = 8 + (pageIndex * 3);
        const dailyWave = 0.82 + (((Math.sin(dayIndex / (5 + pageIndex) + pageIndex) + 1) / 2) * 0.64);
        const noise = 0.88 + (((seed % 17) / 100));
        const pageViews = Math.max(0, Math.round(pageBase * dailyWave * noise));
        const pageUnique = Math.min(pageViews, Math.round(pageViews * (0.56 + ((seed % 9) / 100))));
        totals.views += pageViews;
        totals.unique += pageUnique;
        return totals;
      },
      { views: 0, unique: 0 }
    );

  const getMockRangeSnapshot = (range) => {
    const cacheKey = `${range.start}:${range.end}`;
    const cached = state.mockCache.get(cacheKey);
    if (cached) {
      return cached;
    }

    const span = buildDateSpan(range.start, range.end);
    const articleDailyTotals = span.map((day) => ({
      date: day.iso,
      article_views: 0,
      article_unique_visitors: 0
    }));
    const articleDetails = new Map();
    const combinedItems = [];
    const variantItems = [];

    state.articleGroups.forEach((group) => {
      const detail = buildMockArticleDetail(group, span);
      articleDetails.set(group.id, detail);

      if (detail.combined.views > 0) {
        const languages = {};
        ["en", "zh"].forEach((lang) => {
          const stats = detail.by_language[lang];
          if (stats.views > 0 || stats.unique_visitors > 0) {
            languages[lang] = {
              views: stats.views,
              unique_visitors: stats.unique_visitors
            };
            variantItems.push({
              article_id: group.id,
              lang,
              views: stats.views,
              unique_visitors: stats.unique_visitors,
              languages: {
                [lang]: {
                  views: stats.views,
                  unique_visitors: stats.unique_visitors
                }
              }
            });
          }
        });

        combinedItems.push({
          article_id: group.id,
          lang: null,
          views: detail.combined.views,
          unique_visitors: detail.combined.unique_visitors,
          languages
        });
      }

      detail.daily.forEach((row, index) => {
        articleDailyTotals[index].article_views += row.combined.views;
        articleDailyTotals[index].article_unique_visitors += row.combined.unique_visitors;
      });
    });

    const overviewDaily = span.map((day, index) => {
      const pageMetrics = buildMockPageMetrics(day, index);
      const articleMetrics = articleDailyTotals[index];
      const siteViews = pageMetrics.views + articleMetrics.article_views;
      const siteUnique = Math.min(
        siteViews,
        Math.max(
          pageMetrics.unique,
          Math.round((pageMetrics.unique * 0.72) + (articleMetrics.article_unique_visitors * 0.62))
        )
      );
      return {
        date: day.iso,
        site_views: siteViews,
        site_unique_visitors: siteUnique,
        article_views: articleMetrics.article_views,
        article_unique_visitors: articleMetrics.article_unique_visitors
      };
    });

    const overview = {
      from: range.start,
      to: range.end,
      summary: overviewDaily.reduce(
        (totals, row) => {
          totals.site_views += row.site_views;
          totals.site_unique_visitors += row.site_unique_visitors;
          totals.article_views += row.article_views;
          totals.article_unique_visitors += row.article_unique_visitors;
          return totals;
        },
        {
          site_views: 0,
          site_unique_visitors: 0,
          article_views: 0,
          article_unique_visitors: 0
        }
      ),
      daily: overviewDaily
    };

    const snapshot = {
      articleDetails,
      combinedItems: sortArticleRows(combinedItems),
      overview,
      span,
      variantItems: sortArticleRows(variantItems)
    };
    state.mockCache.set(cacheKey, snapshot);
    return snapshot;
  };

  const buildMockSessionPayload = () => {
    const session = getMockSession();
    if (!session) {
      throw new Error("Mock sign-in required.");
    }

    return {
      authorized: true,
      groups: ["analytics-admin"],
      user: {
        email: session.email,
        name: session.name,
        sub: session.sub,
        username: session.username
      }
    };
  };

  const mockApiFetch = async (path) => {
    const url = new URL(path, window.location.origin);
    const pathname = url.pathname;
    const from = url.searchParams.get("from");
    const to = url.searchParams.get("to");
    const range = {
      start: from || buildRangePreset(30).start,
      end: to || utcToday()
    };
    validateRange(range);
    const snapshot = getMockRangeSnapshot(range);

    if (pathname === "/analytics-api/admin/session") {
      return buildMockSessionPayload();
    }

    if (pathname === "/analytics-api/admin/overview") {
      buildMockSessionPayload();
      return snapshot.overview;
    }

    if (pathname === "/analytics-api/admin/articles") {
      buildMockSessionPayload();
      const group = url.searchParams.get("group") || "combined";
      const limit = Math.max(1, Math.min(100, Number(url.searchParams.get("limit") || "50")));
      const items = group === "variant" ? snapshot.variantItems : snapshot.combinedItems;
      return {
        from: range.start,
        to: range.end,
        group,
        items: items.slice(0, limit),
        next_cursor: items.length > limit ? String(limit) : null
      };
    }

    if (pathname.startsWith("/analytics-api/admin/articles/")) {
      buildMockSessionPayload();
      const articleId = decodeURIComponent(pathname.replace("/analytics-api/admin/articles/", ""));
      return snapshot.articleDetails.get(articleId) || buildEmptyArticleDetail(articleId, snapshot.span);
    }

    throw new Error(`Unsupported mock route: ${pathname}`);
  };

  const apiFetch = async (path) => {
    if (isMockModeEnabled()) {
      return mockApiFetch(path);
    }

    const response = await fetch(path, {
      cache: "no-store",
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      let apiMessage = "";
      try {
        const payload = await response.json();
        apiMessage = String(payload?.error || payload?.message || "").trim();
      } catch (error) {}

      if (response.status === 401) {
        throw createDashboardError("Your admin session expired. Please sign in again.", {
          action: "signin",
          clearToken: true,
          title: "Session expired"
        });
      }

      if (response.status === 403) {
        const lacksAdminGroup =
          apiMessage === "Authenticated user is not in the analytics admin group.";
        throw createDashboardError(
          lacksAdminGroup
            ? "This account is signed in, but it does not have access to the private analytics dashboard. Add it to the analytics-admin Cognito group, then sign in again."
            : apiMessage || "Access to the private analytics dashboard was denied.",
          {
            action: "signin",
            clearToken: true,
            title: "Access denied"
          }
        );
      }

      throw createDashboardError(apiMessage || `API request failed: HTTP ${response.status}`, {
        title: "Analytics unavailable"
      });
    }

    return response.json();
  };

  const buildAuthorizeUrl = async () => {
    const verifier = randomToken();
    const stateToken = randomToken();
    const challenge = await buildPkceChallenge(verifier);
    sessionStorage.setItem(STORAGE_KEYS.pkceVerifier, verifier);
    sessionStorage.setItem(STORAGE_KEYS.pkceState, stateToken);

    const redirectUri = `${state.config.admin.site_base_url}${state.config.cognito.redirect_path}`;
    const url = new URL(`${state.config.cognito.domain_url}/oauth2/authorize`);
    url.searchParams.set("response_type", "code");
    url.searchParams.set("client_id", state.config.cognito.client_id);
    url.searchParams.set("redirect_uri", redirectUri);
    url.searchParams.set("scope", state.config.cognito.scopes.join(" "));
    url.searchParams.set("code_challenge_method", "S256");
    url.searchParams.set("code_challenge", challenge);
    url.searchParams.set("state", stateToken);
    return url.toString();
  };

  const beginLogin = async () => {
    const authorizeUrl = await buildAuthorizeUrl();
    window.location.assign(authorizeUrl);
  };

  const exchangeCodeForToken = async (code, returnedState) => {
    const storedState = sessionStorage.getItem(STORAGE_KEYS.pkceState);
    const verifier = sessionStorage.getItem(STORAGE_KEYS.pkceVerifier);
    if (!storedState || !verifier || storedState !== returnedState) {
      throw createDashboardError("The sign-in callback could not be verified. Please start the login flow again.", {
        action: "signin",
        clearToken: true,
        title: "Sign-in failed"
      });
    }

    const redirectUri = `${state.config.admin.site_base_url}${state.config.cognito.redirect_path}`;
    const response = await fetch(`${state.config.cognito.domain_url}/oauth2/token`, {
      method: "POST",
      headers: {
        "content-type": "application/x-www-form-urlencoded"
      },
      body: new URLSearchParams({
        client_id: state.config.cognito.client_id,
        code,
        code_verifier: verifier,
        grant_type: "authorization_code",
        redirect_uri: redirectUri
      }).toString()
    });

    if (!response.ok) {
      throw createDashboardError(
        `The hosted sign-in flow completed, but the session token exchange failed with HTTP ${response.status}.`,
        {
          action: "signin",
          clearToken: true,
          title: "Sign-in failed"
        }
      );
    }

    const payload = await response.json();
    storeToken(payload);
    sessionStorage.removeItem(STORAGE_KEYS.pkceState);
    sessionStorage.removeItem(STORAGE_KEYS.pkceVerifier);
    const cleanUrl = `${window.location.origin}${window.location.pathname}`;
    window.history.replaceState({}, "", cleanUrl);
  };

  const signOut = () => {
    if (isMockModeEnabled()) {
      clearToken();
      clearMockSession();
      window.location.reload();
      return;
    }

    clearToken();
    if (!state.config?.cognito?.domain_url || !state.config?.admin?.site_base_url) {
      window.location.reload();
      return;
    }

    const logoutUrl = new URL(`${state.config.cognito.domain_url}/logout`);
    logoutUrl.searchParams.set("client_id", state.config.cognito.client_id);
    logoutUrl.searchParams.set("logout_uri", `${state.config.admin.site_base_url}${state.config.cognito.redirect_path}`);
    window.location.assign(logoutUrl.toString());
  };

  const loadConfig = async () => {
    state.config = await fetchJson(CONFIG_PATH);
  };

  const loadArticleIndex = async () => {
    const payload = await fetchJson(ARTICLES_INDEX_PATH);
    const groups = new Map();

    (payload.articles || []).forEach((article) => {
      const id = String(article.id || "").trim();
      const lang = String(article.lang || "").trim();
      if (!id || !lang) {
        return;
      }

      state.articleLookup.set(`${id}:${lang}`, article);
      const current = groups.get(id) || {
        id,
        pageUrlsByLang: {},
        searchText: "",
        titlesByLang: {}
      };
      current.pageUrlsByLang[lang] = article.page_url;
      current.titlesByLang[lang] = article.title;
      current.searchText = `${current.searchText} ${article.title || ""}`.trim().toLowerCase();
      groups.set(id, current);
    });

    state.articleGroups = [...groups.values()].sort((a, b) =>
      (a.titlesByLang.en || a.titlesByLang.zh || a.id).localeCompare(b.titlesByLang.en || b.titlesByLang.zh || b.id)
    );
  };

  const getCurrentRange = () => ({
    end: els.endInput.value || utcToday(),
    start: els.startInput.value || buildRangePreset(30).start
  });

  const setRange = ({ start, end }, preset = state.rangePreset) => {
    state.rangePreset = preset;
    els.startInput.value = start;
    els.endInput.value = end;
    els.presetButtons.forEach((button) => {
      const active = button.dataset.rangePreset === preset;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  };

  const validateRange = ({ start, end }) => {
    const startDate = new Date(`${start}T00:00:00Z`);
    const endDate = new Date(`${end}T00:00:00Z`);
    if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime()) || endDate < startDate) {
      throw new Error("Choose a valid date range.");
    }
    const dayCount = Math.floor((endDate - startDate) / 86400000) + 1;
    if (dayCount > 365) {
      throw new Error("Date range must be 365 days or fewer.");
    }
  };

  const renderSummaryCards = (summary) => {
    const cards = [
      { label: "Site views", value: summary.site_views },
      { label: "Site unique visitors", value: summary.site_unique_visitors },
      { label: "Article views", value: summary.article_views },
      { label: "Article unique visitors", value: summary.article_unique_visitors }
    ];

    els.summaryCards.innerHTML = cards
      .map(
        (card) => `
          <article class="card analytics-metric-card">
            <p class="meta">${escapeHtml(card.label)}</p>
            <h3>${formatNumber(card.value)}</h3>
          </article>
        `
      )
      .join("");
  };

  const renderDashboardLoading = (message = "Loading analytics dashboard.") => {
    const loadingCards = [
      "Site views",
      "Site unique visitors",
      "Article views",
      "Article unique visitors"
    ];

    els.dashboard.setAttribute("aria-busy", "true");
    els.summaryCards.innerHTML = loadingCards
      .map(
        (label) => `
          <article class="card analytics-metric-card analytics-loading-card">
            <p class="meta">${escapeHtml(label)}</p>
            <h3>Loading...</h3>
            <p class="meta analytics-loading-copy">${escapeHtml(message)}</p>
          </article>
        `
      )
      .join("");
    els.trendCaption.textContent = message;
    els.trendChart.innerHTML = '<p class="meta analytics-loading-copy">Loading daily trend...</p>';
    els.topArticlesMeta.textContent = message;
    els.topArticlesTable.innerHTML = '<article class="card analytics-loading-card"><p class="meta analytics-loading-copy">Loading top articles...</p></article>';
    els.articleDetailMeta.innerHTML = '<p class="meta analytics-loading-copy">Loading article drilldown...</p>';
    els.articleDetailChart.innerHTML = "";
  };

  const renderLineChart = (container, rows, valueKey, emptyText) => {
    if (!rows.length || rows.every((row) => Number(row[valueKey] || 0) === 0)) {
      container.innerHTML = `<p class="meta">${escapeHtml(emptyText)}</p>`;
      return;
    }

    const maxValue = Math.max(...rows.map((row) => Number(row[valueKey] || 0)), 1);
    const width = 720;
    const height = 220;
    const points = rows
      .map((row, index) => {
        const x = rows.length === 1 ? width / 2 : (index / (rows.length - 1)) * width;
        const y = height - (Number(row[valueKey] || 0) / maxValue) * (height - 24) - 12;
        return `${x},${y}`;
      })
      .join(" ");

    const labels = rows
      .map(
        (row, index) => `
          <div class="analytics-chart-label" style="--label-index:${index};--label-count:${rows.length}">
            <span>${escapeHtml(formatDateLabel(row.date))}</span>
            <strong>${formatNumber(row[valueKey])}</strong>
          </div>
        `
      )
      .join("");

    container.innerHTML = `
      <div class="analytics-chart-frame">
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Daily analytics trend">
          <polyline class="analytics-chart-line" fill="none" points="${escapeHtml(points)}"></polyline>
        </svg>
      </div>
      <div class="analytics-chart-labels">${labels}</div>
    `;
  };

  const displayArticleTitle = (articleId) => {
    const match = state.articleGroups.find((item) => item.id === articleId);
    if (!match) {
      return articleId;
    }
    return match.titlesByLang.en || match.titlesByLang.zh || articleId;
  };

  const linkListForArticle = (articleId) => {
    const match = state.articleGroups.find((item) => item.id === articleId);
    if (!match) {
      return "";
    }

    return Object.entries(match.pageUrlsByLang)
      .map(
        ([lang, href]) =>
          `<a class="tag" href="../${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(lang.toUpperCase())}</a>`
      )
      .join("");
  };

  const languageBadgeListForArticle = (articleId) => {
    const match = state.articleGroups.find((item) => item.id === articleId);
    if (!match) {
      return "";
    }

    return Object.keys(match.pageUrlsByLang)
      .sort()
      .map((lang) => `<span class="tag">${escapeHtml(lang.toUpperCase())}</span>`)
      .join("");
  };

  const renderTopArticles = (payload) => {
    if (!payload.items.length) {
      els.topArticlesTable.innerHTML = '<article class="card"><p>No article data for this range yet.</p></article>';
      els.topArticlesMeta.textContent = "";
      return;
    }

    els.topArticlesMeta.textContent = `Showing ${payload.items.length} article row(s) from ${payload.from} to ${payload.to}`;
    els.topArticlesTable.innerHTML = `
      <div class="analytics-table-wrap">
        <table class="analytics-table">
          <thead>
            <tr>
              <th>Article</th>
              <th>Views</th>
              <th>Unique</th>
              <th>Variants</th>
            </tr>
          </thead>
          <tbody>
            ${payload.items
              .map((item) => {
                const articleId = item.article_id;
                const title = displayArticleTitle(articleId);
                const variantLabel =
                  payload.group === "variant"
                    ? escapeHtml((item.lang || "").toUpperCase())
                    : Object.keys(item.languages || {})
                        .sort()
                        .map((lang) => `<span class="tag">${escapeHtml(lang.toUpperCase())}</span>`)
                        .join("");
                return `
                  <tr data-article-row="${escapeHtml(articleId)}">
                    <td>
                      <button class="analytics-table-link" type="button" data-article-open="${escapeHtml(articleId)}">${escapeHtml(title)}</button>
                    </td>
                    <td>${formatNumber(item.views)}</td>
                    <td>${formatNumber(item.unique_visitors)}</td>
                    <td>${variantLabel}</td>
                  </tr>
                `;
              })
              .join("")}
          </tbody>
        </table>
      </div>
    `;
  };

  const renderArticleSearchResults = (query) => {
    const normalized = String(query || "").trim().toLowerCase();
    const matches = normalized
      ? state.articleGroups.filter((group) => group.searchText.includes(normalized)).slice(0, 8)
      : state.articleGroups.slice(0, 8);

    els.articleSearchResults.innerHTML = matches
      .map(
        (group) => `
          <button class="card analytics-search-result" type="button" data-article-open="${escapeHtml(group.id)}">
            <p class="meta">${escapeHtml(group.id)}</p>
            <h3>${escapeHtml(group.titlesByLang.en || group.titlesByLang.zh || group.id)}</h3>
            <div class="tag-list">${languageBadgeListForArticle(group.id)}</div>
          </button>
        `
      )
      .join("");
  };

  const renderArticleDetail = (payload) => {
    state.activeArticleId = payload.article_id;
    els.articleDetailMeta.innerHTML = `
      <h3>${escapeHtml(displayArticleTitle(payload.article_id))}</h3>
      <p class="meta">
        Combined views: ${formatNumber(payload.combined.views)} / Combined unique visitors: ${formatNumber(payload.combined.unique_visitors)}
      </p>
      <div class="tag-list">${linkListForArticle(payload.article_id)}</div>
      <div class="analytics-language-breakdown">
        <div class="card analytics-language-card">
          <p class="meta">English</p>
          <h4>${formatNumber(payload.by_language.en.views)} views</h4>
          <p>${formatNumber(payload.by_language.en.unique_visitors)} unique visitors</p>
        </div>
        <div class="card analytics-language-card">
          <p class="meta">中文</p>
          <h4>${formatNumber(payload.by_language.zh.views)} views</h4>
          <p>${formatNumber(payload.by_language.zh.unique_visitors)} unique visitors</p>
        </div>
      </div>
    `;
    renderLineChart(
      els.articleDetailChart,
      payload.daily.map((row) => ({
        date: row.date,
        views: row.combined.views
      })),
      "views",
      "No article trend is available for this range yet."
    );
  };

  const getRangeQuery = () => {
    const range = getCurrentRange();
    validateRange(range);
    return `from=${encodeURIComponent(range.start)}&to=${encodeURIComponent(range.end)}`;
  };

  const refreshDashboard = async ({ showLoadingState = false } = {}) => {
    setSignedInShell();
    if (showLoadingState) {
      renderDashboardLoading("Loading analytics dashboard.");
    } else {
      els.dashboard.setAttribute("aria-busy", "true");
    }

    const query = getRangeQuery();
    try {
      const [, overviewPayload, topArticlesPayload] = await Promise.all([
        apiFetch("/analytics-api/admin/session"),
        apiFetch(`/analytics-api/admin/overview?${query}`),
        apiFetch(`/analytics-api/admin/articles?${query}&group=${encodeURIComponent(state.topArticlesGroup)}&limit=20`)
      ]);

      renderSummaryCards(overviewPayload.summary || {});
      renderLineChart(els.trendChart, overviewPayload.daily || [], "site_views", "No site activity is available for this range yet.");
      els.trendCaption.textContent = `Daily site views from ${overviewPayload.from} to ${overviewPayload.to}`;
      renderTopArticles(topArticlesPayload);

      const articleId = state.activeArticleId || topArticlesPayload.items?.[0]?.article_id;
      if (articleId) {
        const detailPayload = await apiFetch(`/analytics-api/admin/articles/${encodeURIComponent(articleId)}?${query}`);
        renderArticleDetail(detailPayload);
      } else {
        els.articleDetailMeta.innerHTML = '<p class="meta">Select an article to inspect its trend.</p>';
        els.articleDetailChart.innerHTML = "";
      }
    } finally {
      els.dashboard.setAttribute("aria-busy", "false");
    }
  };

  const handleArticleOpen = async (articleId) => {
    const query = getRangeQuery();
    const detailPayload = await apiFetch(`/analytics-api/admin/articles/${encodeURIComponent(articleId)}?${query}`);
    renderArticleDetail(detailPayload);
  };

  const authActionMarkup = (type, label) =>
    `<button class="button-link analytics-inline-action" type="button" data-auth-action="${escapeHtml(type)}">${escapeHtml(label)}</button>`;

  const attachEvents = () => {
    els.authActions.addEventListener("click", async (event) => {
      const signInButton = event.target.closest("[data-auth-action='signin']");
      if (signInButton) {
        try {
          await beginLogin();
        } catch (error) {
          setAuthState({
            title: "Sign-in unavailable",
            message: error instanceof Error ? error.message : "Unable to start sign-in."
          });
        }
        return;
      }

      const mockButton = event.target.closest("[data-auth-action='mock-signin']");
      if (!mockButton) {
        return;
      }

      storeMockSession();
      await refreshDashboard().catch((error) => {
        presentDashboardError(error, {
          fallbackMessage: "Failed to load mock analytics.",
          fallbackTitle: "Analytics unavailable",
          mockFallbackTitle: "Mock analytics unavailable"
        });
      });
    });

    els.signOutButton.addEventListener("click", signOut);

    els.presetButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const preset = button.dataset.rangePreset || "30d";
        const days = Number(preset.replace("d", ""));
        setRange(buildRangePreset(days), preset);
      });
    });

    els.rangeForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      state.rangePreset = "custom";
      els.presetButtons.forEach((button) => {
        button.classList.remove("is-active");
        button.setAttribute("aria-pressed", "false");
      });
      await refreshDashboard().catch((error) => {
        presentDashboardError(error, {
          fallbackMessage: "Failed to load analytics.",
          fallbackTitle: "Unable to load analytics",
          mockFallbackTitle: "Unable to load mock analytics"
        });
      });
    });

    els.topArticlesModeButtons.forEach((button) => {
      button.addEventListener("click", async () => {
        const nextMode = button.dataset.articlesGroup || "combined";
        state.topArticlesGroup = nextMode;
        els.topArticlesModeButtons.forEach((candidate) => {
          const active = candidate === button;
          candidate.classList.toggle("is-active", active);
          candidate.setAttribute("aria-pressed", String(active));
        });
        await refreshDashboard().catch((error) => {
          presentDashboardError(error, {
            fallbackMessage: "Failed to load analytics.",
            fallbackTitle: "Unable to load analytics",
            mockFallbackTitle: "Unable to load mock analytics"
          });
        });
      });
    });

    els.topArticlesTable.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-article-open]");
      if (!button) {
        return;
      }
      await handleArticleOpen(button.dataset.articleOpen);
    });

    els.articleSearchResults.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-article-open]");
      if (!button) {
        return;
      }
      await handleArticleOpen(button.dataset.articleOpen);
    });

    els.articleSearchInput.addEventListener("input", () => {
      renderArticleSearchResults(els.articleSearchInput.value);
    });
  };

  const processCallbackIfNeeded = async () => {
    const params = new URLSearchParams(window.location.search);
    const error = params.get("error");
    if (error) {
      const message = params.get("error_description") || "Sign-in was cancelled or rejected.";
      throw createDashboardError(message, {
        action: "signin",
        clearToken: true,
        title: "Sign-in failed"
      });
    }

    const code = params.get("code");
    const returnedState = params.get("state");
    if (!code) {
      return;
    }

    setAuthState({
      title: "Completing sign-in",
      message: "Exchanging the Cognito authorization code for a session token."
    });
    await exchangeCodeForToken(code, returnedState || "");
    return true;
  };

  const initialize = async () => {
    attachEvents();
    setRange(buildRangePreset(30), "30d");

    try {
      await Promise.all([loadConfig(), loadArticleIndex()]);
      renderArticleSearchResults("");

      if (isMockModeEnabled()) {
        const mockSession = getMockSession();
        if (!mockSession) {
          setAuthState({
            title: "Local analytics preview",
            message: "Localhost uses generated mock analytics data so you can inspect the private dashboard without Cognito, API Gateway, or DynamoDB.",
            actions: authActionMarkup("mock-signin", "Open mock dashboard")
          });
          return;
        }

        await refreshDashboard();
        return;
      }

      if (!state.config?.admin?.enabled) {
        setAuthState({
          title: "Production-only admin",
          message: "The private analytics dashboard is only enabled on the production site."
        });
        return;
      }

      if (!isConfigUsable()) {
        setAuthState({
          title: "Production-only admin",
          message: "This analytics login is configured only for the production site origin. Previews use the static shell only."
        });
        return;
      }

      const completedSignIn = await processCallbackIfNeeded();
      const token = getStoredToken();
      if (!token) {
        setAuthState({
          title: "Private analytics",
          message: "Sign in with your Cognito admin username to access site and article analytics.",
          actions: authActionMarkup("signin", "Sign in")
        });
        return;
      }

      await refreshDashboard({ showLoadingState: completedSignIn });
    } catch (error) {
      presentDashboardError(error, {
        fallbackMessage: "Failed to initialize the analytics dashboard.",
        fallbackTitle: "Analytics unavailable",
        mockFallbackTitle: "Mock analytics unavailable"
      });
    }
  };

  initialize();
})();
