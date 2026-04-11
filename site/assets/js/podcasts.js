(() => {
  const homeRoot = document.querySelector("[data-podcast-home-latest]");
  const featureRoot = document.querySelector("[data-podcast-feature]");
  const showsRoot = document.querySelector("[data-podcast-shows]");

  if (!homeRoot && !featureRoot && !showsRoot) {
    return;
  }

  const CONFIG_PATH = "data/podcasts.shows.json";
  const LOCAL_PROXY_URL = "http://127.0.0.1:8787/podcast-feed";
  const MAX_SHOW_EPISODES = 5;
  const LIST_EXCERPT_LENGTH = 180;

  const PLATFORM_LABELS = [
    ["soundon", "SoundOn"],
    ["spotify", "Spotify"],
    ["apple", "Apple Podcasts"],
    ["kkbox", "KKBOX"]
  ];

  const PLATFORM_ICONS = {
    soundon: `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.7"></circle>
        <path d="M10 8.7 16 12l-6 3.3Z" fill="currentColor"></path>
      </svg>
    `,
    spotify: `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.7"></circle>
        <path d="M7.6 10.2c2.8-1 6-0.7 8.9.8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"></path>
        <path d="M8.4 13.1c2.2-.7 4.7-.5 6.7.7" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M9.3 15.8c1.5-.4 3.2-.2 4.5.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"></path>
      </svg>
    `,
    apple: `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="1.6" fill="currentColor"></circle>
        <circle cx="12" cy="12" r="4.3" fill="none" stroke="currentColor" stroke-width="1.5"></circle>
        <circle cx="12" cy="12" r="7.4" fill="none" stroke="currentColor" stroke-width="1.5"></circle>
      </svg>
    `,
    kkbox: `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="8.8" fill="none" stroke="currentColor" stroke-width="1.7"></circle>
        <circle cx="12" cy="12" r="4.7" fill="none" stroke="currentColor" stroke-width="1.5"></circle>
        <path d="M11 9.4 15 12l-4 2.6Z" fill="currentColor"></path>
      </svg>
    `
  };

  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const collapseWhitespace = (value) =>
    String(value ?? "")
      .replace(/\s+/g, " ")
      .trim();

  const findDirectChildContent = (node, localNames) => {
    const child = findDirectChild(node, localNames);
    if (!child) {
      return "";
    }
    return String(child.textContent || "");
  };

  const findDescendantContent = (node, localNames) => {
    const wanted = localNames.map((name) => name.toLowerCase());
    const match = findDescendant(node, (child) => wanted.includes(getLocalName(child)));
    if (!match) {
      return "";
    }
    return String(match.textContent || "");
  };

  const unwrapCdata = (value) =>
    String(value ?? "")
      .replace(/^<!\[CDATA\[/i, "")
      .replace(/\]\]>$/i, "")
      .trim();

  const stripSoundOnFooter = (value) =>
    String(value ?? "")
      .replace(/\s*--\s*Hosting provided by SoundOn\s*$/i, "")
      .trim();

  const formatFeedDescription = (value) => {
    const source = unwrapCdata(value);
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<body>${source}</body>`, "text/html");

    doc.body.querySelectorAll("br").forEach((node) => node.replaceWith("\n"));
    doc.body.querySelectorAll("p, div, section, article, blockquote").forEach((node) => {
      node.prepend("\n\n");
      node.append("\n\n");
    });
    doc.body.querySelectorAll("li").forEach((node) => {
      node.prepend("• ");
      node.append("\n");
    });

    const withBreaks = String(doc.body.textContent || "")
      .replace(/\r\n?/g, "\n")
      .replace(/[ \t]+(?=✉)/g, "\n\n")
      .replace(/[ \t]+(?=☕)/g, "\n")
      .replace(/[ \t]+(?=🎧)/g, "\n");

    return stripSoundOnFooter(
      withBreaks
        .split("\n")
        .map((line) => collapseWhitespace(line))
        .join("\n")
        .replace(/\n{3,}/g, "\n\n")
        .trim()
    );
  };

  const truncateText = (value, maxLength) => {
    const normalized = collapseWhitespace(value);
    if (!normalized || normalized.length <= maxLength) {
      return normalized;
    }
    return `${normalized.slice(0, maxLength - 1).trimEnd()}…`;
  };

  const formatDate = (value) => {
    if (!value) {
      return "";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "";
    }

    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric"
    }).format(date);
  };

  const getLocalName = (element) =>
    String(element?.localName || element?.nodeName || "")
      .split(":")
      .pop()
      .toLowerCase();

  const directChildren = (node) => Array.from(node?.children || []);

  const findDirectChild = (node, localNames) => {
    const wanted = localNames.map((name) => name.toLowerCase());
    return directChildren(node).find((child) => wanted.includes(getLocalName(child))) || null;
  };

  const findDirectChildText = (node, localNames) => {
    const child = findDirectChild(node, localNames);
    return collapseWhitespace(child?.textContent || "");
  };

  const findDescendant = (node, predicate) =>
    Array.from(node?.getElementsByTagName("*") || []).find((child) => predicate(child)) || null;

  const findDescendantText = (node, localNames) => {
    const wanted = localNames.map((name) => name.toLowerCase());
    const match = findDescendant(node, (child) => wanted.includes(getLocalName(child)));
    return collapseWhitespace(match?.textContent || "");
  };

  const fetchJson = async (path) => {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`Failed to load ${path}: HTTP ${res.status}`);
    }
    return res.json();
  };

  const fetchText = async (url) => {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`Failed to load ${url}: HTTP ${res.status}`);
    }
    return res.text();
  };

  const resolveProxyUrl = (config) => {
    const configured = collapseWhitespace(config?.proxy_url || "");
    if (configured) {
      return configured;
    }

    if (["127.0.0.1", "localhost"].includes(window.location.hostname)) {
      return LOCAL_PROXY_URL;
    }

    return "";
  };

  const buildFeedRequestUrl = (show, proxyUrl) => {
    if (!proxyUrl) {
      return show.feed_proxy_path || show.feed_url;
    }

    const url = new URL(proxyUrl);
    url.searchParams.set("show_id", show.id);
    return url.toString();
  };

  const parseXml = (xmlText) => {
    const parser = new DOMParser();
    const xml = parser.parseFromString(xmlText, "text/xml");
    if (xml.getElementsByTagName("parsererror").length > 0) {
      throw new Error("Podcast feed returned invalid XML.");
    }
    return xml;
  };

  const renderArtwork = ({ imageUrl, eyebrow, title, subline, variant }) => {
    const safeEyebrow = escapeHtml(eyebrow || "Podcast");
    const safeTitle = escapeHtml(title || "Podcast");
    const safeSubline = escapeHtml(subline || "");

    if (imageUrl) {
      return `
        <div class="podcast-media podcast-media--${escapeHtml(variant || "feature")}">
          <img src="${escapeHtml(imageUrl)}" alt="${safeTitle}" loading="lazy" />
        </div>
      `;
    }

    return `
      <div class="podcast-media podcast-media--${escapeHtml(variant || "feature")}">
        <div class="podcast-media__fallback">
          <span class="podcast-media__eyebrow">${safeEyebrow}</span>
          <strong class="podcast-media__title">${safeTitle}</strong>
          <span class="podcast-media__subline">${safeSubline}</span>
        </div>
      </div>
    `;
  };

  const renderAudioPlayer = (audioUrl, title) => {
    if (!audioUrl) {
      return "";
    }

    return `
      <audio
        class="podcast-audio"
        controls
        preload="none"
        src="${escapeHtml(audioUrl)}"
        aria-label="Play ${escapeHtml(title || "podcast episode")}"
      ></audio>
    `;
  };

  const renderPlatformAction = ({ platformKey, href, label }) => {
    const safeHref = collapseWhitespace(href || "");
    if (!safeHref) {
      return "";
    }

    const icon = PLATFORM_ICONS[platformKey] || "";
    const safeLabel = escapeHtml(label || platformKey);

    return `
      <a
        class="button-link podcast-platform-link podcast-platform-link--icon-only podcast-platform-link--${escapeHtml(platformKey)}"
        href="${escapeHtml(safeHref)}"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="${safeLabel}"
        title="${safeLabel}"
        data-tooltip="${safeLabel}"
      >
        <span class="podcast-platform-link__icon">${icon}</span>
        <span class="visually-hidden">${safeLabel}</span>
      </a>
    `;
  };

  const renderPlatformLinks = (show) => {
    const links = show?.links || {};
    return PLATFORM_LABELS.map(([key, label]) => {
      const href = collapseWhitespace(links[key] || "");
      if (!href) {
        return "";
      }
      return renderPlatformAction({
        platformKey: key,
        href,
        label: `Open ${show?.title || "podcast"} on ${label}`
      });
    })
      .filter(Boolean)
      .join("");
  };

  const renderEpisodeActions = (episode, extraActions = []) => {
    const actions = [];
    if (episode?.episodeUrl) {
      actions.push(
        renderPlatformAction({
          platformKey: "soundon",
          href: episode.episodeUrl,
          label: `Open ${episode.title || "episode"} on SoundOn`
        })
      );
    }

    const showLinks = episode?.showLinks || {};
    PLATFORM_LABELS.filter(([key]) => key !== "soundon").forEach(([key, label]) => {
      const href = collapseWhitespace(showLinks[key] || "");
      if (!href) {
        return;
      }
      actions.push(
        renderPlatformAction({
          platformKey: key,
          href,
          label: `Open ${episode.showTitle || "show"} on ${label}`
        })
      );
    });

    actions.push(...extraActions);
    return actions.join("");
  };

  const buildEpisodeMeta = (episode) => {
    const parts = [];
    const formattedDate = formatDate(episode?.publishedAt);
    if (formattedDate) {
      parts.push(formattedDate);
    }
    if (episode?.showTitle) {
      parts.push(episode.showTitle);
    }
    if (episode?.duration) {
      parts.push(episode.duration);
    }
    return parts.join(" / ");
  };

  const extractChannelImage = (channel) => {
    const itunesImage = findDirectChild(channel, ["image"]);
    if (itunesImage?.getAttribute("href")) {
      return collapseWhitespace(itunesImage.getAttribute("href"));
    }

    const imageNode = directChildren(channel).find(
      (child) => getLocalName(child) === "image" && !child.getAttribute("href")
    );
    if (!imageNode) {
      return "";
    }

    return findDirectChildText(imageNode, ["url"]);
  };

  const extractEpisodeImage = (item, channelImage) => {
    const itunesImage = findDescendant(
      item,
      (child) => getLocalName(child) === "image" && child.getAttribute("href")
    );
    if (itunesImage?.getAttribute("href")) {
      return collapseWhitespace(itunesImage.getAttribute("href"));
    }
    return channelImage;
  };

  const extractAudioUrl = (item) => {
    const enclosures = directChildren(item).filter((child) => getLocalName(child) === "enclosure");
    const preferred =
      enclosures.find((child) => String(child.getAttribute("type") || "").startsWith("audio/")) ||
      enclosures.find((child) => child.getAttribute("url"));
    return collapseWhitespace(preferred?.getAttribute("url") || "");
  };

  const renderFormattedCopy = (value, fallback = "") => {
    const source = String(value ?? "").trim() || String(fallback ?? "").trim();
    if (!source) {
      return "";
    }

    const paragraphs = source
      .split(/\n{2,}/)
      .map((paragraph) =>
        paragraph
          .split("\n")
          .map((line) => collapseWhitespace(line))
          .filter(Boolean)
      )
      .filter((lines) => lines.length > 0);

    if (!paragraphs.length) {
      return `<div class="podcast-copy"><p>${escapeHtml(source)}</p></div>`;
    }

    return `
      <div class="podcast-copy">
        ${paragraphs
          .map((lines) => `<p>${lines.map((line) => escapeHtml(line)).join("<br />")}</p>`)
          .join("")}
      </div>
    `;
  };

  const normalizeEpisode = (item, show, channelImage) => {
    const publishedRaw = findDirectChildText(item, ["pubDate"]);
    const publishedDate = publishedRaw ? new Date(publishedRaw) : null;
    const publishedAt =
      publishedDate && !Number.isNaN(publishedDate.getTime()) ? publishedDate.toISOString() : "";
    const excerptSource =
      findDescendantContent(item, ["encoded"]) ||
      findDirectChildContent(item, ["summary"]) ||
      findDirectChildContent(item, ["description"]) ||
      findDirectChildContent(item, ["subtitle"]);

    const title = findDirectChildText(item, ["title"]) || "Untitled episode";
    const audioUrl = extractAudioUrl(item);
    const episodeUrl = findDirectChildText(item, ["link"]) || audioUrl || "";
    const imageUrl = extractEpisodeImage(item, channelImage) || collapseWhitespace(show.cover_image || "");

    return {
      id: `${show.id}::${publishedAt || title}::${episodeUrl || audioUrl || "episode"}`,
      showId: show.id,
      showTitle: show.title,
      showLinks: show.links || {},
      title,
      publishedAt,
      publishedAtMs: publishedAt ? Date.parse(publishedAt) : 0,
      excerpt: formatFeedDescription(excerptSource),
      audioUrl,
      episodeUrl,
      imageUrl,
      duration: findDirectChildText(item, ["duration"])
    };
  };

  const parseShowFeed = (xmlText, show) => {
    const xml = parseXml(xmlText);
    const channel = xml.getElementsByTagName("channel")[0];
    if (!channel) {
      throw new Error("Podcast feed does not contain an RSS channel.");
    }

    const channelImage = collapseWhitespace(show.cover_image || "") || extractChannelImage(channel);
    const episodes = Array.from(channel.getElementsByTagName("item"))
      .map((item) => normalizeEpisode(item, show, channelImage))
      .filter((episode) => Boolean(episode.title))
      .sort((a, b) => b.publishedAtMs - a.publishedAtMs);

    return {
      show,
      coverImage: channelImage,
      episodes,
      error: null
    };
  };

  const loadShowEpisodes = async (show, proxyUrl) => {
    const upstreamFeedUrl = collapseWhitespace(show.feed_url || "");
    const siteFeedPath = collapseWhitespace(show.feed_proxy_path || "");
    const requestFeedUrl = proxyUrl ? upstreamFeedUrl : siteFeedPath || upstreamFeedUrl;
    if (!requestFeedUrl) {
      return {
        show,
        coverImage: collapseWhitespace(show.cover_image || ""),
        episodes: [],
        error: "Feed URL is not configured."
      };
    }

    try {
      const requestUrl = buildFeedRequestUrl(show, proxyUrl);
      const xmlText = await fetchText(requestUrl);
      return parseShowFeed(xmlText, show);
    } catch (err) {
      const fallbackError =
        proxyUrl
          ? "The podcast proxy could not read this feed right now."
          : siteFeedPath
            ? "The podcast feed route could not read this feed right now."
            : "Direct browser feed loading failed. This usually means the upstream feed is blocked by CORS and needs the podcast proxy.";
      return {
        show,
        coverImage: collapseWhitespace(show.cover_image || ""),
        episodes: [],
        error: err instanceof Error ? `${fallbackError} ${err.message}` : fallbackError
      };
    }
  };

  const sortShows = (shows) =>
    [...shows].sort((a, b) => {
      const aOrder = Number.isFinite(Number(a.order)) ? Number(a.order) : Number.MAX_SAFE_INTEGER;
      const bOrder = Number.isFinite(Number(b.order)) ? Number(b.order) : Number.MAX_SAFE_INTEGER;
      if (aOrder !== bOrder) {
        return aOrder - bOrder;
      }
      return String(a.title || "").localeCompare(String(b.title || ""));
    });

  const renderHomeFallback = (message) => {
    if (!homeRoot) {
      return;
    }

    homeRoot.innerHTML = `
      <p class="kicker">Podcasts</p>
      <h3>Podcast updates will appear here soon.</h3>
      <p class="podcast-fallback-copy">${escapeHtml(message)}</p>
      <div class="podcast-action-row">
        <a class="button-link" href="podcasts.html">Explore podcasts</a>
      </div>
    `;
  };

  const renderHomeEpisode = (episode) => {
    if (!homeRoot) {
      return;
    }

    homeRoot.innerHTML = `
      ${renderArtwork({
        imageUrl: episode.imageUrl,
        eyebrow: episode.showTitle,
        title: episode.title,
        subline: buildEpisodeMeta(episode),
        variant: "home"
      })}
      <div class="podcast-content">
        <p class="kicker">Latest Episode</p>
        <h3>${escapeHtml(episode.title)}</h3>
        <p class="meta">${escapeHtml(buildEpisodeMeta(episode))}</p>
        <p>${escapeHtml(truncateText(episode.excerpt, LIST_EXCERPT_LENGTH) || "Latest episode metadata loaded from the configured live feed.")}</p>
        ${renderAudioPlayer(episode.audioUrl, episode.title)}
        <div class="podcast-action-row">
          ${renderEpisodeActions(episode, ['<a class="button-link" href="podcasts.html">View all podcasts</a>'])}
        </div>
      </div>
    `;
  };

  const renderFeatureFallback = (message) => {
    if (!featureRoot) {
      return;
    }

    featureRoot.innerHTML = `
      <p class="kicker">Latest</p>
      <h3>No live episode available right now.</h3>
      <p class="podcast-fallback-copy">${escapeHtml(message)}</p>
      <div class="podcast-action-row">
        <a class="button-link" href="index.html">Back to home</a>
      </div>
    `;
  };

  const renderFeaturedEpisode = (episode) => {
    if (!featureRoot) {
      return;
    }

    featureRoot.innerHTML = `
      ${renderArtwork({
        imageUrl: episode.imageUrl,
        eyebrow: episode.showTitle,
        title: episode.title,
        subline: buildEpisodeMeta(episode),
        variant: "feature"
      })}
      <div class="podcast-content">
        <p class="kicker">Featured Latest Episode</p>
        <h3>${escapeHtml(episode.title)}</h3>
        <p class="meta">${escapeHtml(buildEpisodeMeta(episode))}</p>
        ${renderFormattedCopy(episode.excerpt, "This latest episode was loaded from the configured live podcast feed.")}
        ${renderAudioPlayer(episode.audioUrl, episode.title)}
        <div class="podcast-action-row">
          ${renderEpisodeActions(episode)}
        </div>
      </div>
    `;
  };

  const renderShowResults = (
    showResults,
    emptyMessage = "Once podcast feeds are configured, this page will group episodes here by show.",
    emptyTitle = "No podcast feeds configured yet."
  ) => {
    if (!showsRoot) {
      return;
    }

    if (!showResults.length) {
      showsRoot.innerHTML = `
        <article class="card podcast-empty-card">
          <p class="kicker">Podcasts</p>
          <h3>${escapeHtml(emptyTitle)}</h3>
          <p>${escapeHtml(emptyMessage)}</p>
        </article>
      `;
      return;
    }

    showsRoot.innerHTML = showResults
      .map((result) => {
        const recentEpisodes = result.episodes.slice(0, MAX_SHOW_EPISODES);

        const statusLine = result.error
          ? `<p class="meta podcast-status">Episodes unavailable right now.</p>`
          : recentEpisodes.length
            ? `<p class="meta podcast-status">Showing the latest ${recentEpisodes.length} episode(s) from this feed.</p>`
            : `<p class="meta podcast-status">No episodes were found in this feed.</p>`;

        const recentList = recentEpisodes.length
          ? `
            <div class="podcast-episode-list">
              ${recentEpisodes
                .map((episode) => {
                  return `
                    <article class="podcast-episode-item">
                      <p class="meta">${escapeHtml(buildEpisodeMeta(episode))}</p>
                      <h3>${escapeHtml(episode.title)}</h3>
                      ${renderFormattedCopy(episode.excerpt, "Episode metadata loaded from the live RSS feed.")}
                      ${renderAudioPlayer(episode.audioUrl, episode.title)}
                      <div class="podcast-action-row">
                        ${renderEpisodeActions(episode)}
                      </div>
                    </article>
                  `;
                })
                .join("")}
            </div>
          `
          : `<p>${escapeHtml(result.error || "Episodes will appear here when this feed exposes recent items.")}</p>`;

        return `
          <section class="card podcast-show-card">
            <div class="podcast-show-topline">
              <div class="podcast-show-media">
                ${renderArtwork({
                  imageUrl: result.coverImage || result.show.cover_image,
                  eyebrow: "Podcast Show",
                  title: result.show.title,
                  subline: result.show.description || "Configured podcast feed",
                  variant: "show"
                })}
                <div class="podcast-platform-links podcast-platform-links--cover">
                  ${renderPlatformLinks(result.show)}
                </div>
              </div>
              <div class="podcast-show-header">
                <div class="podcast-content">
                  <p class="kicker">Show</p>
                  <h3>${escapeHtml(result.show.title)}</h3>
                  <p>${escapeHtml(result.show.description || "Configured podcast feed and platform destinations.")}</p>
                  ${statusLine}
                </div>
              </div>
            </div>
            ${recentList}
          </section>
        `;
      })
      .join("");
  };

  const normalizeConfig = (config) => {
    const shows = Array.isArray(config?.shows) ? config.shows : [];
    return sortShows(
      shows.map((show) => ({
        id: collapseWhitespace(show.id || show.title || "podcast-show"),
        title: collapseWhitespace(show.title || show.id || "Podcast Show"),
        feed_url: collapseWhitespace(show.feed_url || ""),
        feed_proxy_path: collapseWhitespace(show.feed_proxy_path || ""),
        description: collapseWhitespace(show.description || ""),
        cover_image: collapseWhitespace(show.cover_image || ""),
        order: show.order,
        links: {
          soundon: collapseWhitespace(show?.links?.soundon || ""),
          spotify: collapseWhitespace(show?.links?.spotify || ""),
          apple: collapseWhitespace(show?.links?.apple || ""),
          kkbox: collapseWhitespace(show?.links?.kkbox || "")
        }
      }))
    );
  };

  const initPodcasts = async () => {
    try {
      const config = await fetchJson(CONFIG_PATH);
      const shows = normalizeConfig(config);
      const proxyUrl = resolveProxyUrl(config);

      if (!shows.length) {
        renderHomeFallback("Podcast feeds are not connected on this site yet. Once they are configured, refreshing the page will surface the newest published episode here.");
        renderFeatureFallback("Once at least one podcast feed is connected, the latest episode across all shows will appear here.");
      renderShowResults([]);
        return;
      }

      const showResults = await Promise.all(shows.map((show) => loadShowEpisodes(show, proxyUrl)));
      const allEpisodes = showResults
        .flatMap((result) => result.episodes)
        .sort((a, b) => b.publishedAtMs - a.publishedAtMs);

      const featuredEpisode = allEpisodes[0] || null;

      if (featuredEpisode) {
        renderHomeEpisode(featuredEpisode);
        renderFeaturedEpisode(featuredEpisode);
      } else {
        const failureMessage = showResults.some((result) => result.error)
          ? "The configured feeds could not be read in this browser session. Platform links remain available below."
          : "The configured feeds did not expose any episodes yet.";
        renderHomeFallback(failureMessage);
        renderFeatureFallback(failureMessage);
      }

      renderShowResults(showResults);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Unable to load the local podcast configuration right now.";
      renderHomeFallback(message);
      renderFeatureFallback(message);
      renderShowResults(
        [],
        "The podcast configuration could not be loaded, so show sections are unavailable right now.",
        "Podcast sections are unavailable right now."
      );
      console.error(err);
    }
  };

  initPodcasts();
})();
