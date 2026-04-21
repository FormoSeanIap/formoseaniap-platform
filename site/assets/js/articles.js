(() => {
  const listRoot = document.querySelector("[data-articles-list]");
  const detailRoot = document.querySelector("[data-article-detail]");
  if (!listRoot && !detailRoot) {
    return;
  }

  const INDEX_PATH = "data/articles.index.json";
  const SEARCH_INDEX_PATH = "data/articles.search.json";
  const LANGUAGE_OPTIONS = [
    { value: "en", label: "English" },
    { value: "zh", label: "中文" }
  ];
  const DEFAULT_LANGS = LANGUAGE_OPTIONS.map((entry) => entry.value);
  const CATEGORY_LABELS = {
    technical: { en: "Technical", zh: "技術" },
    review: { en: "Review", zh: "評論" },
    other: { en: "Other", zh: "其他" }
  };
  const SEARCH_MODES = ["title", "series", "content"];

  const COPY = {
    en: {
      allCategories: "All Categories",
      allSubcategories: "All Subcategories",
      allTags: "All Tags",
      readArticle: "Read article",
      readMedium: "Read on Medium",
      openCollection: "Open collection",
      backToList: "Back to articles",
      backToTop: "Back to top",
      backToHome: "Back to articles home",
      clearExtraFilters: "Clear extra filters",
      seriesHome: "Series home",
      seriesKicker: "Series Collection",
      categoryPrefix: "Category",
      subcategoryPrefix: "Subcategory",
      tagPrefix: "Tag",
      previousPart: "Previous Part",
      nextPart: "Next Part",
      previousInSeries: "Previous in series",
      nextInSeries: "Next in series",
      noCollections: "No collections match the current filters.",
      noArticles: "No articles match the current filters.",
      loadError: "Failed to load article data.",
      notFound: "Article not found.",
      searchPlaceholder: "Search articles by title, series, or keywords",
      searchTitle: "Title",
      searchSeries: "Series",
      searchContent: "Content",
      loadMore: "Load more",
      loadingSearch: "Loading search index...",
      collectionsSummary: (count) => `Current filtered results: ${count} collection(s)`,
      articlesSummary: (count) => `Current filtered results: ${count} article(s)`,
      searchStatus: (modeLabel, query, count, viewMode) =>
        `${modeLabel} search for "${query}" / ${count} ${viewMode === "collections" ? "collection(s)" : "article(s)"}`,
      progressiveStatus: (visibleCount, totalCount) => `Showing ${visibleCount} of ${totalCount}`,
      published: (dateLabel) => `Published ${dateLabel}`,
      readTime: (minutes) => `${minutes} min read`,
      collectionCount: (count) => `${count} article(s)`,
      seriesMeta: (totalCount, visibleCount, languages) =>
        `${totalCount} part(s) in this collection / showing ${visibleCount} article(s) / Languages: ${languages.join(", ")}`
    },
    zh: {
      allCategories: "全部分類",
      allSubcategories: "全部子分類",
      allTags: "全部標籤",
      readArticle: "閱讀文章",
      readMedium: "前往 Medium",
      openCollection: "查看系列",
      backToList: "回到文章列表",
      backToTop: "回到頂部",
      backToHome: "回到文章首頁",
      clearExtraFilters: "清除其他篩選",
      seriesHome: "系列首頁",
      seriesKicker: "系列文章",
      categoryPrefix: "分類",
      subcategoryPrefix: "子分類",
      tagPrefix: "標籤",
      previousPart: "上一部",
      nextPart: "下一部",
      previousInSeries: "系列上一篇",
      nextInSeries: "系列下一篇",
      noCollections: "目前沒有符合篩選條件的系列／作品。",
      noArticles: "目前沒有符合篩選條件的文章。",
      loadError: "無法載入文章資料。",
      notFound: "找不到文章。",
      searchPlaceholder: "搜尋文章標題、系列或內文關鍵字",
      searchTitle: "標題",
      searchSeries: "系列",
      searchContent: "內容",
      loadMore: "顯示更多",
      loadingSearch: "正在載入搜尋索引...",
      collectionsSummary: (count) => `目前篩選結果：${count} 個系列／作品`,
      articlesSummary: (count) => `目前篩選結果：${count} 篇文章`,
      searchStatus: (modeLabel, query, count, viewMode) =>
        `${modeLabel}搜尋：「${query}」 / ${count} ${viewMode === "collections" ? "個系列／作品" : "篇文章"}`,
      progressiveStatus: (visibleCount, totalCount) => `已顯示 ${visibleCount} / ${totalCount}`,
      published: (dateLabel) => `發布 ${dateLabel}`,
      readTime: (minutes) => `${minutes} 分鐘閱讀`,
      collectionCount: (count) => `${count} 篇`,
      seriesMeta: (totalCount, visibleCount, languages) =>
        `系列共 ${totalCount} 部 / 目前顯示 ${visibleCount} 篇 / 語言：${languages.join("、")}`
    }
  };

  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const formatDate = (value, lang) => {
    if (!value) {
      return "";
    }
    const locale = lang === "zh" ? "zh-TW" : "en-US";
    const dt = new Date(`${value}T00:00:00Z`);
    return new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "2-digit" }).format(dt);
  };

  const localeForLanguage = (lang) => (lang === "zh" ? "zh-TW" : "en-US");

  const compareLabels = (a, b, lang) => a.localeCompare(b, localeForLanguage(lang));

  const languageLabel = (lang) => LANGUAGE_OPTIONS.find((entry) => entry.value === lang)?.label || lang;

  const tagLabel = (indexData, tag, lang) => indexData.tags?.[tag]?.[lang] || tag;

  const categoryLabel = (category, lang) => CATEGORY_LABELS[category]?.[lang] || category;

  const subcategoryLabel = (value, fallbackLabel = "") =>
    fallbackLabel || String(value || "").replaceAll("_", " ").trim();

  const partLabel = (partNumber, lang) => {
    if (!partNumber) {
      return "";
    }
    return lang === "zh" ? `第 ${partNumber} 部` : `Part ${partNumber}`;
  };

  const normalizeSearchMode = (value) => (SEARCH_MODES.includes(value) ? value : "title");

  const normalizeSearchText = (value) =>
    String(value ?? "")
      .normalize("NFKC")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();

  const seriesSortValue = (value) => (value == null ? Number.MAX_SAFE_INTEGER : Number(value));

  const compareSeriesItems = (a, b) => {
    const aSeriesOrder = seriesSortValue(a.series_order);
    const bSeriesOrder = seriesSortValue(b.series_order);
    if (aSeriesOrder !== bSeriesOrder) {
      return aSeriesOrder - bSeriesOrder;
    }

    const aPart = seriesSortValue(a.part_number);
    const bPart = seriesSortValue(b.part_number);
    if (aPart !== bPart) {
      return aPart - bPart;
    }

    if (a.published_at !== b.published_at) {
      return String(a.published_at).localeCompare(String(b.published_at));
    }

    return String(a.title || "").localeCompare(String(b.title || ""));
  };

  const buildSeriesNavLabel = (copy, currentArticle, adjacentArticle, direction) => {
    const currentHasPart = currentArticle?.part_number != null;
    const adjacentHasPart = adjacentArticle?.part_number != null;
    const usePartCopy = currentHasPart && adjacentHasPart;
    const baseLabel =
      direction === "previous"
        ? usePartCopy
          ? copy.previousPart
          : copy.previousInSeries
        : usePartCopy
          ? copy.nextPart
          : copy.nextInSeries;
    const navLang = currentArticle?.lang || adjacentArticle?.lang || "en";
    const suffix = adjacentHasPart ? ` (${partLabel(adjacentArticle.part_number, navLang)})` : "";
    return `${baseLabel}${suffix}`;
  };

  const arrayify = (value) => {
    if (Array.isArray(value)) {
      return value;
    }
    if (value == null || value === "") {
      return [];
    }
    return [value];
  };

  const uniqueOrdered = (values, order = []) => {
    const seen = new Set();
    const deduped = [];
    values.forEach((value) => {
      if (!value || seen.has(value)) {
        return;
      }
      seen.add(value);
      deduped.push(value);
    });

    if (!order.length) {
      return deduped;
    }

    return [
      ...order.filter((value) => seen.has(value)),
      ...deduped.filter((value) => !order.includes(value))
    ];
  };

  const normalizeSelection = (values, validValues) =>
    uniqueOrdered(
      arrayify(values).filter((value) => validValues.includes(value)),
      validValues
    );

  const normalizeLangSelection = (values) => {
    const normalized = normalizeSelection(values, DEFAULT_LANGS);
    return normalized.length ? normalized : [...DEFAULT_LANGS];
  };

  const isDefaultLangSelection = (langs) =>
    langs.length === DEFAULT_LANGS.length && DEFAULT_LANGS.every((lang) => langs.includes(lang));

  const arrayEquals = (a, b) =>
    a.length === b.length && a.every((value, index) => value === b[index]);

  const languageSortRank = (lang) => DEFAULT_LANGS.indexOf(lang);

  const stableCategoryOrder = (articles) =>
    Object.keys(CATEGORY_LABELS).filter((category) => articles.some((article) => article.category === category));

  const collectSubcategoryMeta = (articles) => {
    const map = new Map();
    articles.forEach((article) => {
      if (!article.subcategory_id || map.has(article.subcategory_id)) {
        return;
      }
      map.set(
        article.subcategory_id,
        subcategoryLabel(article.subcategory_id, article.subcategory_label)
      );
    });
    return map;
  };

  const collectTagValues = (articles) =>
    [...new Set(articles.flatMap((article) => article.tags || []))];

  const getUiLanguage = (langs) =>
    langs.length === 1 && langs[0] === "zh" ? "zh" : "en";

  const serializePageParams = (params) => {
    const next = new URLSearchParams();
    const normalizedQuery = String(params.q || "").trim();

    if ("langs" in params) {
      const langs = normalizeLangSelection(params.langs);
      if (!isDefaultLangSelection(langs)) {
        langs.forEach((lang) => next.append("lang", lang));
      }
    } else if ("lang" in params) {
      arrayify(params.lang).filter(Boolean).forEach((lang) => next.append("lang", lang));
    }

    if ("categories" in params) {
      arrayify(params.categories).filter(Boolean).forEach((category) => next.append("category", category));
    } else if ("category" in params) {
      arrayify(params.category).filter(Boolean).forEach((category) => next.append("category", category));
    }

    if ("subcategories" in params) {
      arrayify(params.subcategories)
        .filter(Boolean)
        .forEach((subcategory) => next.append("subcategory", subcategory));
    } else if ("subcategory" in params) {
      arrayify(params.subcategory)
        .filter(Boolean)
        .forEach((subcategory) => next.append("subcategory", subcategory));
    }

    if ("tags" in params) {
      arrayify(params.tags).filter(Boolean).forEach((tag) => next.append("tag", tag));
    } else if ("tag" in params) {
      arrayify(params.tag).filter(Boolean).forEach((tag) => next.append("tag", tag));
    }

    if (params.series) {
      next.set("series", String(params.series));
    }

    if (normalizedQuery) {
      next.set("q", normalizedQuery);
      next.set("search", normalizeSearchMode(params.search || "title"));
    }

    return next.toString();
  };

  const buildPageUrl = (params) => {
    const qs = serializePageParams(params);
    return qs ? `articles.html?${qs}` : "articles.html";
  };

  const fetchJson = async (path) => {
    const res = await fetch(path, { cache: "no-cache" });
    if (!res.ok) {
      throw new Error(`Failed to load ${path}: HTTP ${res.status}`);
    }
    return res.json();
  };

  const renderFilterRow = (container, items) => {
    container.innerHTML = items.join("");
  };

  const translationLabel = (targetLang) => {
    if (targetLang === "zh") {
      return "中文版本";
    }
    if (targetLang === "en") {
      return "English Version";
    }
    return `${targetLang} Version`;
  };

  const searchModeLabel = (copy, mode) => {
    if (mode === "series") {
      return copy.searchSeries;
    }
    if (mode === "content") {
      return copy.searchContent;
    }
    return copy.searchTitle;
  };

  const buildToggleButton = ({ label, group, value = "", active = false, action = "toggle" }) => `
    <button
      class="tag filter-chip filter-chip-button${active ? " is-active" : ""}"
      type="button"
      data-filter-group="${escapeHtml(group)}"
      data-filter-value="${escapeHtml(value)}"
      data-filter-action="${escapeHtml(action)}"
      aria-pressed="${active ? "true" : "false"}"
    >
      ${escapeHtml(label)}
    </button>
  `;

  const toggleSelection = (selectedValues, value, orderedValues, { allowEmpty = true } = {}) => {
    if (selectedValues.includes(value)) {
      const next = selectedValues.filter((item) => item !== value);
      return !allowEmpty && next.length === 0 ? selectedValues : next;
    }
    return uniqueOrdered([...selectedValues, value], orderedValues);
  };

  const articleMatchesState = (
    article,
    state,
    {
      ignoreLangs = false,
      ignoreCategories = false,
      ignoreSubcategories = false,
      ignoreTags = false,
      ignoreSeries = false
    } = {}
  ) => {
    if (!ignoreLangs && !state.langs.includes(article.lang)) {
      return false;
    }
    if (!ignoreCategories && state.categories.length && !state.categories.includes(article.category)) {
      return false;
    }
    if (
      !ignoreSubcategories &&
      state.subcategories.length &&
      !state.subcategories.includes(article.subcategory_id || "")
    ) {
      return false;
    }
    if (
      !ignoreTags &&
      state.tags.length &&
      !state.tags.some((tag) => (article.tags || []).includes(tag))
    ) {
      return false;
    }
    if (!ignoreSeries && state.series && article.series_id !== state.series) {
      return false;
    }
    return true;
  };

  const buildCategoryOptions = (allArticles, state) => {
    const available = new Set(
      allArticles
        .filter((article) => articleMatchesState(article, state, { ignoreCategories: true }))
        .map((article) => article.category)
    );
    const values = stableCategoryOrder(allArticles).filter(
      (category) => available.has(category) || state.categories.includes(category)
    );
    return values.map((value) => ({ value }));
  };

  const buildSubcategoryOptions = (allArticles, state, uiLang, subcategoryMeta) => {
    const available = new Set(
      allArticles
        .filter((article) => articleMatchesState(article, state, { ignoreSubcategories: true }))
        .map((article) => article.subcategory_id)
        .filter(Boolean)
    );
    const values = [...new Set([...available, ...state.subcategories])];
    return values
      .map((value) => ({
        value,
        label: subcategoryMeta.get(value) || subcategoryLabel(value)
      }))
      .sort((a, b) => compareLabels(a.label, b.label, uiLang));
  };

  const buildTagOptions = (indexData, allArticles, state, uiLang) => {
    const available = new Set(
      allArticles
        .filter((article) => articleMatchesState(article, state, { ignoreTags: true }))
        .flatMap((article) => article.tags || [])
    );
    const values = [...new Set([...available, ...state.tags])];
    return values
      .map((value) => ({
        value,
        label: tagLabel(indexData, value, uiLang)
      }))
      .sort((a, b) => compareLabels(a.label, b.label, uiLang));
  };

  const pickPrimaryArticle = (articles, preferredLang) => {
    const sorted = [...articles].sort((a, b) => {
      const seriesOrderCompare = compareSeriesItems(a, b);
      if (seriesOrderCompare !== 0) {
        return seriesOrderCompare;
      }
      return languageSortRank(a.lang) - languageSortRank(b.lang);
    });

    return (
      sorted.find((article) => article.lang === preferredLang) ||
      sorted.find((article) => article.lang === "en") ||
      sorted[0]
    );
  };

  const buildCollectionTitle = (titlesByLang, uiLang, mergeLanguages) => {
    const orderedLangs =
      uiLang === "zh"
        ? ["zh", "en", ...DEFAULT_LANGS.filter((lang) => !["zh", "en"].includes(lang))]
        : ["en", "zh", ...DEFAULT_LANGS.filter((lang) => !["en", "zh"].includes(lang))];
    const orderedTitles = uniqueOrdered(
      orderedLangs.map((lang) => titlesByLang[lang]).filter(Boolean)
    );
    if (!orderedTitles.length) {
      return "";
    }
    if (!mergeLanguages) {
      return orderedTitles[0];
    }
    return orderedTitles.join(" / ");
  };

  const compareCollections = (a, b, lang) => {
    const aLatestPublishedAt = String(a.latest_published_at || "");
    const bLatestPublishedAt = String(b.latest_published_at || "");
    if (aLatestPublishedAt !== bLatestPublishedAt) {
      return bLatestPublishedAt.localeCompare(aLatestPublishedAt);
    }

    const titleCompare = compareLabels(a.title, b.title, lang);
    if (titleCompare !== 0) {
      return titleCompare;
    }

    return String(a.id || "").localeCompare(String(b.id || ""));
  };

  const buildCollections = (uiLang, articles, mergeLanguages) => {
    const grouped = new Map();
    articles.forEach((article) => {
      const baseKey = article.series_id || article.id;
      const key = mergeLanguages ? baseKey : `${article.lang}:${baseKey}`;
      const existing = grouped.get(key) || [];
      existing.push(article);
      grouped.set(key, existing);
    });

    return [...grouped.values()]
      .map((groupArticles) => {
        const langs = uniqueOrdered(
          groupArticles.map((article) => article.lang),
          DEFAULT_LANGS
        );
        const titlesByLang = {};
        langs.forEach((lang) => {
          const source = pickPrimaryArticle(
            groupArticles.filter((article) => article.lang === lang),
            lang
          );
          titlesByLang[lang] = source?.series_title || source?.title || "";
        });
        const primary = pickPrimaryArticle(groupArticles, uiLang);
        const uniqueCount = new Set(groupArticles.map((article) => article.id)).size;
        const latestPublishedAt = groupArticles.reduce((latest, article) => {
          const publishedAt = String(article.published_at || "");
          return publishedAt > latest ? publishedAt : latest;
        }, "");

        return {
          id: primary.series_id || primary.id,
          series_id: primary.series_id || primary.id,
          title: buildCollectionTitle(titlesByLang, uiLang, mergeLanguages),
          title_search: normalizeSearchText(Object.values(titlesByLang).join(" ")),
          category: primary.category,
          subcategory_id: primary.subcategory_id || "",
          subcategory_label: subcategoryLabel(primary.subcategory_id, primary.subcategory_label),
          excerpt: primary.excerpt || "",
          count: uniqueCount,
          languages: langs,
          titlesByLang,
          latest_published_at: latestPublishedAt,
          series_preview_image:
            primary.series_preview_image ||
            groupArticles.find((article) => article.series_preview_image)?.series_preview_image ||
            null,
          source_article: primary
        };
      })
      .sort((a, b) => compareCollections(a, b, uiLang));
  };

  const buildCollectionCoverBody = (collection, lang) => {
    if (collection.series_preview_image) {
      const alt = lang === "zh" ? `${collection.title} 封面` : `Cover for ${collection.title}`;
      return `
        <img
          class="collection-cover__image"
          src="${escapeHtml(collection.series_preview_image)}"
          alt="${escapeHtml(alt)}"
          loading="lazy"
        />
      `;
    }

    return `
      <div class="collection-cover__fallback">
        <p class="collection-cover__eyebrow">${escapeHtml(categoryLabel(collection.category, lang))}</p>
        <h3 class="collection-cover__title">${escapeHtml(collection.title)}</h3>
        <p class="collection-cover__subline">${escapeHtml(collection.subcategory_label)}</p>
      </div>
    `;
  };

  const buildLinkAttrs = (href, { external = false } = {}) =>
    external
      ? `href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer"`
      : `href="${escapeHtml(href)}"`;

  const renderCollectionCover = (collection, lang, href, extraClass = "") =>
    `
      <a class="card-media-link" ${buildLinkAttrs(href)} aria-label="${escapeHtml(
        lang === "zh" ? `開啟 ${collection.title}` : `Open ${collection.title}`
      )}">
        <div class="collection-cover${extraClass ? ` ${extraClass}` : ""}">${buildCollectionCoverBody(collection, lang)}</div>
      </a>
    `;

  const renderSeriesContextCover = (container, collection, lang) => {
    if (!container || !collection) {
      return;
    }
    container.className = "collection-cover collection-cover--context";
    container.innerHTML = buildCollectionCoverBody(collection, lang);
    container.hidden = false;
  };

  const renderCollectionCards = (uiLang, collections, state, copy) =>
    collections
      .map((collection) => {
        const href = buildPageUrl({
          langs: state.langs,
          categories: state.categories,
          subcategories: state.subcategories,
          tags: state.tags,
          series: collection.series_id,
          q: state.q,
          search: state.search
        });
        const meta = `${categoryLabel(collection.category, uiLang)} / ${collection.subcategory_label} / ${copy.collectionCount(collection.count)}`;
        const languageBadges =
          state.langs.length > 1
            ? `
              <div class="collection-language-badges">
                ${collection.languages
                  .map((lang) => `<span class="tag">${escapeHtml(languageLabel(lang))}</span>`)
                  .join("")}
              </div>
            `
            : "";

        return `
          <article class="card collection-card">
            ${renderCollectionCover(collection, uiLang, href)}
            <div class="collection-card-content">
              <p class="meta">${escapeHtml(meta)}</p>
              ${languageBadges}
              <h3>${escapeHtml(collection.title)}</h3>
              <p>${escapeHtml(collection.excerpt)}</p>
              <a class="button-link" href="${href}">${escapeHtml(copy.openCollection)}</a>
            </div>
          </article>
        `;
      })
      .join("");

  const renderArticleMedia = (article, uiLang) => {
    if (!article.preview_image) {
      return "";
    }
    const alt = uiLang === "zh" ? `${article.title} 預覽圖` : `Preview image for ${article.title}`;
    const href = article.external_url || article.page_url;
    return `
      <a class="card-media-link" ${buildLinkAttrs(href, { external: Boolean(article.external_url) })} aria-label="${escapeHtml(
        uiLang === "zh" ? `閱讀 ${article.title}` : `Read ${article.title}`
      )}">
        <div class="article-card-media">
          <img
            class="article-card-image"
            src="${escapeHtml(article.preview_image)}"
            alt="${escapeHtml(alt)}"
            loading="lazy"
          />
        </div>
      </a>
    `;
  };

  const renderArticleCards = (indexData, uiLang, items, state, copy) =>
    items
      .map((article) => {
        const tags = (article.tags || [])
          .map((tag) => {
            const nextTags = state.tags.includes(tag)
              ? [...state.tags]
              : uniqueOrdered([...state.tags, tag]);
            const href = buildPageUrl({
              langs: state.langs,
              categories: state.categories,
              subcategories: state.subcategories,
              tags: nextTags,
              series: state.series || article.series_id || "",
              q: state.q,
              search: state.search
            });
            return `<a class="tag" href="${href}">${escapeHtml(tagLabel(indexData, tag, uiLang))}</a>`;
          })
          .join("");

        const part = partLabel(article.part_number, article.lang);
        const seriesHref = article.series_id
          ? buildPageUrl({
              langs: state.langs,
              categories: state.categories,
              subcategories: state.subcategories,
              tags: state.tags,
              series: article.series_id,
              q: state.q,
              search: state.search
            })
          : "";
        const seriesMeta = article.series_title
          ? `<p class="meta"><a href="${seriesHref}">${escapeHtml(article.series_title)}</a>${part ? ` / ${escapeHtml(part)}` : ""}</p>`
          : part
            ? `<p class="meta">${escapeHtml(part)}</p>`
            : "";
        const linkLabel = article.external_url ? copy.readMedium : copy.readArticle;
        const linkAttrs = buildLinkAttrs(article.external_url || article.page_url, {
          external: Boolean(article.external_url)
        });
        const languageBadges =
          state.langs.length > 1
            ? `
              <div class="article-card-badges">
                <span class="tag">${escapeHtml(languageLabel(article.lang))}</span>
              </div>
            `
            : "";

        return `
          <article class="card article-card">
            ${renderArticleMedia(article, uiLang)}
            <div class="article-card-content">
              <p class="meta">${escapeHtml(categoryLabel(article.category, uiLang))} / ${escapeHtml(
                copy.readTime(article.read_time)
              )}</p>
              ${languageBadges}
              ${seriesMeta}
              <h3>${escapeHtml(article.title)}</h3>
              <p>${escapeHtml(article.excerpt || "")}</p>
              <p class="meta">${escapeHtml(copy.published(formatDate(article.published_at, uiLang)))}</p>
              <div class="tag-list">${tags}</div>
              <div class="article-card-link-row">
                <a class="button-link" ${linkAttrs}>${escapeHtml(linkLabel)}</a>
              </div>
            </div>
          </article>
        `;
      })
      .join("");

  const setDocumentLanguage = (lang) => {
    document.documentElement.setAttribute("lang", lang === "zh" ? "zh-Hant" : "en");
  };

  const SITE_URL = "https://www.formoseaniap.com";

  // Distinguish main tree vs engineering tree so the title prefix matches the
  // static template that ships for each. The two article.html files advertise
  // "Portfolio | Article" and "Engineering | Article" respectively; keeping
  // the runtime update consistent avoids a brief flash of the wrong prefix
  // while the fetch lands.
  const isEngineeringTree = () => {
    try {
      return window.location.pathname.startsWith("/engineer/");
    } catch (err) {
      return false;
    }
  };

  const titlePrefix = () => (isEngineeringTree() ? "Engineering" : "Portfolio");

  // Article page URLs are relative (`article.html?id=...&lang=...`). Resolve
  // them against the page's own location so the same helper works on
  // `/article.html` (main tree) and `/engineer/article.html` (engineering
  // tree). That way the runtime canonical and OG URLs always point at the
  // tree the reader is actually viewing.
  const buildArticleCanonicalUrl = (article, lang) => {
    try {
      const relative = article?.page_url || `article.html?id=${encodeURIComponent(article?.id || "")}&lang=${encodeURIComponent(lang)}`;
      // Resolve against the current location so both `/article.html?...`
      // (main site) and `/engineer/article.html?...` (engineering tree) are
      // produced correctly.
      const resolved = new URL(relative, window.location.href);
      return `${SITE_URL}${resolved.pathname}${resolved.search}`;
    } catch (err) {
      return `${SITE_URL}/article.html?id=${article?.id || ""}&lang=${lang}`;
    }
  };

  const ensureLinkElement = (rel) => {
    let node = document.querySelector(`link[rel="${rel}"]`);
    if (!node) {
      node = document.createElement("link");
      node.setAttribute("rel", rel);
      document.head.appendChild(node);
    }
    return node;
  };

  const setMetaByProperty = (property, content) => {
    const node = document.querySelector(`meta[property="${property}"]`);
    if (node) {
      node.setAttribute("content", content);
    }
  };

  const setMetaByName = (name, content) => {
    let node = document.querySelector(`meta[name="${name}"]`);
    if (!node) {
      node = document.createElement("meta");
      node.setAttribute("name", name);
      document.head.appendChild(node);
    }
    node.setAttribute("content", content);
  };

  const setDescriptionMeta = (content) => {
    const node = document.querySelector('meta[name="description"]');
    if (node) {
      node.setAttribute("content", content);
    } else {
      setMetaByName("description", content);
    }
  };

  // Update the canonical URL and Open Graph / Twitter Card metadata for the
  // article detail page once we know which article is actually being shown.
  // The static `article.html` template ships a generic description so link
  // previews fall back to something sensible if JS fails; this runtime pass
  // upgrades each share preview to the article's real title and excerpt.
  const applyArticleHeadMetadata = (article, lang) => {
    if (!article) {
      return;
    }

    const canonicalUrl = buildArticleCanonicalUrl(article, lang);
    const title = article.title || "";
    const description = (article.excerpt || "").trim() || title;
    const localeAttr = lang === "zh" ? "zh_TW" : "en_US";

    const canonical = ensureLinkElement("canonical");
    canonical.setAttribute("href", canonicalUrl);

    setDescriptionMeta(description);

    setMetaByProperty("og:title", title ? `${titlePrefix()} | ${title}` : `${titlePrefix()} | Article`);
    setMetaByProperty("og:description", description);
    setMetaByProperty("og:locale", localeAttr);
    // Ensure og:url exists (static template omits it for articles because the
    // canonical URL isn't knowable server-side). Insert a placeholder tag if
    // absent so future head-scrapers can find it.
    let ogUrl = document.querySelector('meta[property="og:url"]');
    if (!ogUrl) {
      ogUrl = document.createElement("meta");
      ogUrl.setAttribute("property", "og:url");
      document.head.appendChild(ogUrl);
    }
    ogUrl.setAttribute("content", canonicalUrl);

    setMetaByName("twitter:title", title ? `${titlePrefix()} | ${title}` : `${titlePrefix()} | Article`);
    setMetaByName("twitter:description", description);
  };

  const buildDetailActionLinks = (copy, article, lang, { includeBackToTop = false } = {}) => {
    const links = [
      `<a class="tag filter-chip" href="${buildPageUrl({ lang })}">${escapeHtml(copy.backToList)}</a>`
    ];

    if (article.series_id) {
      links.push(
        `<a class="tag filter-chip" href="${buildPageUrl({
          lang,
          category: article.category,
          subcategory: article.subcategory_id || "",
          series: article.series_id
        })}">${escapeHtml(copy.seriesHome)}</a>`
      );
    }

    if (article.external_url) {
      links.push(
        `<a class="tag filter-chip" href="${escapeHtml(
          article.external_url
        )}" target="_blank" rel="noopener noreferrer">${escapeHtml(copy.readMedium)}</a>`
      );
    }

    if (article.series_previous?.page_url) {
      const label = buildSeriesNavLabel(copy, article, article.series_previous, "previous");
      links.push(
        `<a class="tag filter-chip" href="${escapeHtml(article.series_previous.page_url)}">${escapeHtml(
          label
        )}</a>`
      );
    }

    if (article.series_next?.page_url) {
      const label = buildSeriesNavLabel(copy, article, article.series_next, "next");
      links.push(
        `<a class="tag filter-chip" href="${escapeHtml(article.series_next.page_url)}">${escapeHtml(
          label
        )}</a>`
      );
    }

    Object.entries(article.translations || {}).forEach(([targetLang, pageUrl]) => {
      links.push(
        `<a class="tag filter-chip" href="${escapeHtml(pageUrl)}">${escapeHtml(translationLabel(targetLang))}</a>`
      );
    });

    if (includeBackToTop) {
      links.push(`<a class="tag filter-chip" href="#article-top">${escapeHtml(copy.backToTop)}</a>`);
    }

    return links;
  };

  const createFallbackProgressiveList = (root, controls) => ({
    reset({ items = [], render, emptyState = "" }) {
      root.innerHTML = items.length ? render(items) : emptyState;
      controls.hidden = true;
    }
  });

  const initListPage = async () => {
    const languageFilters = document.querySelector("#language-filters");
    const categoryFilters = document.querySelector("#category-filters");
    const subcategoryFilters = document.querySelector("#subcategory-filters");
    const tagFilters = document.querySelector("#tag-filters");
    const summary = document.querySelector("#active-filter-summary");
    const emptyNode = document.querySelector("#article-empty");
    const controlsRoot = document.querySelector("[data-articles-list-controls]");
    const seriesSection = document.querySelector("#series-context-section");
    const seriesCoverNode = document.querySelector("#series-context-cover");
    const seriesKickerNode = document.querySelector("#series-context-kicker");
    const seriesTitleNode = document.querySelector("#series-context-title");
    const seriesMetaNode = document.querySelector("#series-context-meta");
    const seriesTagsNode = document.querySelector("#series-context-tags");
    const seriesActionsNode = document.querySelector("#series-context-actions");
    const searchForm = document.querySelector("#article-search");
    const searchInput = document.querySelector("#article-search-input");
    const searchStatus = document.querySelector("#article-search-status");
    const searchModeButtons = [...document.querySelectorAll("[data-search-mode]")];

    if (
      !languageFilters ||
      !categoryFilters ||
      !subcategoryFilters ||
      !tagFilters ||
      !summary ||
      !emptyNode ||
      !controlsRoot ||
      !seriesKickerNode ||
      !seriesTitleNode ||
      !seriesMetaNode ||
      !seriesTagsNode ||
      !seriesActionsNode ||
      !searchForm ||
      !searchInput ||
      !searchStatus
    ) {
      return;
    }

    const progressiveList = window.ProgressiveList?.createProgressiveList
      ? window.ProgressiveList.createProgressiveList({
          listRoot,
          controlsRoot,
          items: [],
          initialCount: 8,
          stepCount: 8,
          render: () => "",
          emptyState: ""
        })
      : createFallbackProgressiveList(listRoot, controlsRoot);

    let searchIndexPromise = null;
    let renderToken = 0;
    let inputDebounceId = 0;

    const ensureSearchIndex = async () => {
      searchIndexPromise = searchIndexPromise || fetchJson(SEARCH_INDEX_PATH);
      return searchIndexPromise;
    };

    const applySearchUi = (state, copy) => {
      searchInput.value = state.q;
      searchInput.placeholder = copy.searchPlaceholder;
      searchModeButtons.forEach((button) => {
        const mode = button.dataset.searchMode || "title";
        button.classList.toggle("is-active", mode === state.search);
        button.setAttribute("aria-pressed", mode === state.search ? "true" : "false");
        button.textContent = searchModeLabel(copy, mode);
      });
    };

    const showLoadError = (copy) => {
      progressiveList.reset({
        items: [],
        render: () => "",
        emptyState: ""
      });
      listRoot.innerHTML = `<article class="card"><p>${escapeHtml(copy.loadError)}</p></article>`;
      controlsRoot.hidden = true;
      emptyNode.hidden = true;
      summary.textContent = "";
      searchStatus.textContent = "";
      if (seriesSection) {
        seriesSection.hidden = true;
      }
    };

    const handleFilterButtonClick = (button, state, orderings, renderList) => {
      const group = button.dataset.filterGroup || "";
      const value = button.dataset.filterValue || "";
      const action = button.dataset.filterAction || "toggle";

      if (group === "langs") {
        state.langs =
          action === "clear"
            ? [...DEFAULT_LANGS]
            : toggleSelection(state.langs, value, DEFAULT_LANGS, { allowEmpty: false });
        renderList();
        return;
      }

      if (group === "categories") {
        state.categories =
          action === "clear"
            ? []
            : toggleSelection(state.categories, value, orderings.categories);
        renderList();
        return;
      }

      if (group === "subcategories") {
        state.subcategories =
          action === "clear"
            ? []
            : toggleSelection(state.subcategories, value, orderings.subcategories);
        renderList();
        return;
      }

      if (group === "tags") {
        state.tags =
          action === "clear"
            ? []
            : toggleSelection(state.tags, value, orderings.tags);
        renderList();
      }
    };

    try {
      const indexData = await fetchJson(INDEX_PATH);
      const allArticles = Array.isArray(indexData.articles) ? indexData.articles : [];
      const subcategoryMeta = collectSubcategoryMeta(allArticles);
      const allCategoryValues = stableCategoryOrder(allArticles);
      const allSubcategoryValues = [...subcategoryMeta.keys()];
      const allTagValues = collectTagValues(allArticles);
      const params = new URLSearchParams(window.location.search);
      const rawLangs = params.getAll("lang");
      const state = {
        langs: normalizeLangSelection(rawLangs),
        categories: normalizeSelection(params.getAll("category"), allCategoryValues),
        subcategories: normalizeSelection(params.getAll("subcategory"), allSubcategoryValues),
        tags: normalizeSelection(params.getAll("tag"), allTagValues),
        series: params.get("series") || "",
        q: String(params.get("q") || "").trim(),
        search: normalizeSearchMode(params.get("search") || "title")
      };

      if (state.series && !allArticles.some((article) => article.series_id === state.series)) {
        state.series = "";
      }

      const renderList = async () => {
        const currentRun = ++renderToken;
        const uiLang = getUiLanguage(state.langs);
        const copy = COPY[uiLang];

        try {
          setDocumentLanguage(uiLang);
          applySearchUi(state, copy);

          const normalizedQuery = normalizeSearchText(state.q);
          if (normalizedQuery && state.search === "content") {
            searchStatus.textContent = copy.loadingSearch;
            await ensureSearchIndex();
            if (currentRun !== renderToken) {
              return;
            }
          }

          const searchIndex = searchIndexPromise ? await searchIndexPromise : null;
          if (currentRun !== renderToken) {
            return;
          }

          const filteredArticles = allArticles.filter((article) => articleMatchesState(article, state));
          const categoryOptions = buildCategoryOptions(allArticles, state);
          const subcategoryOptions = buildSubcategoryOptions(allArticles, state, uiLang, subcategoryMeta);
          const tagOptions = buildTagOptions(indexData, allArticles, state, uiLang);
          const orderings = {
            categories: categoryOptions.map((option) => option.value),
            subcategories: subcategoryOptions.map((option) => option.value),
            tags: tagOptions.map((option) => option.value)
          };

          const viewMode =
            state.series || (normalizedQuery && state.search !== "series") ? "articles" : "collections";
          const mergeCollections = state.langs.length > 1;

          const matchesArticleSearch = (article) => {
            if (!normalizedQuery) {
              return true;
            }
            if (state.search === "series") {
              return normalizeSearchText(article.series_title || article.title).includes(normalizedQuery);
            }
            if (state.search === "content") {
              const searchEntry = searchIndex?.articles?.[article.lang]?.[article.id];
              return Boolean(searchEntry?.content?.includes(normalizedQuery));
            }
            return normalizeSearchText(article.title).includes(normalizedQuery);
          };

          const collections = buildCollections(uiLang, filteredArticles, mergeCollections);
          const collectionResults =
            normalizedQuery && !state.series && state.search === "series"
              ? collections.filter((collection) => collection.title_search.includes(normalizedQuery))
              : collections;
          const articleResults = state.series
            ? [...filteredArticles.filter(matchesArticleSearch)].sort(compareSeriesItems)
            : filteredArticles.filter(matchesArticleSearch);
          const viewItems = viewMode === "collections" ? collectionResults : articleResults;

          const normalizedSearch = serializePageParams({
            langs: state.langs,
            categories: state.categories,
            subcategories: state.subcategories,
            tags: state.tags,
            series: state.series,
            q: state.q,
            search: state.search
          });
          if (normalizedSearch !== window.location.search.replace(/^\?/, "")) {
            const nextUrl = `${window.location.pathname}${normalizedSearch ? `?${normalizedSearch}` : ""}${window.location.hash || ""}`;
            history.replaceState({}, "", nextUrl);
          }

          renderFilterRow(
            languageFilters,
            LANGUAGE_OPTIONS.map((entry) =>
              buildToggleButton({
                label: entry.label,
                group: "langs",
                value: entry.value,
                active: state.langs.includes(entry.value)
              })
            )
          );

          renderFilterRow(
            categoryFilters,
            [
              buildToggleButton({
                label: copy.allCategories,
                group: "categories",
                action: "clear",
                active: state.categories.length === 0
              }),
              ...categoryOptions.map((option) =>
                buildToggleButton({
                  label: categoryLabel(option.value, uiLang),
                  group: "categories",
                  value: option.value,
                  active: state.categories.includes(option.value)
                })
              )
            ]
          );

          renderFilterRow(
            subcategoryFilters,
            [
              buildToggleButton({
                label: copy.allSubcategories,
                group: "subcategories",
                action: "clear",
                active: state.subcategories.length === 0
              }),
              ...subcategoryOptions.map((option) =>
                buildToggleButton({
                  label: option.label,
                  group: "subcategories",
                  value: option.value,
                  active: state.subcategories.includes(option.value)
                })
              )
            ]
          );

          renderFilterRow(
            tagFilters,
            [
              buildToggleButton({
                label: copy.allTags,
                group: "tags",
                action: "clear",
                active: state.tags.length === 0
              }),
              ...tagOptions.map((option) =>
                buildToggleButton({
                  label: option.label,
                  group: "tags",
                  value: option.value,
                  active: state.tags.includes(option.value)
                })
              )
            ]
          );

          if (state.series) {
            const allSeriesArticles = allArticles.filter((article) => article.series_id === state.series);
            const selectedSeriesArticles = allSeriesArticles.filter((article) => state.langs.includes(article.lang));
            let seriesCollection = buildCollections(
              uiLang,
              selectedSeriesArticles,
              state.langs.length > 1
            )[0];
            if (!seriesCollection) {
              seriesCollection = buildCollections(uiLang, allSeriesArticles, true)[0];
            }
            const uniqueSeriesCount = new Set(allSeriesArticles.map((article) => article.id)).size;
            const selectedLanguages = state.langs.map((lang) => languageLabel(lang));
            const contextBadges = [
              ...state.categories.map(
                (category) =>
                  `<span class="tag series-context-pill">${copy.categoryPrefix}: ${escapeHtml(
                    categoryLabel(category, uiLang)
                  )}</span>`
              ),
              ...state.subcategories.map(
                (subcategory) =>
                  `<span class="tag series-context-pill">${copy.subcategoryPrefix}: ${escapeHtml(
                    subcategoryMeta.get(subcategory) || subcategoryLabel(subcategory)
                  )}</span>`
              ),
              ...state.tags.map(
                (tag) =>
                  `<span class="tag series-context-pill">${copy.tagPrefix}: ${escapeHtml(
                    tagLabel(indexData, tag, uiLang)
                  )}</span>`
              )
            ];

            if (seriesSection && seriesCollection) {
              renderSeriesContextCover(seriesCoverNode, seriesCollection, uiLang);
              seriesSection.hidden = false;
              seriesKickerNode.textContent = copy.seriesKicker;
              seriesTitleNode.textContent = seriesCollection.title;
              seriesMetaNode.textContent = copy.seriesMeta(
                uniqueSeriesCount,
                articleResults.length,
                selectedLanguages
              );
              seriesTagsNode.innerHTML = contextBadges.join("");
              seriesTagsNode.hidden = contextBadges.length === 0;
              seriesActionsNode.innerHTML = [
                `<a class="tag filter-chip" href="${buildPageUrl({
                  langs: state.langs
                })}">${escapeHtml(copy.backToHome)}</a>`,
                `<a class="tag filter-chip" href="${buildPageUrl({
                  langs: state.langs,
                  series: state.series
                })}">${escapeHtml(copy.clearExtraFilters)}</a>`
              ].join("");
            }
            summary.textContent = "";
          } else {
            if (seriesSection) {
              seriesSection.hidden = true;
            }
            if (seriesCoverNode) {
              seriesCoverNode.hidden = true;
              seriesCoverNode.innerHTML = "";
            }
            summary.textContent =
              viewMode === "collections"
                ? copy.collectionsSummary(collectionResults.length)
                : copy.articlesSummary(articleResults.length);
          }

          searchStatus.textContent = normalizedQuery
            ? copy.searchStatus(searchModeLabel(copy, state.search), state.q.trim(), viewItems.length, viewMode)
            : "";

          emptyNode.textContent = viewMode === "collections" ? copy.noCollections : copy.noArticles;
          if (viewItems.length === 0) {
            progressiveList.reset({
              items: [],
              render: () => "",
              emptyState: ""
            });
            listRoot.innerHTML = "";
            controlsRoot.hidden = true;
            emptyNode.hidden = false;
            return;
          }

          emptyNode.hidden = true;
          progressiveList.reset({
            items: viewItems,
            initialCount: viewMode === "collections" ? 8 : 10,
            stepCount: viewMode === "collections" ? 8 : 10,
            render:
              viewMode === "collections"
                ? (items) => renderCollectionCards(uiLang, items, state, copy)
                : (items) => renderArticleCards(indexData, uiLang, items, state, copy),
            emptyState: "",
            labels: {
              loadMore: copy.loadMore
            },
            renderProgress: ({ visibleCount, totalCount }) => copy.progressiveStatus(visibleCount, totalCount)
          });

          const nextOrders = {
            categories: orderings.categories,
            subcategories: orderings.subcategories,
            tags: orderings.tags
          };
          languageFilters.onclick = (event) => {
            const button = event.target.closest("button[data-filter-group]");
            if (!button || !languageFilters.contains(button)) {
              return;
            }
            handleFilterButtonClick(button, state, nextOrders, renderList);
          };
          categoryFilters.onclick = (event) => {
            const button = event.target.closest("button[data-filter-group]");
            if (!button || !categoryFilters.contains(button)) {
              return;
            }
            handleFilterButtonClick(button, state, nextOrders, renderList);
          };
          subcategoryFilters.onclick = (event) => {
            const button = event.target.closest("button[data-filter-group]");
            if (!button || !subcategoryFilters.contains(button)) {
              return;
            }
            handleFilterButtonClick(button, state, nextOrders, renderList);
          };
          tagFilters.onclick = (event) => {
            const button = event.target.closest("button[data-filter-group]");
            if (!button || !tagFilters.contains(button)) {
              return;
            }
            handleFilterButtonClick(button, state, nextOrders, renderList);
          };
        } catch (err) {
          showLoadError(copy);
          console.error(err);
        }
      };

      searchForm.addEventListener("submit", (event) => {
        event.preventDefault();
      });

      searchInput.addEventListener("input", () => {
        window.clearTimeout(inputDebounceId);
        inputDebounceId = window.setTimeout(() => {
          state.q = searchInput.value.trim();
          renderList();
        }, 180);
      });

      searchModeButtons.forEach((button) => {
        button.addEventListener("click", () => {
          const mode = normalizeSearchMode(button.dataset.searchMode || "title");
          if (state.search === mode) {
            return;
          }
          state.search = mode;
          renderList();
        });
      });

      await renderList();
    } catch (err) {
      showLoadError(COPY.en);
      console.error(err);
    }
  };

  const initDetailPage = async () => {
    const titleNode = document.querySelector("#article-title");
    const excerptNode = document.querySelector("#article-excerpt");
    const metaNode = document.querySelector("#article-meta");
    const linksNode = document.querySelector("#article-links");
    const endLinksNode = document.querySelector("#article-end-links");
    const bodyNode = document.querySelector("#article-body");
    const tagsNode = document.querySelector("#article-tags");
    const kickerNode = document.querySelector("#article-kicker");

    if (!titleNode || !excerptNode || !metaNode || !linksNode || !endLinksNode || !bodyNode || !tagsNode || !kickerNode) {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const lang = params.get("lang") === "zh" ? "zh" : "en";
    const id = params.get("id") || "";
    const copy = COPY[lang];
    setDocumentLanguage(lang);

    if (!id) {
      titleNode.textContent = copy.notFound;
      excerptNode.textContent = copy.loadError;
      return;
    }

    try {
      const [indexData, article] = await Promise.all([
        fetchJson(INDEX_PATH),
        fetchJson(`data/articles/${lang}/${encodeURIComponent(id)}.json`)
      ]);

      document.title = `${titlePrefix()} | ${article.title}`;
      applyArticleHeadMetadata(article, lang);
      titleNode.textContent = article.title;
      excerptNode.textContent = article.excerpt || "";
      const partText = article.part_number ? ` / ${partLabel(article.part_number, lang)}` : "";
      const seriesText = article.series_title ? ` / ${article.series_title}` : "";
      kickerNode.textContent = `${categoryLabel(article.category, lang)} / ${article.read_time} min read${partText}${seriesText}`;

      const published = formatDate(article.published_at, lang);
      const updated = article.updated_at ? formatDate(article.updated_at, lang) : "";
      metaNode.textContent = updated
        ? `Published ${published} / Updated ${updated}`
        : `Published ${published}`;

      linksNode.innerHTML = buildDetailActionLinks(copy, article, lang).join("");
      endLinksNode.innerHTML = buildDetailActionLinks(copy, article, lang, { includeBackToTop: true }).join("");

      bodyNode.innerHTML = article.body_html || `<p>${escapeHtml(copy.notFound)}</p>`;
      window.SiteAnalytics?.trackArticleView({
        articleId: article.id || id,
        lang
      });
      tagsNode.innerHTML = (article.tags || [])
        .map((tag) => {
          const href = buildPageUrl({
            lang,
            category: article.category,
            subcategory: article.subcategory_id || "",
            tag: [tag],
            series: article.series_id || ""
          });
          return `<a class="tag" href="${href}">${escapeHtml(tagLabel(indexData, tag, lang))}</a>`;
        })
        .join("");
    } catch (err) {
      titleNode.textContent = copy.notFound;
      excerptNode.textContent = copy.loadError;
      metaNode.textContent = "";
      linksNode.innerHTML = "";
      endLinksNode.innerHTML = "";
      bodyNode.innerHTML = "";
      tagsNode.innerHTML = "";
      console.error(err);
    }
  };

  if (listRoot) {
    initListPage();
  }
  if (detailRoot) {
    initDetailPage();
  }
})();
