(() => {
  "use strict";

  // ---------- helpers ----------
  function clamp(n, a, b){ return Math.max(a, Math.min(b, n)); }
  function escapeHtml(s){
    return (s || "")
      .replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;")
      .replaceAll('"',"&quot;").replaceAll("'","&#039;");
  }
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  // ---------- config ----------
  const CHANNEL = (document.documentElement.dataset.channel || "main").trim();

  // IMPORTANT: these MUST match freestyle/urls.py
  const NOW_URL = `/api/freestyle/channel/${encodeURIComponent(CHANNEL)}/now.json`;
  const PRESENCE_URL = `/api/freestyle/presence/ping.json`;
  const CHAT_POLL_URL = (afterId) =>
    `/api/freestyle/channel/${encodeURIComponent(CHANNEL)}/chat/messages.json?after_id=${afterId || 0}`;
  const CHAT_SEND_URL =
    `/api/freestyle/channel/${encodeURIComponent(CHANNEL)}/chat/send.json`;

  const REACT_STATE_URL = (videoId) =>
    `/api/freestyle/channel/${encodeURIComponent(CHANNEL)}/reactions/state.json?video_id=${encodeURIComponent(videoId)}`;
  const REACT_VOTE_URL =
    `/api/freestyle/channel/${encodeURIComponent(CHANNEL)}/reactions/vote.json`;

  const DURATION_SAVE_URL = (videoId) =>
    `/api/freestyle/video/${encodeURIComponent(videoId)}/duration.json`;

  const CSRF_TOKEN = getCookie("csrftoken");

  const POLL_MS = 2500;
  const CHAT_POLL_MS = 1200;
  const PRESENCE_MS = 10000;

  const VIEW_BASE = 1100;

  // Sync policy (NO rewind ever)
  const SEEK_FORWARD_IF_BEHIND_SEC = 6;   // only jump forward if badly behind
  const DRIFT_OK_SEC = 1.25;              // do nothing if within this window

  // ---------- elements ----------
  const videoEl = document.getElementById("player");
  const qualityHud = document.getElementById("qualityHud");

  const muteBtn = document.getElementById("muteBtn");
  const volSlider = document.getElementById("volSlider");
  const fsBtn = document.getElementById("fsBtn");

  const viewerCountEl = document.getElementById("viewerCount");

  const chatDock = document.getElementById("chatDock");
  const chatOpenBtn = document.getElementById("chatOpenBtn");
  const chatCloseBtn = document.getElementById("chatCloseBtn");
  const chatUserEl = document.getElementById("chatUser");
  const chatList = document.getElementById("chatList");
  const chatInput = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");

  const fireBtn = document.getElementById("fireBtn");
  const nahBtn = document.getElementById("nahBtn");
  const fireCount = document.getElementById("fireCount");
  const nahCount = document.getElementById("nahCount");
  const rxNote = document.getElementById("rxNote");

  const gateEl = document.getElementById("gate");
  const agreeBox = document.getElementById("agreeBox");
  const enterBtn = document.getElementById("enterBtn");

  // ---------- ids ----------
  function getGuestName(){
    let g = localStorage.getItem("fs_guest_name");
    if (!g){
      g = "Guest-" + Math.floor(1000 + Math.random()*9000);
      localStorage.setItem("fs_guest_name", g);
    }
    return g;
  }
  const GUEST = getGuestName();
  chatUserEl.textContent = GUEST;

  function getSid(){
    let sid = sessionStorage.getItem("fs_sid");
    if (!sid){
      sid = (crypto?.randomUUID?.() || ("sid_" + Math.random().toString(16).slice(2) + Date.now().toString(16)));
      sessionStorage.setItem("fs_sid", sid);
    }
    return sid;
  }
  const SID = getSid();

  function getClientId(){
    let cid = localStorage.getItem("fs_client_id");
    if (!cid){
      cid = "cid_" + Math.random().toString(16).slice(2) + Date.now().toString(16);
      localStorage.setItem("fs_client_id", cid);
    }
    return cid;
  }
  const CLIENT_ID = getClientId();

  // ---------- UI ----------
  function setQuality(text){
    if (qualityHud) qualityHud.textContent = text;
  }
  function updateMuteBtn(){
    muteBtn.textContent = videoEl.muted ? "Unmute" : "Mute";
  }

  // start muted until enter
  videoEl.muted = true;
  videoEl.volume = parseFloat(volSlider.value || "0.8");
  updateMuteBtn();

  muteBtn.addEventListener("click", async () => {
    videoEl.muted = !videoEl.muted;
    updateMuteBtn();
    try { await videoEl.play(); } catch(e) {}
  });

  volSlider.addEventListener("input", () => {
    const v = parseFloat(volSlider.value || "0.8");
    videoEl.volume = isFinite(v) ? v : 0.8;
    if (videoEl.volume > 0) videoEl.muted = false;
    updateMuteBtn();
  });

  fsBtn.addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await videoEl.requestFullscreen();
    } catch(e) {}
  });

  // ---------- enter overlay ----------
  function setEnterEnabled(on){
    enterBtn.disabled = !on;
    enterBtn.classList.toggle("enabled", !!on);
  }
  setEnterEnabled(false);
  agreeBox.addEventListener("change", () => setEnterEnabled(agreeBox.checked));

  enterBtn.addEventListener("click", async () => {
    gateEl.style.display = "none";
    videoEl.muted = false;
    updateMuteBtn();
    try { await videoEl.play(); } catch(e) {}
  });

  // ---------- chat open/close ----------
  function setChatOpen(open){
    if (open){
      chatDock.style.display = "block";
      chatOpenBtn.style.display = "none";
      document.body.classList.remove("chat-closed");
    } else {
      chatDock.style.display = "none";
      chatOpenBtn.style.display = "block";
      document.body.classList.add("chat-closed");
    }
    localStorage.setItem("fs_chat_open", open ? "1" : "0");
  }
  setChatOpen(localStorage.getItem("fs_chat_open") !== "0");
  chatCloseBtn.addEventListener("click", () => setChatOpen(false));
  chatOpenBtn.addEventListener("click", () => setChatOpen(true));

  // ---------- reactions ----------
  function votedKey(videoId){ return `fs_voted_${videoId}`; }

  function bubble(emoji){
    const b = document.createElement("div");
    b.className = "bubble";
    b.textContent = emoji;
    document.body.appendChild(b);
    setTimeout(() => b.remove(), 1200);
  }

  let currentVideoId = null;

  async function refreshReactions(){
    if (!currentVideoId) return;
    try{
      const res = await fetch(REACT_STATE_URL(currentVideoId), {
        cache:"no-store",
        headers: { "X-Client-Id": CLIENT_ID }
      });
      if (!res.ok) return;
      const data = await res.json();
      if (!data.ok) return;

      fireCount.textContent = data.counts?.fire ?? 0;
      nahCount.textContent  = data.counts?.nah  ?? 0;

      const votedLocal = localStorage.getItem(votedKey(currentVideoId));
      const voted = data.voted || votedLocal;

      if (voted){
        fireBtn.disabled = true;
        nahBtn.disabled = true;
        rxNote.textContent = "voted";
      } else {
        fireBtn.disabled = false;
        nahBtn.disabled = false;
        rxNote.textContent = "Vote once per video";
      }
    }catch(e){}
  }

  async function vote(reaction){
    if (!currentVideoId) return;
    if (localStorage.getItem(votedKey(currentVideoId))) return;

    try{
      const res = await fetch(REACT_VOTE_URL, {
        method:"POST",
        headers: {
          "Content-Type":"application/json",
          "X-CSRFToken": CSRF_TOKEN
        },
        body: JSON.stringify({ video_id: currentVideoId, reaction, client_id: CLIENT_ID })
      });
      const data = await res.json();
      if (!data.ok && !data.already_voted) return;

      localStorage.setItem(votedKey(currentVideoId), reaction);
      bubble(reaction === "fire" ? "🔥" : "🚫");
      await refreshReactions();
    }catch(e){}
  }

  fireBtn.addEventListener("click", () => vote("fire"));
  nahBtn.addEventListener("click", () => vote("nah"));
  setInterval(refreshReactions, 2500);

  // ---------- duration repair ----------
  async function trySaveDuration(videoId){
    if (!videoId) return;
    const d = Number(videoEl.duration || 0);
    if (!d || d < 2) return;

    const dur = Math.floor(d);
    const key = `fs_saved_dur_${videoId}_${dur}`;
    if (localStorage.getItem(key)) return;

    try{
      await fetch(DURATION_SAVE_URL(videoId), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": CSRF_TOKEN
        },
        body: JSON.stringify({ duration_seconds: dur })
      });
      localStorage.setItem(key, "1");
    }catch(e){}
  }

  // ---------- HLS / source handling ----------
  let hls = null;
  let currentSrc = null;
  let currentIsHls = false;

  // MP4 should NOT locally loop (prevents end replay glitch)
  let mp4Ended = false;

  function destroyHls(){
    if (hls) { hls.destroy(); hls = null; }
  }

  function pickBestLevel(levels){
    // Choose highest height; tie-break by bitrate
    let bestIdx = 0;
    for (let i = 0; i < levels.length; i++){
      const a = levels[i];
      const b = levels[bestIdx];
      const ah = a?.height || 0;
      const bh = b?.height || 0;
      if (ah > bh) bestIdx = i;
      else if (ah === bh && (a?.bitrate || 0) > (b?.bitrate || 0)) bestIdx = i;
    }
    return bestIdx;
  }

  function attachSource(url, isHls){
    destroyHls();
    mp4Ended = false;

    currentIsHls = !!isHls;

    // hard rule: never loop MP4 locally
    videoEl.loop = false;

    if (isHls) {
      if (videoEl.canPlayType("application/vnd.apple.mpegurl")) {
        // Safari native HLS (ABR controlled by browser)
        videoEl.src = url;
        setQuality("Quality: HLS (Safari auto)");
      } else if (window.Hls) {
        hls = new Hls({
          enableWorker: true,

          // IMPORTANT: do NOT cap to player size (keeps 1080 if available)
          capLevelToPlayerSize: false,

          // buffer a bit more smoothly
          maxBufferLength: 45,
          backBufferLength: 30,
        });

        hls.loadSource(url);
        hls.attachMedia(videoEl);

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          const levels = hls.levels || [];
          if (!levels.length) {
            setQuality("Quality: HLS");
            return;
          }

          const best = pickBestLevel(levels);

          // lock to best
          hls.currentLevel = best;
          hls.loadLevel = best;

          const L = levels[best];
          const label = L?.height ? `${L.height}p` : `L${best}`;
          setQuality(`Quality: ${label} (locked)`);
        });

        hls.on(Hls.Events.LEVEL_SWITCHED, (_, data) => {
          const idx = data?.level;
          const L = hls?.levels?.[idx];
          const label = L?.height ? `${L.height}p` : `L${idx}`;
          setQuality(`Quality: ${label}`);
        });

      } else {
        videoEl.src = "";
        setQuality("Quality: HLS unsupported");
      }
    } else {
      videoEl.src = url;
      videoEl.addEventListener("loadedmetadata", () => {
        const h = videoEl.videoHeight || 0;
        setQuality(h ? `Quality: ${h}p (MP4)` : "Quality: MP4");
      }, { once:true });
    }
  }

  // If MP4 ends, we do NOT loop.
  // We pause and wait for scheduler to move to next content.
  videoEl.addEventListener("ended", () => {
    if (!currentIsHls) {
      mp4Ended = true;
      try { videoEl.pause(); } catch(e) {}
    }
  });

  // ---------- NOW sync (NO rewind) ----------
  async function fetchNow(){
    const res = await fetch(NOW_URL, { cache:"no-store" });
    if (!res.ok) throw new Error(`now.json ${res.status}`);
    return await res.json();
  }

  async function syncNow(){
    const data = await fetchNow();
    const item = data?.item;
    if (!item?.play_url) return;

    const nextSrc = String(item.play_url);
    const nextIsHls = !!item.is_hls;
    const nextId = String(item.video_id || "");
    const offset = Number(data.offset_seconds || 0);

    // update viewers (backend returns REAL count, we add base)
    const viewersReal = Number(data.viewers || 0) || 0;
    viewerCountEl.textContent = String(VIEW_BASE + viewersReal);

    // set current video id for reactions
    currentVideoId = nextId;

    // source change
    if (nextSrc !== currentSrc) {
      currentSrc = nextSrc;
      currentIsHls = nextIsHls;

      attachSource(nextSrc, nextIsHls);

      videoEl.addEventListener("loadedmetadata", async () => {
        trySaveDuration(nextId);

        // seek to station offset ONCE when MP4 loads
        if (!nextIsHls) {
          const dur = Number(videoEl.duration || 0);
          const safe = (dur > 1) ? clamp(Math.floor(offset), 0, Math.max(0, Math.floor(dur) - 1)) : Math.floor(offset);
          try { videoEl.currentTime = safe; } catch(e) {}
        }

        try { await videoEl.play(); } catch(e) {}
        refreshReactions();
      }, { once:true });

      try { await videoEl.play(); } catch(e) {}
      return;
    }

    // same source: only correct if we're BEHIND (never rewind)
    if (!currentIsHls) {
      if (!videoEl.seeking) {
        const ct = Number(videoEl.currentTime || 0);
        const behind = offset - ct;

        // If video ended locally but scheduler still says same src,
        // kick it back to the station offset and play.
        if (mp4Ended) {
          mp4Ended = false;
          try { videoEl.currentTime = Math.max(0, Math.floor(offset)); } catch(e) {}
          try { await videoEl.play(); } catch(e) {}
          return;
        }

        // If we're within tolerance, do nothing
        if (Math.abs(behind) <= DRIFT_OK_SEC) return;

        // If we're behind a lot, jump forward.
        if (behind > SEEK_FORWARD_IF_BEHIND_SEC) {
          try { videoEl.currentTime = Math.max(0, Math.floor(offset)); } catch(e) {}
          return;
        }

        // If we're slightly behind, do NOTHING (no micro-seeks).
        // This prevents “restarting after a few seconds”.
      }
    }
  }

  // ---------- Chat ----------
  let lastChatId = 0;

  function appendMsg(m){
    const div = document.createElement("div");
    div.className = "msg";
    div.innerHTML = `<span class="u">${escapeHtml(m.username)}</span><span class="t">${escapeHtml(m.message)}</span>`;
    chatList.appendChild(div);
    chatList.scrollTop = chatList.scrollHeight;
  }

  async function pollChat(){
    try{
      const res = await fetch(CHAT_POLL_URL(lastChatId), { cache:"no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const items = Array.isArray(data.items) ? data.items : [];
      for (const m of items){
        lastChatId = Math.max(lastChatId, m.id || 0);
        appendMsg(m);
      }
    }catch(e){}
  }

  async function sendChat(){
    const msg = (chatInput.value || "").trim();
    if (!msg) return;
    chatInput.value = "";
    try{
      await fetch(CHAT_SEND_URL, {
        method:"POST",
        headers: { "Content-Type":"application/json", "X-CSRFToken": CSRF_TOKEN },
        body: JSON.stringify({ username: GUEST, message: msg })
      });
    }catch(e){}
  }

  sendBtn.addEventListener("click", sendChat);
  chatInput.addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });

  // ---------- Presence ----------
  async function pingPresence(){
    try{
      await fetch(`${PRESENCE_URL}?sid=${encodeURIComponent(SID)}&channel=${encodeURIComponent(CHANNEL)}`, { cache:"no-store" });
    }catch(e){}
  }

  // resync when tab returns
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      syncNow().catch(()=>{});
      videoEl.play().catch(()=>{});
    }
  });

  // ---------- start ----------
  syncNow().catch(()=>{});
  pollChat().catch(()=>{});
  pingPresence().catch(()=>{});

  setInterval(() => syncNow().catch(()=>{}), POLL_MS);
  setInterval(() => pollChat().catch(()=>{}), CHAT_POLL_MS);
  setInterval(() => pingPresence().catch(()=>{}), PRESENCE_MS);

})();
