// Content script running inside YouTube tabs to reliably track video views
// across YouTube's Single-Page Application (SPA) navigation.

function extractVideoId(urlStr) {
  try {
    const u = new URL(urlStr || window.location.href);
    if (u.hostname === "youtu.be") {
      return u.pathname.slice(1).split("/")[0].split("?")[0].split("#")[0] || null;
    }
    if (u.hostname === "youtube.com" || u.hostname.endsWith(".youtube.com")) {
      if (u.searchParams.has("v")) return u.searchParams.get("v");
      const shortsMatch = u.pathname.match(/^\/shorts\/([^/?#]+)/);
      if (shortsMatch) return shortsMatch[1];
      const liveMatch = u.pathname.match(/^\/live\/([^/?#]+)/);
      if (liveMatch) return liveMatch[1];
      const embedMatch = u.pathname.match(/^\/embed\/([^/?#]+)/);
      if (embedMatch) return embedMatch[1];
    }
  } catch {}
  return null;
}

function cleanTitle(raw) {
  if (!raw) return "";
  return raw
    .replace(/^\(\d+\)\s*/, "") // Remove notification count prefix like (3)
    .replace(/\s*-\s*YouTube$/, "") // Remove trailing - YouTube
    .trim();
}

function getYouTubeTitle() {
  const el = document.querySelector(
    "ytd-watch-metadata h1 yt-formatted-string, #title h1 yt-formatted-string, h1.ytd-watch-metadata, #title h1, ytd-reel-video-renderer[is-active] #title"
  );
  const text = el?.textContent?.trim();
  if (text) return cleanTitle(text);
  return cleanTitle(document.title);
}

function getYouTubeChannel() {
  const el = document.querySelector(
    "ytd-watch-metadata #owner #channel-name a, " +
    "ytd-watch-metadata #upload-info #channel-name a, " +
    "#owner #channel-name a, " +
    "ytd-video-owner-renderer #channel-name a, " +
    "ytd-channel-name a, " +
    "ytd-reel-video-renderer[is-active] #channel-name a"
  );
  return el?.textContent?.trim()?.slice(0, 200) || "";
}

let lastNotifiedVideoId = null;
let lastNotifiedTime = 0;

function notifyVideoViewed() {
  const videoId = extractVideoId(window.location.href);
  if (!videoId) return;

  const now = Date.now();
  if (lastNotifiedVideoId === videoId && (now - lastNotifiedTime) < 30_000) {
    return;
  }

  const title = getYouTubeTitle();
  const channel = getYouTubeChannel();

  lastNotifiedVideoId = videoId;
  lastNotifiedTime = now;

  try {
    chrome.runtime.sendMessage({
      type: "YOUTUBE_VIDEO_VIEWED",
      videoId,
      title: title || `YouTube Video (${videoId})`,
      channel: channel || null,
      url: window.location.href,
    }).catch(() => undefined);
  } catch {}
}

// YouTube emits 'yt-navigate-finish' whenever in-page SPA navigation completes
window.addEventListener("yt-navigate-finish", () => {
  setTimeout(notifyVideoViewed, 600);
});

// Also trigger on initial script injection
setTimeout(notifyVideoViewed, 1000);
