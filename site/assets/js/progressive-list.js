(() => {
  const createProgressiveList = ({
    listRoot,
    controlsRoot,
    sentinelRoot,
    items = [],
    initialCount = 8,
    stepCount = 8,
    render,
    emptyState = "",
    labels = {},
    renderProgress
  }) => {
    if (!listRoot || !(controlsRoot || sentinelRoot) || typeof render !== "function") {
      return {
        reset() {},
        destroy() {}
      };
    }

    const controlHost = sentinelRoot || controlsRoot;
    const statusNode = document.createElement("p");
    const sentinel = document.createElement("div");

    statusNode.className = "meta progressive-list-status";
    sentinel.className = "progressive-list-sentinel";
    sentinel.setAttribute("aria-hidden", "true");

    controlHost.innerHTML = "";
    controlHost.append(statusNode, sentinel);
    controlHost.hidden = true;

    let currentItems = Array.isArray(items) ? items : [];
    let currentInitialCount = initialCount;
    let currentStepCount = stepCount;
    let currentRender = render;
    let currentEmptyState = emptyState;
    let currentLabels = labels;
    let currentRenderProgress = renderProgress;
    let visibleCount = 0;
    let observer = null;

    const disconnectObserver = () => {
      if (observer) {
        observer.disconnect();
      }
    };

    const hasObserverSupport = "IntersectionObserver" in window;

    const updateControls = () => {
      const totalCount = currentItems.length;
      const hasMore = visibleCount < totalCount;
      const shouldShowControls = totalCount > currentInitialCount && hasMore;

      if (!hasObserverSupport) {
        controlHost.hidden = true;
        statusNode.hidden = true;
        sentinel.hidden = true;
        disconnectObserver();
        return;
      }

      controlHost.hidden = !shouldShowControls;
      statusNode.hidden = !shouldShowControls;
      sentinel.hidden = !shouldShowControls;

      if (!shouldShowControls) {
        disconnectObserver();
        return;
      }

      const progressText =
        typeof currentRenderProgress === "function"
          ? currentRenderProgress({ visibleCount, totalCount })
          : `Showing ${visibleCount} of ${totalCount}`;
      statusNode.textContent = progressText;

      if (!observer) {
        observer = new IntersectionObserver(
          (entries) => {
            if (!entries.some((entry) => entry.isIntersecting)) {
              return;
            }
            loadMore();
          },
          { rootMargin: "0px 0px 320px 0px", threshold: 0.01 }
        );
      }

      observer.disconnect();
      observer.observe(sentinel);
    };

    const renderCurrent = () => {
      if (!currentItems.length) {
        listRoot.innerHTML = currentEmptyState;
        controlHost.hidden = true;
        disconnectObserver();
        return;
      }

      const slice = currentItems.slice(0, visibleCount);
      listRoot.innerHTML = currentRender(slice, {
        visibleCount,
        totalCount: currentItems.length
      });
      updateControls();
    };

    const loadMore = () => {
      if (visibleCount >= currentItems.length) {
        return;
      }
      visibleCount = Math.min(currentItems.length, visibleCount + currentStepCount);
      renderCurrent();
    };

    const reset = ({
      items: nextItems = currentItems,
      initialCount: nextInitialCount = currentInitialCount,
      stepCount: nextStepCount = currentStepCount,
      render: nextRender = currentRender,
      emptyState: nextEmptyState = currentEmptyState,
      labels: nextLabels = currentLabels,
      renderProgress: nextRenderProgress = currentRenderProgress
    } = {}) => {
      currentItems = Array.isArray(nextItems) ? nextItems : [];
      currentInitialCount = nextInitialCount;
      currentStepCount = nextStepCount;
      currentRender = nextRender;
      currentEmptyState = nextEmptyState;
      currentLabels = nextLabels;
      currentRenderProgress = nextRenderProgress;
      visibleCount = hasObserverSupport ? Math.min(currentItems.length, currentInitialCount) : currentItems.length;
      renderCurrent();
    };

    const destroy = () => {
      disconnectObserver();
      listRoot.innerHTML = "";
      controlHost.innerHTML = "";
      controlHost.hidden = true;
    };

    reset({
      items: currentItems,
      initialCount: currentInitialCount,
      stepCount: currentStepCount,
      render: currentRender,
      emptyState: currentEmptyState,
      labels: currentLabels,
      renderProgress: currentRenderProgress
    });

    return { reset, destroy };
  };

  window.ProgressiveList = {
    createProgressiveList
  };
})();
