(() => {
  const body = document.body;
  if (!body) return;

  const modal = document.createElement("div");
  modal.className = "lightbox";
  modal.setAttribute("hidden", "");
  modal.innerHTML = `
    <button class="lightbox__close" type="button" aria-label="Закрыть">×</button>
    <img class="lightbox__image" alt="" />
  `;
  body.appendChild(modal);

  const modalImage = modal.querySelector(".lightbox__image");
  const closeButton = modal.querySelector(".lightbox__close");

  const openLightbox = (src, alt) => {
    if (!src || !modalImage) return;
    modalImage.src = src;
    modalImage.alt = alt || "";
    modal.removeAttribute("hidden");
    body.classList.add("modal-open");
  };

  const closeLightbox = () => {
    modal.setAttribute("hidden", "");
    body.classList.remove("modal-open");
    if (modalImage) {
      modalImage.src = "";
      modalImage.alt = "";
    }
  };

  closeButton?.addEventListener("click", closeLightbox);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeLightbox();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hasAttribute("hidden")) closeLightbox();
  });

  document.querySelectorAll(".media-grid img").forEach((img) => {
    const isPreview = img.classList.contains("local-video-preview");
    if (isPreview) {
      img.addEventListener("click", () => {
        const block = img.closest(".video-embed");
        const link = block?.querySelector(".video-link");
        if (link?.href) window.open(link.href, "_blank", "noopener,noreferrer");
      });
      return;
    }

    img.classList.add("media-grid__zoomable");
    img.addEventListener("click", () => openLightbox(img.currentSrc || img.src, img.alt));
  });

  document.querySelectorAll(".local-video").forEach((video) => {
    video.addEventListener("click", () => {
      if (video.paused) video.play();
      else video.pause();
    });
  });
})();
