(() => {
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

    window.addEventListener("pointermove", (event) => {
      const rect = landingCanvas.getBoundingClientRect();
      const px = (event.clientX - rect.left) / rect.width - 0.5;
      const py = (event.clientY - rect.top) / rect.height - 0.5;
      landingCanvas.style.transform = `translate(${px * 10}px, ${py * 10}px)`;
    });
  }

  const yearNode = document.querySelector("[data-year]");
  if (yearNode) {
    yearNode.textContent = String(new Date().getFullYear());
  }
})();
