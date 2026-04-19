(() => {
  const listRoot = document.querySelector("[data-projects-list]");
  const controlsRoot = document.querySelector("[data-projects-list-controls]");
  if (!listRoot || !controlsRoot || !window.ProgressiveList?.createProgressiveList) {
    return;
  }

  const DATA_PATH = "data/projects.json";
  const PROJECT_STATUS_CLASS = {
    current: "project-status--current",
    public: "project-status--public",
    private: "project-status--private"
  };

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

  const getProjectLinks = (project) => {
    if (Array.isArray(project.links) && project.links.length > 0) {
      return project.links;
    }

    if (project.link_href) {
      return [
        {
          href: project.link_href,
          label: project.link_label,
          external: project.link_external
        }
      ];
    }

    return [];
  };

  const renderProjectLinks = (links) =>
    links
      .map((link) => {
        const href = escapeHtml(link.href || "#");
        const label = escapeHtml(link.label || "Open project");
        const linkAttrs = link.external
          ? `href="${href}" target="_blank" rel="noopener noreferrer"`
          : `href="${href}"`;

        return `<a class="button-link" ${linkAttrs}>${label}</a>`;
      })
      .join("");

  const renderProjectCards = (items) =>
    items
      .map((project) => {
        const tags = (project.tags || [])
          .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
          .join("");
        const highlights = (project.highlights || [])
          .map((highlight) => `<li>${escapeHtml(highlight)}</li>`)
          .join("");
        const links = getProjectLinks(project);
        const linkMarkup = renderProjectLinks(links);
        const statusClass = PROJECT_STATUS_CLASS[project.status_tone] || "";
        const cardClass = project.featured ? "card project-card project-card--featured" : "card project-card";

        return `
          <article class="${cardClass}">
            <div class="project-card-head">
              <div class="project-card-meta-row">
                <p class="meta">${escapeHtml(project.meta || "")}</p>
                ${
                  project.status_label
                    ? `<span class="project-status ${statusClass}">${escapeHtml(project.status_label)}</span>`
                    : ""
                }
              </div>
              <div class="project-card-title">
                ${project.kind ? `<p class="kicker">${escapeHtml(project.kind)}</p>` : ""}
                <h3 class="project-card-heading">${escapeHtml(project.title || "")}</h3>
              </div>
            </div>
            <div class="project-card-body">
              <div class="project-card-copy">
                <p class="project-card-summary">${escapeHtml(project.summary || project.excerpt || "")}</p>
                ${project.context ? `<p>${escapeHtml(project.context)}</p>` : ""}
              </div>
              <div class="project-card-facts">
                ${
                  project.role
                    ? `<div class="project-card-fact"><p class="meta">Role</p><p class="project-card-role">${escapeHtml(project.role)}</p></div>`
                    : ""
                }
                ${
                  tags
                    ? `<div class="project-card-fact"><p class="meta">Core stack</p><div class="tag-list">${tags}</div></div>`
                    : ""
                }
              </div>
            </div>
            ${
              highlights
                ? `<div class="project-card-highlights"><p class="meta">Highlights</p><ul class="project-highlight-list">${highlights}</ul></div>`
                : ""
            }
            ${
              linkMarkup || project.availability_note
                ? `<footer class="project-card-footer">${
                    linkMarkup ? `<div class="project-link-row">${linkMarkup}</div>` : ""
                  }${
                    project.availability_note
                      ? `<p class="project-availability">${escapeHtml(project.availability_note)}</p>`
                      : ""
                  }</footer>`
                : ""
            }
          </article>
        `;
      })
      .join("");

  const progressiveList = window.ProgressiveList.createProgressiveList({
    listRoot,
    controlsRoot,
    items: [],
    initialCount: 3,
    stepCount: 3,
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
        initialCount: 3,
        stepCount: 3,
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
