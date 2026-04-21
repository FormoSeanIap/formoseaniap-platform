(() => {
  const THEME_STORAGE_KEY = "theme-preference";
  const THEME_OPTIONS = new Set(["system", "light", "dark"]);

  const getStoredThemePreference = () => {
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY);
      return THEME_OPTIONS.has(stored) ? stored : "system";
    } catch (error) {
      return "system";
    }
  };

  const applyThemePreference = (preference) => {
    if (preference === "light" || preference === "dark") {
      document.documentElement.dataset.theme = preference;
      return;
    }

    document.documentElement.removeAttribute("data-theme");
  };

  const syncThemeButtons = (preference) => {
    document.querySelectorAll("[data-theme-option]").forEach((button) => {
      const isActive = button.dataset.themeOption === preference;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", String(isActive));
    });
  };

  const setThemePreference = (preference) => {
    const nextPreference = THEME_OPTIONS.has(preference) ? preference : "system";

    applyThemePreference(nextPreference);
    syncThemeButtons(nextPreference);

    try {
      localStorage.setItem(THEME_STORAGE_KEY, nextPreference);
    } catch (error) {
      // Ignore storage failures and keep the session-level theme applied.
    }
  };

  const initialThemePreference = getStoredThemePreference();
  applyThemePreference(initialThemePreference);
  syncThemeButtons(initialThemePreference);

  document.body.classList.add("page-enter");
  requestAnimationFrame(() => {
    document.body.classList.add("page-ready");
  });

  const page = document.body.dataset.page;
  if (page) {
    const active = document.querySelector(`[data-nav='${page}']`);
    if (active) {
      active.classList.add("is-active");
      active.setAttribute("aria-current", "page");
    }
  }

  const revealNodes = document.querySelectorAll("[data-reveal]");
  if ("IntersectionObserver" in window && revealNodes.length > 0) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) {
            return;
          }

          const node = entry.target;
          const delay = Number(node.dataset.delay || 0);
          window.setTimeout(() => {
            node.classList.add("is-visible");
          }, delay);
          observer.unobserve(node);
        });
      },
      { threshold: 0.15 }
    );

    revealNodes.forEach((node) => {
      node.classList.add("reveal");
      observer.observe(node);
    });
  } else {
    revealNodes.forEach((node) => node.classList.add("is-visible"));
  }

  const landingCanvas = document.querySelector("#landing-canvas");
  if (landingCanvas) {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const orbCount = window.innerWidth < 720 ? 14 : 24;

    for (let i = 0; i < orbCount; i += 1) {
      const orb = document.createElement("span");
      const size = 24 + Math.random() * 140;
      const x = Math.random() * 100;
      const y = Math.random() * 100;
      const duration = 8 + Math.random() * 16;
      const delay = Math.random() * 4;

      orb.className = "orb";
      orb.style.width = `${size}px`;
      orb.style.height = `${size}px`;
      orb.style.left = `${x}%`;
      orb.style.top = `${y}%`;
      orb.style.animationDuration = `${duration}s`;
      orb.style.animationDelay = `${delay}s`;
      orb.style.opacity = `${0.12 + Math.random() * 0.42}`;

      landingCanvas.appendChild(orb);
    }

    // Only attach the parallax-on-pointer effect when the OS is not
    // asking for reduced motion. CSS already freezes the orb-drift
    // animation under prefers-reduced-motion; this covers the JS path.
    if (!reducedMotion.matches) {
      window.addEventListener("pointermove", (event) => {
        const rect = landingCanvas.getBoundingClientRect();
        const px = (event.clientX - rect.left) / rect.width - 0.5;
        const py = (event.clientY - rect.top) / rect.height - 0.5;
        landingCanvas.style.transform = `translate(${px * 10}px, ${py * 10}px)`;
      });
    }
  }

  const yearNode = document.querySelector("[data-year]");
  if (yearNode) {
    yearNode.textContent = String(new Date().getFullYear());
  }

  document.querySelectorAll("[data-theme-option]").forEach((button) => {
    button.addEventListener("click", () => {
      setThemePreference(button.dataset.themeOption || "system");
    });
  });

  window.addEventListener("storage", (event) => {
    if (event.key !== THEME_STORAGE_KEY) {
      return;
    }

    const nextPreference = THEME_OPTIONS.has(event.newValue) ? event.newValue : "system";
    applyThemePreference(nextPreference);
    syncThemeButtons(nextPreference);
  });
})();
