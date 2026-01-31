/* static/freestyle/live.js
   Fixes: "Failed to load Live TV endpoint" showing even when API is fine.
   Root cause is usually autoplay restrictions (NotAllowedError).
*/

(() => {
  // --- Config ---
  const CHANNEL_SLUG = "main";
  const NOW_URL = `/api/freestyle/channel/${encodeURIComponent(CHANNEL_SLUG)}/now.json`;

  // --- Elements (be flexible: grab first video if id differs) ---
  const video =
    document.querySelector("video#liveVideo") ||
    document.querySelector("video#live-video") ||
    document.querySelector("video#tvVideo") ||
    document.querySelector("video");

  if (!video) return;

  // Optional UI controls if your template has them (won't break if missing)
  const muteBtn =
    document.querySelector("#muteBtn") ||
    document.querySelector("[data-mute-btn]");
  const volSlider =
    document.querySelector("#volSlider") ||
    document.querySelector("[data-vol-slider]");
  const fullscreenBtn =
    document.querySelector("#fullscreenBtn") ||
    document.querySelector("[data-fullscreen-btn]");

  // Create a click-to-play overlay (only shows if autoplay is blocked)
  const overlay = document.createElement("div");
  overlay.style.position = "fixed";
  overlay.style.inset = "0";
  overlay.style.display = "none";
  overlay.style.alignItems = "center";
  overlay.style.justifyContent = "center";
  overlay.style.zIndex = "9999";
  overlay.style.background = "rgba(0,0,0,0.55)";
  overlay.style.cursor = "pointer";
  overlay.innerHTML = `
    <div style="
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      color: white;
      font-size: 18px;
      padding: 14px 18px;
      border: 1px solid rgba(255,255,255,0.25);
      border-radius: 12px;
      background: rgba(0,0,0,0.35);
      backdrop-filter: blur(6px);
      text-align: center;
      line-height: 1.35;
      ">
      Click to start Live TV<br/>
      <span style="font-size: 12px; opacity: 0.85;">(browser blocked autoplay)</span>
    </div>
  `;
  document.body.appendChild(overlay);

  function showOverlay() {
    overlay.style.display = "flex";
  }
  function hideOverlay() {
    overlay.style.display = "none";
  }

  // Make autoplay as permissive as possible
  video.autoplay = true;
  video.playsInline = true;
  video.muted = true;          // critical for autoplay
  video.preload = "auto";

  // Hook up optional controls (if present)
  if (muteBtn) {
    muteBtn.addEventListener("click", () => {
      video.muted = !video.muted;
      // If user unmutes, this counts as interaction and allows play
      if (!video.paused) return;
      video.play().catch(() => {});
    });
  }

  if (volSlider) {
    volSlider.addEventListener("input", () => {
      const v = Number(volSlider.value);
      // assume slider 0..1 or 0..100
      video.volume = v > 1 ? Math.max(0, Math.min(1, v / 100)) : Math.max(0, Math.min(1, v));
      if (video.volume > 0) video.muted = false;
    });
  }

  if (fullscreenBtn) {
    fullscreenBtn.addEventListener("click", () => {
      const el = video.closest(".player") || video.parentElement || video;
      if (!document.fullscreenElement) {
        el.requestFullscreen?.().catch(() => {});
      } else {
        document.exitFullscreen?.().catch(() => {});
      }
    });
  }

  // If autoplay is blocked, user click starts playback
  overlay.addEventListener("click", async () => {
    try {
      // once user clicks, we can unmute if you want:
      // video.muted = false;
      await video.play();
      hideOverlay();
    } catch (e) {
      // keep overlay visible
    }
  });

  // Load captions track (if your API returns captions_vtt)
  function setCaptionsTrack(vttUrl) {
    // remove existing tracks
    Array.from(video.querySelectorAll("track")).forEach((t) => t.remove());
    if (!vttUrl) return;

    const track = document.createElement("track");
    track.kind = "subtitles";
    track.label = "Captions";
    track.srclang = "en";
    track.src = vttUrl;
    track.default = true;
    video.appendChild(track);
  }

  async function fetchNow() {
    const res = await fetch(`${NOW_URL}?t=${Date.now()}`, {
      method: "GET",
      cache: "no-store",
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    });

    if (!res.ok) {
      throw new Error(`NOW endpoint HTTP ${res.status}`);
    }

    const data = await res.json();
    if (!data || data.ok !== true) {
      const msg = data?.error || "NOW endpoint returned ok:false";
      throw new Error(msg);
    }
    return data;
  }

  // Load + play video safely
  async function loadAndPlay() {
    try {
      const now = await fetchNow();

      // IMPORTANT: use play_url exactly as API sends it (absolute or relative both fine)
      const src = now.play_url;
      if (!src) throw new Error("NOW endpoint missing play_url");

      setCaptionsTrack(now.captions_vtt);

      // If source changed, reset
      if (video.src !== src) {
        video.src = src;
        video.load();
      }

      // Try autoplay (muted)
      video.muted = true;
      hideOverlay();

      const p = video.play();
      if (p && typeof p.then === "function") {
        await p;
      }

      // success: keep polling occasionally in case the "now" item rotates
      // (lightweight)
    } catch (err) {
      // Two buckets:
      // 1) endpoint truly failing -> log it
      // 2) autoplay blocked -> show overlay
      const msg = String(err?.message || err);

      // Autoplay blocked messages vary, but "NotAllowedError" is the main one.
      if (
        msg.includes("NotAllowedError") ||
        msg.toLowerCase().includes("play() failed") ||
        msg.toLowerCase().includes("user didn't interact")
      ) {
        showOverlay();
      } else {
        // Real error: show ONCE in console, and show overlay so user can still try to play
        console.error("Live TV load failed:", err);
        showOverlay();
      }
    }
  }

  // Start
  loadAndPlay();

  // Refresh “now” every 20s so it can rotate videos without reload
  setInterval(loadAndPlay, 20000);

  // If tab becomes active again, try play
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) loadAndPlay();
  });
})();
