const DEFAULT_SETTINGS = {
  apiBaseUrl: "http://127.0.0.1:8000",
  enabledSources: { browser: false, youtube: false, leetcode: false, document: false },
};

const apiInput = document.querySelector("#api-base-url");
const status = document.querySelector("#status");
const sourceInputs = [...document.querySelectorAll("[data-source]")];

async function loadSettings() {
  let settings = await chrome.storage.local.get(DEFAULT_SETTINGS);

  try {
    const res = await fetch(`${settings.apiBaseUrl.replace(/\/$/, "")}/api/v1/sources`);
    if (res.ok) {
      const sources = await res.json();
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
        settings = await chrome.storage.local.get(DEFAULT_SETTINGS);
      }
    }
  } catch {
    // Backend may not be reachable yet
  }

  apiInput.value = settings.apiBaseUrl;
  for (const input of sourceInputs) {
    input.checked = Boolean(settings.enabledSources[input.dataset.source]);
  }

  if (settings.lastTabUnderstandingError) {
    let cleanErr = settings.lastTabUnderstandingError;
    try {
      const match = cleanErr.match(/Mosaic API returned \d+:\s*(\{.*\})/);
      if (match) {
        const parsed = JSON.parse(match[1]);
        if (parsed.detail) cleanErr = parsed.detail;
      }
    } catch {
      // Keep original
    }
    status.textContent = `Understand this tab failed: ${cleanErr}`;
    status.className = "error";
  } else if (settings.lastDeliveryError) {
    status.textContent = `Last delivery error: ${settings.lastDeliveryError}`;
    status.className = "error";
  } else if (settings.lastTabUnderstanding) {
    status.textContent = `Last tab understood: ${settings.lastTabUnderstanding.title}`;
    status.className = "success";
  }

  const fileStatusEl = document.querySelector("#file-access-status");
  if (fileStatusEl && chrome.extension?.isAllowedFileSchemeAccess) {
    chrome.extension.isAllowedFileSchemeAccess((isAllowed) => {
      if (isAllowed) {
        fileStatusEl.textContent = "✅ File URL access is currently allowed in your browser.";
        fileStatusEl.style.color = "#16a34a";
      } else {
        fileStatusEl.textContent = "⚠️ 'Allow access to file URLs' is currently OFF. Turn it ON in your browser's extension details to allow direct tab extraction on local files.";
        fileStatusEl.style.color = "#d97706";
      }
    });
  }
}

document.querySelector("#save").addEventListener("click", async () => {
  try {
    const parsedUrl = new URL(apiInput.value);
    if (parsedUrl.protocol !== "http:" && parsedUrl.protocol !== "https:") {
      throw new Error("The API address must start with http:// or https://.");
    }

    const enabledSources = Object.fromEntries(
      sourceInputs.map((input) => [input.dataset.source, input.checked]),
    );
    await chrome.storage.local.set({
      apiBaseUrl: parsedUrl.origin,
      enabledSources,
      lastDeliveryError: null,
      lastTabUnderstandingError: null,
    });

    // Also sync the toggles to Mosaic backend API if accessible
    for (const [source, enabled] of Object.entries(enabledSources)) {
      try {
        await fetch(`${parsedUrl.origin}/api/v1/sources/${source}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        });
      } catch {
        // Non-blocking sync
      }
    }

    status.textContent = "Settings saved and synced.";
    status.className = "success";
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : "Could not save settings.";
    status.className = "error";
  }
});

void loadSettings();
