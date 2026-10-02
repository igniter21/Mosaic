const DEFAULT_SETTINGS = {
  apiBaseUrl: "http://127.0.0.1:8000",
  enabledSources: {
    browser: false,
    youtube: false,
    leetcode: false,
    document: false,
  },
};

const recentlyRecorded = new Map();
const DEDUPLICATION_WINDOW_MS = 60_000;

function eventEndpoint(apiBaseUrl) {
  return `${apiBaseUrl.replace(/\/$/, "")}/api/v1/events`;
}

function tabContextEndpoint(apiBaseUrl) {
  return `${apiBaseUrl.replace(/\/$/, "")}/api/v1/context/tab`;
}

function pdfContextEndpoint(apiBaseUrl) {
  return `${apiBaseUrl.replace(/\/$/, "")}/api/v1/context/pdf`;
}

async function markTabUnderstandingFailure(tabId, message) {
  await chrome.storage.local.set({
    lastTabUnderstandingError: message,
  });
  if (!tabId) return;

  await chrome.action.setBadgeText({ tabId, text: "!" });
  await chrome.action.setBadgeBackgroundColor({ tabId, color: "#dc2626" });

  let cleanMessage = message || "Could not understand this tab.";
  try {
    const jsonMatch = cleanMessage.match(/Mosaic API returned \d+:\s*(\{.*\})/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[1]);
      if (parsed.detail) cleanMessage = parsed.detail;
    }
  } catch {
    // Keep raw message
  }

  await chrome.action.setTitle({
    tabId,
    title: `Mosaic: ${cleanMessage.slice(0, 100)}`,
  });
}

async function syncSourcesFromApi(apiBaseUrl) {
  try {
    const url = `${apiBaseUrl.replace(/\/$/, "")}/api/v1/sources`;
    const response = await fetch(url);
    if (!response.ok) return null;
    const sources = await response.json();
    const settings = await chrome.storage.local.get(DEFAULT_SETTINGS);
    const updated = { ...settings.enabledSources };
    let changed = false;
    for (const item of sources) {
      if (item.source in updated && updated[item.source] !== item.enabled) {
        updated[item.source] = item.enabled;
        changed = true;
      }
    }
    if (changed) {
      await chrome.storage.local.set({ enabledSources: updated });
    }
    return updated;
  } catch {
    return null;
  }
}

function isSupportedPage(url) {
  return url.protocol === "http:" || url.protocol === "https:" || url.protocol === "file:";
}

function extractYouTubeVideoId(url) {
  if (!url) return null;
  const hostname = (url.hostname || "").toLowerCase();
  if (hostname === "youtu.be") {
    return url.pathname.slice(1).split("/")[0].split("?")[0].split("#")[0] || null;
  }
  if (hostname === "youtube.com" || hostname.endsWith(".youtube.com")) {
    if (url.searchParams?.has("v")) return url.searchParams.get("v");
    const shortsMatch = url.pathname.match(/^\/shorts\/([^/?#]+)/);
    if (shortsMatch) return shortsMatch[1];
    const liveMatch = url.pathname.match(/^\/live\/([^/?#]+)/);
    if (liveMatch) return liveMatch[1];
    const embedMatch = url.pathname.match(/^\/embed\/([^/?#]+)/);
    if (embedMatch) return embedMatch[1];
  }
  return null;
}

function isYouTubeVideoPage(url) {
  return Boolean(extractYouTubeVideoId(url));
}

function isPdf(url, tab) {
  const path = (url.pathname || "").toLowerCase();
  if (path.endsWith(".pdf") || path.includes(".pdf?") || path.includes(".pdf#")) return true;
  if (path.startsWith("/pdf/") || path.includes("/pdf/")) return true;
  if (tab?.title && tab.title.toLowerCase().endsWith(".pdf")) return true;
  return false;
}

function classifyPage(tab) {
  if (!tab.url) return null;

  let url;
  try {
    url = new URL(tab.url);
  } catch {
    return null;
  }

  if (!isSupportedPage(url)) return null;

  if (isPdf(url, tab)) {
    const isLocal = url.protocol === "file:";
    const decodedPath = decodeURIComponent(url.pathname);
    const filename = decodedPath.split("/").pop() || "document.pdf";
    const title = tab.title?.trim() || filename;
    const hostname = isLocal ? "local-file" : url.hostname.toLowerCase();
    const cleanPath = isLocal ? decodedPath : url.pathname;
    return {
      source: "document",
      eventType: "document_viewed",
      title,
      identity: `document:${hostname}${cleanPath}`,
      payload: { host: hostname, path: cleanPath },
    };
  }

  if (url.protocol === "file:") {
    const decodedPath = decodeURIComponent(url.pathname);
    const filename = decodedPath.split("/").pop() || "offline-document";
    const title = tab.title?.trim() || filename;
    return {
      source: "document",
      eventType: "document_viewed",
      title,
      identity: `document:${decodedPath}`,
      payload: { host: "local-file", path: decodedPath },
    };
  }

  const hostname = url.hostname.toLowerCase();
  const title = tab.title?.trim() || hostname;

  const youtubeVideoId = extractYouTubeVideoId(url);
  if (youtubeVideoId) {
    let cleanVideoTitle = title;
    if (cleanVideoTitle.toLowerCase() === "youtube" || cleanVideoTitle === hostname) {
      cleanVideoTitle = `YouTube Video (${youtubeVideoId})`;
    } else {
      cleanVideoTitle = cleanVideoTitle.replace(/^\(\d+\)\s*/, "").replace(/\s*-\s*YouTube$/, "").trim();
    }
    return {
      source: "youtube",
      eventType: "video_viewed",
      title: cleanVideoTitle,
      identity: `youtube:${youtubeVideoId}`,
      payload: { video_id: youtubeVideoId, host: hostname },
    };
  }

  if (hostname === "leetcode.com" || hostname.endsWith(".leetcode.com")) {
    const match = url.pathname.match(/^\/problems\/([^/]+)/);

    if (!match) return null;

    return {
      source: "leetcode",
      eventType: "problem_viewed",
      title,
      identity: `leetcode:${match[1]}`,
      payload: { problem_slug: match[1], host: hostname },
    };
  }

  // Query strings and fragments frequently contain tokens or search terms, so
  // they are deliberately excluded from the local event payload.
  return {
    source: "browser",
    eventType: "page_viewed",
    title,
    identity: `browser:${hostname}${url.pathname}`,
    payload: { host: hostname, path: url.pathname },
  };
}

function wasRecentlyRecorded(identity) {
  const now = Date.now();
  const recordedAt = recentlyRecorded.get(identity);

  recentlyRecorded.set(identity, now);

  for (const [key, value] of recentlyRecorded) {
    if (now - value > DEDUPLICATION_WINDOW_MS) recentlyRecorded.delete(key);
  }

  return recordedAt !== undefined && now - recordedAt < DEDUPLICATION_WINDOW_MS;
}

async function recordTab(tab) {
  const event = classifyPage(tab);
  if (!event || wasRecentlyRecorded(event.identity)) return;

  const settings = await chrome.storage.local.get(DEFAULT_SETTINGS);
  if (!settings.enabledSources[event.source]) return;

  try {
    const response = await fetch(eventEndpoint(settings.apiBaseUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_id: crypto.randomUUID(),
        occurred_at: new Date().toISOString(),
        source: event.source,
        event_type: event.eventType,
        title: event.title.slice(0, 500),
        payload: event.payload,
        privacy_level: "normal",
        retention_class: "short_term",
      }),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Mosaic API returned ${response.status}: ${detail}`);
    }

    await chrome.storage.local.set({ lastDeliveryError: null });
  } catch (error) {
    await chrome.storage.local.set({
      lastDeliveryError: error instanceof Error ? error.message : String(error),
    });
  }
}

async function recordYouTubeVideo(message, tab) {
  const { videoId, title, channel, url } = message;
  const identity = `youtube:${videoId}`;
  if (wasRecentlyRecorded(identity)) return;

  const settings = await chrome.storage.local.get(DEFAULT_SETTINGS);
  if (!settings.enabledSources.youtube) return;

  let host = "youtube.com";
  try {
    if (url) host = new URL(url).hostname.toLowerCase();
  } catch {}

  try {
    const response = await fetch(eventEndpoint(settings.apiBaseUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_id: crypto.randomUUID(),
        occurred_at: new Date().toISOString(),
        source: "youtube",
        event_type: "video_viewed",
        title: (title || `YouTube Video (${videoId})`).slice(0, 500),
        payload: { video_id: videoId, host, channel: channel || undefined },
        privacy_level: "normal",
        retention_class: "short_term",
      }),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Mosaic API returned ${response.status}: ${detail}`);
    }

    await chrome.storage.local.set({ lastDeliveryError: null });
  } catch (error) {
    await chrome.storage.local.set({
      lastDeliveryError: error instanceof Error ? error.message : String(error),
    });
  }
}

function extractVisiblePageContext() {
  function getCleanText(el) {
    if (!el) return "";
    const clone = el.cloneNode(true);
    clone.querySelectorAll(
      "aside, button, footer, form, header, input, nav, noscript, script, select, style, textarea, [hidden], [aria-hidden='true']",
    ).forEach((element) => element.remove());
    return (clone.innerText || clone.textContent || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  let text = "";
  const root = document.querySelector("article, main, [role='main']");
  if (root) {
    text = getCleanText(root);
  }
  if (!text || text.length < 80) {
    text = getCleanText(document.body);
  }
  text = text.slice(0, 6_000);

  const description = document.querySelector("meta[name='description']")?.content
    ?.replace(/\s+/g, " ")
    .trim()
    .slice(0, 500) || null;

  return {
    title: document.title.trim().slice(0, 500),
    description,
    contextText: text,
  };
}

function extractYouTubePageContext() {
  function cleanTitle(raw) {
    if (!raw) return "";
    return raw
      .replace(/^\(\d+\)\s*/, "")
      .replace(/\s*-\s*YouTube$/, "")
      .trim();
  }

  const titleEl = document.querySelector(
    "ytd-watch-metadata h1 yt-formatted-string, #title h1 yt-formatted-string, h1.ytd-watch-metadata, #title h1, ytd-reel-video-renderer[is-active] #title"
  );
  const title = cleanTitle(titleEl?.textContent) || cleanTitle(document.title) || "YouTube Video";

  // Channel name
  const channelEl = document.querySelector(
    "ytd-watch-metadata #owner #channel-name a, " +
    "ytd-watch-metadata #upload-info #channel-name a, " +
    "#owner #channel-name a, " +
    "ytd-video-owner-renderer #channel-name a, " +
    "ytd-channel-name a, " +
    "ytd-reel-video-renderer[is-active] #channel-name a, " +
    "link[itemprop='name']"
  );
  const channel = channelEl?.textContent?.trim()?.slice(0, 200) || "";

  // Video description from modern expander or metadata
  const descEl = document.querySelector(
    "#description-inline-expander .ytd-text-inline-expander, " +
    "ytd-watch-metadata #description, " +
    "ytd-text-inline-expander #plain-snippet-text, " +
    "ytd-text-inline-expander .content, " +
    "ytd-expander[collapsed] #description-inner, " +
    "#description-inner, " +
    "ytd-structured-description-content-renderer #description"
  );
  const description = descEl
    ? (descEl.innerText || descEl.textContent || "").replace(/\s+/g, " ").trim().slice(0, 2000)
    : "";

  // Keywords / Tags from meta
  const keywords = document.querySelector("meta[name='keywords']")?.content?.trim() || "";

  // Try to extract transcript segments if the transcript panel is open
  let transcript = "";
  const transcriptSegments = document.querySelectorAll(
    "ytd-transcript-segment-renderer .segment-text, " +
    "ytd-transcript-body-renderer .segment-text, " +
    "yt-formatted-string.segment-text"
  );
  if (transcriptSegments.length > 0) {
    const parts = [];
    for (const seg of transcriptSegments) {
      const text = seg.textContent?.trim();
      if (text) parts.push(text);
    }
    transcript = parts.join(" ").slice(0, 4000);
  }

  // If no open transcript panel, try the engagement panels
  if (!transcript) {
    const engagementTranscript = document.querySelector(
      "ytd-engagement-panel-section-list-renderer[target-id='engagement-panel-searchable-transcript']"
    );
    if (engagementTranscript) {
      const segs = engagementTranscript.querySelectorAll(".segment-text");
      const parts = [];
      for (const seg of segs) {
        const text = seg.textContent?.trim();
        if (text) parts.push(text);
      }
      transcript = parts.join(" ").slice(0, 4000);
    }
  }

  // Build combined context text
  const metaDescription = document.querySelector("meta[name='description']")?.content
    ?.replace(/\s+/g, " ").trim().slice(0, 500) || "";

  const contextParts = [
    `Video Title: ${title}`,
    channel ? `Channel: ${channel}` : "",
    description ? `Description: ${description}` : "",
    metaDescription && metaDescription !== description ? `Summary: ${metaDescription}` : "",
    keywords ? `Keywords: ${keywords}` : "",
    transcript ? `Transcript: ${transcript}` : "",
  ].filter(Boolean);

  let contextText = contextParts.join("\n\n").slice(0, 6000);
  if (contextText.length < 30) {
    contextText = `Video: ${title}\nChannel: ${channel || "YouTube Creator"}\nDescription: ${description || metaDescription || "Watched on YouTube"}`;
  }

  return {
    title,
    channel,
    description: description || metaDescription || null,
    transcript: transcript || null,
    contextText,
  };
}

async function understandCurrentTab(tab) {
  if (!tab.id || !tab.url || tab.incognito) {
    await markTabUnderstandingFailure(
      tab.id,
      "Mosaic cannot understand an incognito or unavailable tab.",
    );
    return;
  }

  let url;
  try {
    url = new URL(tab.url);
  } catch {
    await markTabUnderstandingFailure(
      tab.id,
      "Mosaic could not parse this tab's URL.",
    );
    return;
  }

  if (!isSupportedPage(url)) {
    await markTabUnderstandingFailure(
      tab.id,
      "Mosaic can only understand web pages and local files (http, https, or file://).",
    );
    return;
  }

  // Determine which source and handler to use
  const isLocal = url.protocol === "file:";
  const isYouTube = !isLocal && isYouTubeVideoPage(url);
  const isPdfDoc = isPdf(url, tab);

  let requiredSource;
  let sourceLabel;
  if (isLocal || isPdfDoc) {
    requiredSource = "document";
    sourceLabel = "Offline documents";
  } else if (isYouTube) {
    requiredSource = "youtube";
    sourceLabel = "YouTube";
  } else {
    requiredSource = "browser";
    sourceLabel = "Browser pages";
  }

  let settings = await chrome.storage.local.get(DEFAULT_SETTINGS);
  if (!settings.enabledSources[requiredSource]) {
    const synced = await syncSourcesFromApi(settings.apiBaseUrl);
    if (synced?.[requiredSource]) {
      settings = await chrome.storage.local.get(DEFAULT_SETTINGS);
    }
  }

  if (!settings.enabledSources[requiredSource]) {
    await markTabUnderstandingFailure(
      tab.id,
      `Enable ${sourceLabel} in Mosaic and this extension before understanding this content.`,
    );
    chrome.runtime.openOptionsPage().catch(() => undefined);
    return;
  }

  // Provide immediate visual feedback while processing
  await chrome.action.setBadgeText({ tabId: tab.id, text: "..." });
  await chrome.action.setBadgeBackgroundColor({ tabId: tab.id, color: "#6366f1" });
  const analyzeLabel = isPdfDoc ? "PDF" : isLocal ? "offline document" : isYouTube ? "YouTube video" : "tab";
  await chrome.action.setTitle({
    tabId: tab.id,
    title: `Mosaic is analyzing this ${analyzeLabel}...`,
  });

  try {
    if (isPdfDoc) {
      await understandPdfTab(tab, url, settings);
    } else if (isYouTube) {
      await understandYouTubeTab(tab, url, settings);
    } else if (isLocal) {
      await understandOfflineDocument(tab, url, settings);
    } else {
      await understandBrowserTab(tab, url, settings);
    }
  } catch (error) {
    await markTabUnderstandingFailure(
      tab.id,
      error instanceof Error ? error.message : String(error),
    );
  }
}

async function understandBrowserTab(tab, url, settings) {
  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: extractVisiblePageContext,
  });
  const page = results[0]?.result;
  if (!page?.contextText || page.contextText.length < 80) {
    throw new Error("There was not enough visible page text to understand.");
  }

  const response = await fetch(tabContextEndpoint(settings.apiBaseUrl), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_id: crypto.randomUUID(),
      occurred_at: new Date().toISOString(),
      title: page.title || tab.title || url.hostname,
      host: url.hostname.toLowerCase(),
      path: url.pathname || "/",
      description: page.description,
      context_text: page.contextText,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Mosaic API returned ${response.status}: ${detail}`);
  }

  const result = await response.json();
  await chrome.storage.local.set({
    lastTabUnderstandingError: null,
    lastTabUnderstanding: {
      at: new Date().toISOString(),
      summary: result.summary,
      title: page.title || tab.title || url.hostname,
    },
  });
  await chrome.action.setBadgeText({ tabId: tab.id, text: "AI" });
  await chrome.action.setBadgeBackgroundColor({ tabId: tab.id, color: "#16a34a" });
  await chrome.action.setTitle({
    tabId: tab.id,
    title: "Mosaic understood this tab. Open the dashboard to ask about it.",
  });
}

async function understandYouTubeTab(tab, url, settings) {
  const videoId = extractYouTubeVideoId(url);

  let page = null;
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractYouTubePageContext,
    });
    page = results[0]?.result;
  } catch {}

  const rawTitle = page?.title || tab.title || "YouTube Video";
  const cleanTitle = rawTitle.replace(/^\(\d+\)\s*/, "").replace(/\s*-\s*YouTube$/, "").trim() || "YouTube Video";
  let contextText = page?.contextText || "";

  if (contextText.length < 30) {
    contextText = `YouTube Video: ${cleanTitle}\nVideo ID: ${videoId || "unknown"}\nChannel: ${page?.channel || "YouTube Creator"}\nURL: ${url.href}`;
  }

  const response = await fetch(tabContextEndpoint(settings.apiBaseUrl), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_id: crypto.randomUUID(),
      occurred_at: new Date().toISOString(),
      title: cleanTitle.slice(0, 500),
      host: url.hostname.toLowerCase(),
      path: url.pathname || "/",
      description: page?.description || null,
      context_text: contextText,
      source: "youtube",
      video_id: videoId || undefined,
      channel: page?.channel || null,
      has_transcript: !!page?.transcript,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Mosaic API returned ${response.status}: ${detail}`);
  }

  const result = await response.json();
  await chrome.storage.local.set({
    lastTabUnderstandingError: null,
    lastTabUnderstanding: {
      at: new Date().toISOString(),
      summary: result.summary,
      title: cleanTitle,
      source: "youtube",
      videoId,
    },
  });
  await chrome.action.setBadgeText({ tabId: tab.id, text: "AI" });
  await chrome.action.setBadgeBackgroundColor({ tabId: tab.id, color: "#16a34a" });
  await chrome.action.setTitle({
    tabId: tab.id,
    title: "Mosaic understood this YouTube video. Open the dashboard to ask about it.",
  });
}

async function understandOfflineDocument(tab, url, settings) {
  const decodedPath = decodeURIComponent(url.pathname);
  const filename = decodedPath.split("/").pop() || "local-document";

  let page = null;
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractVisiblePageContext,
    });
    page = results[0]?.result;
  } catch {
    // Script execution may fail if "Allow access to file URLs" is disabled in browser
  }

  const contextText = page?.contextText || "";
  const pageTitle = page?.title || tab.title || filename;
  const description = page?.description || `Local document: ${filename}`;

  const response = await fetch(tabContextEndpoint(settings.apiBaseUrl), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_id: crypto.randomUUID(),
      occurred_at: new Date().toISOString(),
      title: pageTitle.slice(0, 500),
      host: "local-file",
      path: decodedPath || `/${filename}`,
      description,
      context_text: contextText,
      source: "document",
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Mosaic API returned ${response.status}: ${detail}`);
  }

  const result = await response.json();
  await chrome.storage.local.set({
    lastTabUnderstandingError: null,
    lastTabUnderstanding: {
      at: new Date().toISOString(),
      summary: result.summary,
      title: pageTitle,
      source: "document",
    },
  });
  await chrome.action.setBadgeText({ tabId: tab.id, text: "AI" });
  await chrome.action.setBadgeBackgroundColor({ tabId: tab.id, color: "#16a34a" });
  await chrome.action.setTitle({
    tabId: tab.id,
    title: "Mosaic understood this document. Open the dashboard to ask about it.",
  });
}

async function understandPdfTab(tab, url, settings) {
  const isLocal = url.protocol === "file:";
  const decodedPath = decodeURIComponent(url.pathname);
  const filename = decodedPath.split("/").pop() || "document.pdf";
  const title = (tab.title?.trim() && !tab.title.toLowerCase().endsWith(".pdf")) ? tab.title.trim() : filename;

  const formData = new FormData();
  formData.append("title", title);
  formData.append("host", isLocal ? "local-file" : url.hostname.toLowerCase());
  formData.append("path", isLocal ? decodedPath : (url.pathname || `/${filename}`));
  formData.append("source", "document");

  // Attempt to fetch PDF bytes directly from background service worker (for online PDFs)
  if (!isLocal) {
    try {
      const pdfResponse = await fetch(url.href);
      if (pdfResponse.ok) {
        const blob = await pdfResponse.blob();
        if (blob.size > 0) {
          formData.append("file", blob, filename);
        }
      }
    } catch {
      // If background fetch is blocked, the backend will handle it
    }
  }

  const response = await fetch(pdfContextEndpoint(settings.apiBaseUrl), {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Mosaic API returned ${response.status}: ${detail}`);
  }

  const result = await response.json();
  await chrome.storage.local.set({
    lastTabUnderstandingError: null,
    lastTabUnderstanding: {
      at: new Date().toISOString(),
      summary: result.summary,
      title: title || filename,
      source: "document",
    },
  });
  await chrome.action.setBadgeText({ tabId: tab.id, text: "AI" });
  await chrome.action.setBadgeBackgroundColor({ tabId: tab.id, color: "#16a34a" });
  await chrome.action.setTitle({
    tabId: tab.id,
    title: "Mosaic understood this PDF. Open the dashboard to ask about it.",
  });
}

chrome.runtime.onInstalled.addListener(() => {
  void chrome.storage.local.get(DEFAULT_SETTINGS).then((settings) => {
    return syncSourcesFromApi(settings.apiBaseUrl);
  }).catch(() => undefined);
});

chrome.runtime.onStartup.addListener(() => {
  void chrome.storage.local.get(DEFAULT_SETTINGS).then((settings) => {
    return syncSourcesFromApi(settings.apiBaseUrl);
  }).catch(() => undefined);
});

chrome.tabs.onUpdated.addListener((_tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" || changeInfo.url) {
    void recordTab(tab);
  }
});

chrome.tabs.onActivated.addListener(({ tabId }) => {
  void chrome.tabs.get(tabId).then(recordTab).catch(() => undefined);
});

chrome.action.onClicked.addListener((tab) => {
  void understandCurrentTab(tab);
});

chrome.runtime.onMessage.addListener((message, sender) => {
  if (message?.type === "YOUTUBE_VIDEO_VIEWED" && message.videoId) {
    void recordYouTubeVideo(message, sender?.tab);
  }
});
