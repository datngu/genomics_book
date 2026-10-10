// Share buttons: native share sheet where available, otherwise copy the link.
document.querySelectorAll(".share").forEach((box) => {
  const url = box.dataset.shareUrl;
  const title = box.dataset.shareTitle;
  const native = box.querySelector("[data-share-native]");
  if (native && navigator.share) {
    native.hidden = false;
    native.addEventListener("click", () => navigator.share({ title, url }).catch(() => {}));
  }
  const copy = box.querySelector("[data-share-copy]");
  if (copy) {
    copy.addEventListener("click", async () => {
      const label = copy.textContent;
      try {
        await navigator.clipboard.writeText(url);
        copy.textContent = "Đã sao chép";
      } catch {
        window.prompt("Sao chép liên kết:", url);
      }
      setTimeout(() => (copy.textContent = label), 1800);
    });
  }
});
