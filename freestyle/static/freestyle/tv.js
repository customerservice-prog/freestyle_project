(() => {
  "use strict";

  // -------------------------
  // Config
  // -------------------------
  const CHANNEL = (document.documentElement.dataset.channel || "main").trim();
  const NOW_URL = `/api/freestyle/channel/${encodeURIComponent(CHANNEL)}/now.json`;
  const PING_URL = `/api/freestyle/presence/ping.json`;

  const POLL_MS = 5000;

  // Drift behavior:
  const HARD_SEEK_DRIFT = 6.0;
  const SOFT_DRIFT = 1.0;
  const SOFT_RATE = 0.05;
  const SOFT_RATE_HOLD_MS = 900;

  const BANNER_MS = 15000;
  const AD_MS = 30000;

  // -------------------------
  // Elements
  // -------------------------
  const video = document.getElementById("tvVideo");

  const banner = document.getElementById("topBanner");
  const bannerTitle = document.getElementById("bannerTitle");

  const adBar = document.getElementById("adBar");
  const adClose = document.getElementById("adClose");

  const viewersPill = document.getElementById("viewersPill");
  const viewersCount = document.getElementById("viewersCount");

  const chatPanel = document.getElementById("chatPanel");
  const chatOpenBtn = document.getElementById("chatOpenBtn");
  const chatCloseBtn = document.getElementById("chatCloseBtn");

  const overlay = document.getElementById("enterOverlay");
  const overlayCheck = document.getElementById("enterAgree");
  const overlayBtn = document.getElementById("enterBtn");

  // Volume UI
  const muteBtn = document.getElementById("muteBtn");
  const volSlider = document.getElementById("volSlider");
  const volPct = document.getElementById("volPct");

  // -------------------------
  // State
  // -------------------------
  let sid = localStorage.getItem("freestyle_sid");
  if (!sid) {
    sid = crypto.randomUUID();
    localStorage.setItem("freestyle_sid", sid);
  }

  let lastPlayUrl = null;
  let lastStartEpoch = 0;

  let lastBannerKey = null;
  let lastAdKey = null;

  let softTimer = null;

  // LIVE clock base
  let baseOffset = 0;
  let basePerfNow = 0;
  let baseSet = false;

  // allow programmatic seeks
  let allowSeekUntilMs = 0;

  // Volume persistence
  const VOL_KEY = "freestyle_volume";
  const MUTE_KEY = "freestyle_muted";

  // -------------------------
  // Helpers
  // -------------------------
  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function show(el) { el?.classList.remove("is-hidden"); }
  function hide(el) { el?.classList.add("is-hidden"); }

  function currentTimeSafe() {
    const t = Number(video.currentTime);
    return Number.isFinite(t) ? t : 0;
  }

  function durationSafe() {
    const d = Number(video.duration);
    return Number.isFinite(d) ? d : 0;
  }

  function setViewers(n) {
    if (!viewersPill || !viewersCount) return;
    viewersCount.textContent = `${n}`;
    show(viewersPill);
  }

  function showBanner(title, key) {
    if (!banner || !bannerTitle) return;
    if (lastBannerKey === key) return;
    lastBannerKey = key;

    bannerTitle.textContent = title || "";
    show(banner);
    banner.classList.remove("fade-out");
    window.setTimeout(() => {
      banner.classList.add("fade-out");
      window.setTimeout(() => hide(banner), 500);
    }, BANNER_MS);
  }

  function showAd(key) {
    if (!adBar) return;
    if (lastAdKey === key) return;
    lastAdKey = key;

    show(adBar);
    adBar.classList.remove("slide-down");
    window.setTimeout(() => {
      adBar.classList.add("slide-down");
      window.setTimeout(() => hide(adBar), 450);
    }, AD_MS);
  }

  function isOverlayAccepted() {
    return sessionStorage.getItem("freestyle_entered") === "1";
  }

  function showOverlayIfNeeded() {
    if (!overlay) return;
    if (isOverlayAccepted()) {
      hide(overlay);
      return;
    }
    show(overlay);
    overlayBtn.disabled = true;
    overlayBtn.classList.add("is-disabled");
  }

  async function safePlay() {
    try { await video.play(); } catch (_) {}
  }

  function allowProgrammaticSeek(ms, fn) {
    allowSeekUntilMs = Date.now() + ms;
    try { fn(); } finally {}
  }

  function desiredLiveTime() {
    if (!baseSet) return 0;
    const elapsed = (performance.now() - basePerfNow) / 1000;
    return Math.max(0, baseOffset + elapsed);
  }

  function setSoftPlaybackRate(rate) {
    clearTimeout(softTimer);
    video.playbackRate = rate;
    softTimer = setTimeout(() => {
      video.playbackRate = 1.0;
    }, SOFT_RATE_HOLD_MS);
  }

  function updateBaseClockFromServer(offsetSeconds) {
    baseOffset = Math.max(0, Number(offsetSeconds) || 0);
    basePerfNow = performance.now();
    baseSet = true;
  }

  // -------------------------
  // VOLUME UI
  // -------------------------
  function setMuteIcon() {
    const muted = video.muted || video.volume === 0;
    if (muteBtn) muteBtn.textContent = muted ? "🔇" : "🔊";
  }

  function applySavedVolume() {
    const savedVol = Number(localStorage.getItem(VOL_KEY));
    const savedMuted = localStorage.getItem(MUTE_KEY) === "1";

    const vol01 = Number.isFinite(savedVol) ? clamp(savedVol, 0, 1) : 1.0;

    if (volSlider) volSlider.value = String(Math.round(vol01 * 100));
    if (volPct) volPct.textContent = `${Math.round(vol01 * 100)}%`;

    // If overlay not accepted, keep muted
    if (!isOverlayAccepted()) {
      video.muted = true;
      video.volume = 0.0;
    } else {
      video.volume = vol01;
      video.muted = savedMuted ? true : false;
    }

    setMuteIcon();
  }

  function initVolumeUI() {
    if (volSlider) {
      volSlider.addEventListener("input", () => {
        const v = clamp(Number(volSlider.value) / 100, 0, 1);
        if (volPct) volPct.textContent = `${Math.round(v * 100)}%`;

        localStorage.setItem(VOL_KEY, String(v));

        // Only apply sound if user accepted overlay
        if (isOverlayAccepted()) {
          video.volume = v;
          if (v > 0) {
            video.muted = false;
            localStorage.setItem(MUTE_KEY, "0");
          }
        }

        setMuteIcon();
      });
    }

    if (muteBtn) {
      muteBtn.addEventListener("click", () => {
        if (!isOverlayAccepted()) return;
        video.muted = !video.muted;
        localStorage.setItem(MUTE_KEY, video.muted ? "1" : "0");
        setMuteIcon();
      });
    }

    video.addEventListener("volumechange", setMuteIcon);

    applySavedVolume();
  }

  // -------------------------
  // Live TV core
  // -------------------------
  async function applyNow(data) {
    if (!data || !data.ok) return;

    setViewers(Number(data.viewers || 1));

    const playUrl = data.play_url || null;
    const title = data.title || "";
    const startEpoch = Number(data.start_epoch || 0);
    const offsetSeconds = Math.max(0, Number(data.offset_seconds || 0));

    updateBaseClockFromServer(offsetSeconds);

    const urlChanged = playUrl && playUrl !== lastPlayUrl;
    const programChanged = startEpoch && startEpoch !== lastStartEpoch;

    if (urlChanged || programChanged) {
      lastPlayUrl = playUrl;
      lastStartEpoch = startEpoch || 0;

      showBanner(title, `${playUrl}|${startEpoch}`);
      showAd(`${playUrl}|${startEpoch}`);

      if (!playUrl) return;

      video.src = playUrl;
      video.load();

      video.onloadedmetadata = () => {
        const target = desiredLiveTime();
        const dur = durationSafe();
        const safeTarget = (dur > 0.5) ? clamp(target, 0, Math.max(0, dur - 0.25)) : target;

        allowProgrammaticSeek(800, () => {
          video.currentTime = safeTarget;
        });

        video.playbackRate = 1.0;
        safePlay();
      };

      return;
    }

    if (video.readyState < 2) {
      safePlay();
      return;
    }

    // Keep running even if overlay blocks audio
    if (!isOverlayAccepted()) {
      video.muted = true;
      video.volume = 0.0;
      setMuteIcon();
    }

    const want = desiredLiveTime();
    const actual = currentTimeSafe();
    const drift = want - actual;

    if (!Number.isFinite(drift)) return;

    if (video.paused) safePlay();

    if (Math.abs(drift) > HARD_SEEK_DRIFT) {
      const dur = durationSafe();
      const safeTarget = (dur > 0.5) ? clamp(want, 0, Math.max(0, dur - 0.25)) : want;

      allowProgrammaticSeek(800, () => {
        video.currentTime = safeTarget;
      });

      video.playbackRate = 1.0;
      safePlay();
      return;
    }

    if (Math.abs(drift) > SOFT_DRIFT) {
      const rate = 1.0 + (drift > 0 ? SOFT_RATE : -SOFT_RATE);
      setSoftPlaybackRate(rate);
    } else {
      video.playbackRate = 1.0;
    }
  }

  // -------------------------
  // Poll + presence ping
  // -------------------------
  async function pollNow() {
    try {
      const res = await fetch(NOW_URL, { cache: "no-store" });
      const data = await res.json();
      await applyNow(data);
    } catch (_) {}
  }

  async function pingPresence() {
    try {
      await fetch(`${PING_URL}?sid=${encodeURIComponent(sid)}&channel=${encodeURIComponent(CHANNEL)}`, {
        cache: "no-store",
      });
    } catch (_) {}
  }

  // -------------------------
  // Lock down controls (LIVE TV)
  // -------------------------
  function lockDownVideo() {
    video.controls = false;

    video.addEventListener("pause", () => {
      safePlay();
    });

    video.addEventListener("seeking", () => {
      if (Date.now() < allowSeekUntilMs) return;

      if (video.readyState >= 2 && baseSet) {
        const want = desiredLiveTime();
        const dur = durationSafe();
        const safeTarget = (dur > 0.5) ? clamp(want, 0, Math.max(0, dur - 0.25)) : want;

        allowProgrammaticSeek(800, () => {
          video.currentTime = safeTarget;
        });
      }
    });

    window.addEventListener("keydown", (e) => {
      const keys = ["ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"];
      if (keys.includes(e.key)) e.preventDefault();
    }, { passive: false });
  }

  // -------------------------
  // Overlay
  // -------------------------
  function initOverlay() {
    if (!overlay || !overlayBtn || !overlayCheck) return;

    overlayBtn.addEventListener("click", (e) => {
      e.preventDefault();
      if (overlayBtn.disabled) return;

      sessionStorage.setItem("freestyle_entered", "1");
      hide(overlay);

      // unlock audio now that user interacted
      video.muted = false;

      // apply saved volume now
      applySavedVolume();
      safePlay();
    });

    overlayCheck.addEventListener("change", () => {
      const ok = overlayCheck.checked;
      overlayBtn.disabled = !ok;
      overlayBtn.classList.toggle("is-disabled", !ok);
    });

    showOverlayIfNeeded();
  }

  // -------------------------
  // Chat open/close
  // -------------------------
  function setChatOpen(open) {
    if (!chatPanel || !chatOpenBtn) return;
    if (open) {
      show(chatPanel);
      hide(chatOpenBtn);
      localStorage.setItem("freestyle_chat_open", "1");
    } else {
      hide(chatPanel);
      show(chatOpenBtn);
      localStorage.setItem("freestyle_chat_open", "0");
    }
  }

  function initChat() {
    if (!chatPanel || !chatOpenBtn || !chatCloseBtn) return;
    chatCloseBtn.addEventListener("click", () => setChatOpen(false));
    chatOpenBtn.addEventListener("click", () => setChatOpen(true));
    const saved = localStorage.getItem("freestyle_chat_open");
    setChatOpen(saved !== "0");
  }

  function initAdClose() {
    if (!adClose || !adBar) return;
    adClose.addEventListener("click", () => hide(adBar));
  }

  // -------------------------
  // Debug
  // -------------------------
  function attachDebug() {
    video.addEventListener("error", () => {
      console.error("VIDEO ERROR", video.error, "src:", video.currentSrc || video.src);
    });
  }

  // -------------------------
  // Start
  // -------------------------
  function start() {
    // ✅ STEP 1 FIX: FORCE overlay to show every refresh
    sessionStorage.removeItem("freestyle_entered");

    lockDownVideo();
    initOverlay();
    initChat();
    initAdClose();
    initVolumeUI();
    attachDebug();

    // Default muted until user clicks enter
    if (!isOverlayAccepted()) {
      video.muted = true;
      video.volume = 0.0;
      setMuteIcon();
    }

    pollNow();
    pingPresence();

    setInterval(pollNow, POLL_MS);
    setInterval(pingPresence, 15000);
  }

  document.addEventListener("DOMContentLoaded", start);
})();
