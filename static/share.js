// Share buttons: native share sheet where available, otherwise copy the link.
document.querySelectorAll(".share").forEach((box) => {
  const url = box.dataset.shareUrl;
  const title = box.dataset.shareTitle;
  const native = box.querySelectorAll("[data-share-native]");
  if (native.length && navigator.share) {
    native.forEach((n) => (n.hidden = false));
    native[native.length - 1].addEventListener("click", () => navigator.share({ title, url }).catch(() => {}));
  }
  const copy = box.querySelector("[data-share-copy]");
  if (copy) {
    copy.addEventListener("click", async () => {
      const label = copy.textContent;
      try {
        await navigator.clipboard.writeText(url);
        copy.textContent = "Copied";
      } catch {
        window.prompt("Copy this link:", url);
      }
      setTimeout(() => (copy.textContent = label), 1800);
    });
  }
});
