(async function () {
  const statusEl = document.getElementById("status");
  const agree = document.getElementById("agree");
  const enterBtn = document.getElementById("enterBtn");

  function setStatus(msg) {
    if (statusEl) statusEl.textContent = msg;
  }

  function updateButton() {
    if (!enterBtn || !agree) return;
    enterBtn.disabled = !agree.checked;
  }

  if (agree) agree.addEventListener("change", updateButton);
  if (enterBtn) enterBtn.addEventListener("click", () => {
    // your “enable audio” logic would go here
    setStatus("Entered. Audio can be enabled here.");
  });

  updateButton();

  // This is the endpoint from your screenshot:
  const url = "/api/freestyle/channel/main/now.json";

  try {
    const res = await fetch(url, { cache: "no-store" });

    if (!res.ok) {
      // Silent failure: no popup.
      console.warn("Now endpoint returned:", res.status, url);
      setStatus("Live TV endpoint unavailable (no popup).");
      return;
    }

    const data = await res.json();
    if (data?.ok) {
      setStatus(`Live TV: ${data.channel} is ready.`);
    } else {
      setStatus("Live TV response received (unexpected shape).");
      console.warn("Unexpected payload:", data);
    }
  } catch (err) {
    console.warn("Now endpoint fetch failed:", err);
    setStatus("Live TV fetch failed (no popup).");
  }
})();
