// static/freestyle/js/tv.js
(() => {
  "use strict";

  const cfg = window.FS_TV || {};
  const channelSlug = cfg.channelSlug || "main";

  const POLL_MS = Number(cfg.pollMs || 6000);
  const CHAT_POLL_MS = Number(cfg.chatPollMs || 1500);
  const DRIFT_FIX_SEC = Number(cfg.driftFixSec || 4);
  const BIG_DRIFT_SEC = Number(cfg.bigDriftSec || 10);

  // Elements
  const videoEl    = document.getElementById("player");
  const captionsEl = document.getElementById("captions");

  const gateEl   = document.getElementById("gate");
  const agreeBox = document.getElementById("agreeBox");
  const enterBtn = document.getElementById("enterBtn");

  const muteBtn   = document.getElementById("muteBtn");
  const volSlider = document.getElementById("volSlider");
  const fsBtn     = document.getElementById("fsBtn");

  const chatMeta  = document.getElementById("chatMeta");
  const chatList  = document.getElementById("chatList");
  const chatInput = document.getElementById("chatInput");
  const sendBtn   = document.getElementById("sendBtn");

  const fireBtn   = document.getElementById("fireBtn");
  const nahBtn    = document.getElementById("nahBtn");
  const fireCount = document.getElementById("fireCount");
  const nahCount  = document.getElementById("nahCount");
  const rxNote    = document.getElementById("rxNote");

  // Hard-guard: if the core video element is missing, do NOT crash the whole page
  if (!videoEl) {
    console.error("TV ERROR: #player video element not found. (Your HTML must have id='player')");
    return;
  }

  // URLs
  const nowUrlBase      = `/api/freestyle/channel/${channelSlug}/now.json`;
  const captionsUrlFor  = (videoId) => `/api/freestyle/video/${videoId}/captions.json`;

  const chatPollUrl = (afterId) => `/api/freestyle/channel/${channelSlug}/chat/messages.json?after_id=${afterId||0}`;
  const chatSendUrl = `/api/freestyle/channel/${channelSlug}/chat/send.json`;

  const reactionStateUrl = (videoId) => `/api/freestyle/channel/${channelSlug}/reactions/state.json?video_id=${encodeURIComponent(videoId)}`;
  const reactionVoteUrl  = `/api/freestyle/channel/${channelSlug}/reactions/vote.json`;

  // Local reset behavior
  const isLocal = (location.hostname === "127.0.0.1" || location.hostname === "localhost");
  let didLocalReset = false;

  // HLS state
  let hls = null;
  let currentVideoId = null;
  let currentSrc = null;
  let switching = false;

  // Captions state
  let capWords = [];
  let capIndex = 0;
  let capLastVideoId = null;

  // Chat state
  let lastChatId = 0;

  // Live-lock state (NO SKIP / REPLAY)
  // We estimate "live time" between server polls so seeking always snaps to live
  let serverOffsetAtSync = 0;
  let serverSyncPerfMs = performance.now();
  let serverDuration = 0;
  let allowSeekProgrammatically = false;

  function estimatedLiveTimeSec() {
    const elapsed = (performance.now() - serverSyncPerfMs) / 1000;
    let t = (serverOffsetAtSync || 0) + elapsed;
    if (serverDuration > 0) {
      // wrap if duration known
      t = t % serverDuration;
    }
    return Math.max(0, t);
  }

  function destroyHls() {
    if (hls) { hls.destroy(); hls = null; }
  }

  function attachSource(url, isHls) {
    destroyHls();
    if (isHls) {
      if (videoEl.canPlayType("application/vnd.apple.mpegurl")) {
        videoEl.src = url;
      } else if (window.Hls) {
        hls = new Hls({ enableWorker: true });
        hls.loadSource(url);
        hls.attachMedia(videoEl);
      } else {
        throw new Error("HLS not supported.");
      }
    } else {
      videoEl.src = url;
    }
  }

  function safeSeek(t) {
    t = Math.max(0, Math.floor(t || 0));
    try {
      allowSeekProgrammatically = true;
      videoEl.currentTime = t;
    } catch (e) {
    } finally {
      allowSeekProgrammatically = false;
    }
  }

  function escapeHtml(s) {
    return (s || "")
      .replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;")
      .replaceAll('"',"&quot;").replaceAll("'","&#039;");
  }

  // Block seeking (no skip / replay)
  videoEl.addEventListener("seeking", () => {
    if (switching) return;
    if (allowSeekProgrammatically) return;

    // snap back to live
    const live = estimatedLiveTimeSec();
    safeSeek(live);
  });

  // Also block common playback shortcut keys
  window.addEventListener("keydown", (e) => {
    const blocked = ["ArrowLeft", "ArrowRight", "j", "k", "l", " "];
    if (blocked.includes(e.key)) e.preventDefault();
  }, { passive: false });

  // Basic player defaults
  videoEl.muted = true;
  videoEl.controls = false;
  videoEl.disablePictureInPicture = true;
  videoEl.controlsList = "nodownload noplaybackrate noremoteplayback";
  if (volSlider) videoEl.volume = parseFloat(volSlider.value || "0.8");

  // Client ID / Guest name
  function getClientId(){
    let cid = localStorage.getItem("fs_client_id");
    if (!cid){
      cid = "cid_" + Math.random().toString(16).slice(2) + Date.now().toString(16);
      localStorage.setItem("fs_client_id", cid);
    }
    return cid;
  }
  const CLIENT_ID = getClientId();

  function getGuestName(){
    let g = localStorage.getItem("fs_guest_name");
    if (!g){
      g = "Guest-" + Math.floor(1000 + Math.random()*9000);
      localStorage.setItem("fs_guest_name", g);
    }
    return g;
  }
  const GUEST = getGuestName();
  if (chatMeta) chatMeta.textContent = GUEST;

  // Mute controls
  function updateMuteBtn() {
    if (!muteBtn) return;
    muteBtn.textContent = videoEl.muted ? "Unmute" : "Mute";
  }
  updateMuteBtn();

  if (muteBtn) {
    muteBtn.addEventListener("click", async () => {
      videoEl.muted = !videoEl.muted;
      updateMuteBtn();
      try { await videoEl.play(); } catch(e) {}
    });
  }

  if (volSlider) {
    volSlider.addEventListener("input", () => {
      videoEl.volume = parseFloat(volSlider.value);
      if (videoEl.volume > 0) videoEl.muted = false;
      updateMuteBtn();
    });
  }

  if (fsBtn) {
    fsBtn.addEventListener("click", async () => {
      try {
        if (document.fullscreenElement) await document.exitFullscreen();
        else await videoEl.requestFullscreen();
      } catch(e) {}
    });
  }

  // Gate / terms: video keeps running, only unlock audio
  if (enterBtn && agreeBox && gateEl) {
    enterBtn.disabled = true;
    agreeBox.addEventListener("change", () => {
      if (agreeBox.checked){
        enterBtn.classList.add("enabled");
        enterBtn.disabled = false;
      } else {
        enterBtn.classList.remove("enabled");
        enterBtn.disabled = true;
      }
    });

    enterBtn.addEventListener("click", async () => {
      if (!agreeBox.checked) return;
      gateEl.style.display = "none";
      videoEl.muted = false;
      updateMuteBtn();
      try { await videoEl.play(); } catch(e) {}
    });
  }

  async function fetchNow(forceReset=false){
    const shouldReset = forceReset || (isLocal && !didLocalReset);
    const url = shouldReset ? `${nowUrlBase}?reset=1` : nowUrlBase;

    const res = await fetch(url, { cache:"no-store" });
    if (shouldReset) didLocalReset = true;
    if (!res.ok) throw new Error(`now.json HTTP ${res.status}`);

    return await res.json();
  }

  async function loadCaptions(videoId){
    if (!captionsEl) return;
    if (!videoId || capLastVideoId === videoId) return;

    capLastVideoId = videoId;
    capWords = []; capIndex = 0;
    captionsEl.style.display = "none";
    captionsEl.textContent = "";

    try {
      const res = await fetch(captionsUrlFor(videoId), { cache:"no-store" });
      if (!res.ok) throw new Error("no captions");
      const data = await res.json();

      capWords = Array.isArray(data.words) ? data.words : [];
      capIndex = 0;

      if (capWords.length) captionsEl.style.display = "block";
    } catch(e) {
      capWords = []; capIndex = 0;
      captionsEl.style.display = "none";
    }
  }

  function findIndexForTime(t){
    let lo = 0, hi = capWords.length - 1, ans = 0;
    while (lo <= hi){
      const mid = (lo + hi) >> 1;
      const s = capWords[mid].s || 0;
      if (s <= t){ ans = mid; lo = mid + 1; }
      else hi = mid - 1;
    }
    return ans;
  }

  function renderCaptions(){
    if (!captionsEl) return;
    if (!capWords.length) return;

    const t = videoEl.currentTime || 0;

    if (capIndex >= capWords.length || (capWords[capIndex] && (capWords[capIndex].s || 0) > t + 0.4)){
      capIndex = findIndexForTime(t);
    }
    while (capIndex < capWords.length && (capWords[capIndex].e || 0) < t) capIndex++;
    if (capIndex >= capWords.length) return;

    const start = Math.max(0, capIndex - 3);
    const end   = Math.min(capWords.length, capIndex + 6);

    const parts = [];
    for (let i=start; i<end; i++){
      const w = (capWords[i].w || "").trim();
      if (!w) continue;

      const isHot = (i === capIndex) &&
        (t >= (capWords[i].s||0) - 0.02) &&
        (t <= (capWords[i].e||0) + 0.02);

      parts.push(`<span class="cw ${isHot ? "hot":""}">${escapeHtml(w)}</span>`);
    }
    captionsEl.innerHTML = parts.join(" ");
    captionsEl.style.display = parts.length ? "block" : "none";
  }

  (function rafLoop(){
    renderCaptions();
    requestAnimationFrame(rafLoop);
  })();

  async function applyServer(data){
    const item = data.item;
    if (!item || !item.play_url) return;

    // accept offset from either top-level or inside item
    let offset = (typeof data.offset_seconds === "number")
      ? data.offset_seconds
      : (typeof item.offset_seconds === "number" ? item.offset_seconds : 0);

    const duration = (typeof data.duration_seconds === "number" && data.duration_seconds > 0)
      ? data.duration_seconds
      : (typeof item.duration_seconds === "number" ? item.duration_seconds : 0);

    serverDuration = duration || 0;

    if (duration > 0 && offset >= duration) offset = offset % duration;

    // update live-lock base
    serverOffsetAtSync = Math.max(0, offset || 0);
    serverSyncPerfMs = performance.now();

    const nextId = String(item.video_id ?? "0");
    const nextSrc = String(item.play_url);
    const nextIsHls = !!item.is_hls;

    if (nextId !== currentVideoId){
      currentVideoId = nextId;
      await refreshReactions();
      await loadCaptions(nextId);
    }

    // only reload video if URL truly changed
    if (nextSrc !== currentSrc){
      if (switching) return;
      switching = true;

      currentSrc = nextSrc;
      videoEl.style.visibility = "hidden";

      attachSource(nextSrc, nextIsHls);

      const onMeta = async () => {
        videoEl.removeEventListener("loadedmetadata", onMeta);

        // seek once metadata is ready
        safeSeek(serverOffsetAtSync);

        videoEl.style.visibility = "visible";
        try { await videoEl.play(); } catch(e) {}
        switching = false;
      };
      videoEl.addEventListener("loadedmetadata", onMeta);

      try { await videoEl.play(); } catch(e) {}
      return;
    }

    // drift correction
    if (!Number.isFinite(videoEl.duration) || videoEl.duration <= 0) return;

    const ct = (videoEl.currentTime || 0);
    const drift = Math.abs(ct - serverOffsetAtSync);

    if (!videoEl.seeking && drift > BIG_DRIFT_SEC) safeSeek(serverOffsetAtSync);
    else if (!videoEl.seeking && drift > DRIFT_FIX_SEC) safeSeek(serverOffsetAtSync);
  }

  async function syncNow(forceReset=false){
    const data = await fetchNow(forceReset);
    await applyServer(data);
  }

  // Avoid weird looping on ended
  videoEl.addEventListener("pause", () => {
    if (videoEl.ended) return;
    setTimeout(() => videoEl.play().catch(()=>{}), 150);
  });

  videoEl.addEventListener("ended", () => {
    syncNow(false).catch(()=>{});
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      syncNow(false).catch(()=>{});
      videoEl.play().catch(()=>{});
    }
  });

  // Initial sync + polling
  syncNow(false).catch(() => alert("Failed to load Live TV endpoint: " + nowUrlBase));
  setInterval(() => syncNow(false).catch(()=>{}), POLL_MS);

  // CHAT
  function appendMsg(m){
    if (!chatList) return;
    const div = document.createElement("div");
    div.className = "msg";
    div.innerHTML = `<span class="u">${escapeHtml(m.username)}</span><span class="t">${escapeHtml(m.message)}</span>`;
    chatList.appendChild(div);
    chatList.scrollTop = chatList.scrollHeight;
  }

  async function pollChat(){
    try{
      const res = await fetch(chatPollUrl(lastChatId), { cache:"no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const items = Array.isArray(data.items) ? data.items : [];
      for (const m of items){
        lastChatId = Math.max(lastChatId, m.id || 0);
        appendMsg(m);
      }
    }catch(e){}
  }
  setInterval(pollChat, CHAT_POLL_MS);
  pollChat();

  async function sendChat(){
    if (!chatInput) return;
    const msg = (chatInput.value || "").trim();
    if (!msg) return;
    chatInput.value = "";

    try{
      await fetch(chatSendUrl, {
        method:"POST",
        headers: { "Content-Type":"application/json" },
        body: JSON.stringify({ username: GUEST, message: msg })
      });
    }catch(e){}
  }
  if (sendBtn) sendBtn.addEventListener("click", sendChat);
  if (chatInput) chatInput.addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });

  // REACTIONS
  function votedKey(videoId){ return `fs_voted_${videoId}`; }

  function bubble(emoji){
    const b = document.createElement("div");
    b.className = "bubble";
    b.textContent = emoji;
    document.body.appendChild(b);
    setTimeout(() => b.remove(), 1200);
  }

  async function refreshReactions(){
    if (!currentVideoId) return;
    try{
      const res = await fetch(reactionStateUrl(currentVideoId), {
        cache:"no-store",
        headers: { "X-Client-Id": CLIENT_ID }
      });
      if (!res.ok) return;
      const data = await res.json();
      if (!data.ok) return;

      if (fireCount) fireCount.textContent = data.counts?.fire ?? 0;
      if (nahCount)  nahCount.textContent  = data.counts?.nah  ?? 0;

      const votedLocal = localStorage.getItem(votedKey(currentVideoId));
      const voted = data.voted || votedLocal;

      if (voted){
        if (fireBtn) fireBtn.disabled = true;
        if (nahBtn)  nahBtn.disabled  = true;
        if (rxNote)  rxNote.textContent = "voted";
      } else {
        if (fireBtn) fireBtn.disabled = false;
        if (nahBtn)  nahBtn.disabled  = false;
        if (rxNote)  rxNote.textContent = "Vote once per video";
      }
    }catch(e){}
  }

  async function vote(reaction){
    if (!currentVideoId) return;
    if (localStorage.getItem(votedKey(currentVideoId))) return;

    try{
      const res = await fetch(reactionVoteUrl, {
        method:"POST",
        headers: { "Content-Type":"application/json" },
        body: JSON.stringify({ video_id: currentVideoId, reaction, client_id: CLIENT_ID })
      });
      const data = await res.json();
      if (!data.ok && !data.already_voted) return;

      localStorage.setItem(votedKey(currentVideoId), reaction);
      bubble(reaction === "fire" ? "🔥" : "🚫");
      await refreshReactions();
    }catch(e){}
  }

  if (fireBtn) fireBtn.addEventListener("click", () => vote("fire"));
  if (nahBtn)  nahBtn.addEventListener("click",  () => vote("nah"));
  setInterval(refreshReactions, 2500);

})();
