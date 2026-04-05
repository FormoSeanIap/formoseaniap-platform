(() => {
  const listRoot = document.querySelector("[data-projects-list]");
  const controlsRoot = document.querySelector("[data-projects-list-controls]");
  if (!listRoot || !controlsRoot || !window.ProgressiveList?.createProgressiveList) {
    return;
  }

  const DATA_PATH = "data/projects.json";

  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const fetchJson = async (path) => {
    const res = await fetch(path, { cache: "no-cache" });
    if (!res.ok) {
      throw new Error(`Failed to load ${path}: HTTP ${res.status}`);
    }
    return res.json();
  };

  const renderProjectCards = (items) =>
    items
      .map((project) => {
        const tags = (project.tags || [])
          .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
          .join("");
        const href = escapeHtml(project.link_href || "#");
        const linkAttrs = project.link_external
          ? `href="${href}" target="_blank" rel="noopener noreferrer"`
          : `href="${href}"`;

        return `
          <article class="card">
            <p class="meta">${escapeHtml(project.meta || "")}</p>
            <h3>${escapeHtml(project.title || "")}</h3>
            <p>${escapeHtml(project.excerpt || "")}</p>
            <p><strong>Role:</strong> ${escapeHtml(project.role || "")}</p>
            <div class="tag-list">${tags}</div>
            <a class="button-link" ${linkAttrs}>${escapeHtml(project.link_label || "Read overview")}</a>
          </article>
        `;
      })
      .join("");

  const progressiveList = window.ProgressiveList.createProgressiveList({
    listRoot,
    controlsRoot,
    items: [],
    initialCount: 4,
    stepCount: 4,
    render: renderProjectCards,
    emptyState: '<article class="card"><p>No projects available yet.</p></article>',
    labels: {
      loadMore: "Load more projects"
    },
    renderProgress: ({ visibleCount, totalCount }) => `Showing ${visibleCount} of ${totalCount} projects`
  });

  const initProjectsPage = async () => {
    try {
      const data = await fetchJson(DATA_PATH);
      progressiveList.reset({
        items: data.projects || [],
        initialCount: 4,
        stepCount: 4,
        render: renderProjectCards,
        emptyState: '<article class="card"><p>No projects available yet.</p></article>',
        labels: {
          loadMore: "Load more projects"
        },
        renderProgress: ({ visibleCount, totalCount }) => `Showing ${visibleCount} of ${totalCount} projects`
      });
    } catch (err) {
      listRoot.innerHTML = '<article class="card"><p>Failed to load project data.</p></article>';
      controlsRoot.hidden = true;
      console.error(err);
    }
  };

  initProjectsPage();
})();
