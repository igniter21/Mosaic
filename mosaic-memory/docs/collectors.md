# Local collectors

Every collector is off by default. Before using one, enable the matching source on the Mosaic **Data Sources** page. The API will reject events for a disabled source.

## Browser, YouTube, and LeetCode

The Chrome extension in `extensions/browser` is a Manifest V3 extension. It captures only completed-page metadata:

- Browser: hostname, path, and the tab title. Query parameters and URL fragments are excluded.
- YouTube: a watched video ID and title.
- LeetCode: a viewed problem slug and title.

### Optional: Understand this tab with Gemini

This is a separate, click-only action—not normal browser collection. After you
explicitly enable the `browser` source in both Mosaic and the extension, click
the Mosaic toolbar icon while on one ordinary web page. The extension then:

1. extracts up to 6,000 characters from visible `article`, `main`, or page-body
   text, excluding forms, inputs, navigation, buttons, and scripts;
2. excludes incognito and browser-internal pages; and
3. sends only that bounded excerpt, title, host, path, and optional description
   to Gemini for one summary and a short topic list.

Mosaic stores the summary plus at most 2,500 characters of the selected excerpt
as local evidence. This makes it retrievable by **Ask Your Memory**. Ordinary
browsing never sends page text to Gemini. Standard **Ask** stays local; the
separate **Ask with Gemini** button sends only the question plus at most 6,000
characters of the top matching, click-approved tab excerpts.

To enable this optional feature, add these values to the ignored repository-root
`.env` file and restart the local API:

```text
MOSAIC_GEMINI_API_KEY=your-key
MOSAIC_GEMINI_MODEL=gemini-3.6-flash
```

Gemini receives content only for pages you click to understand. Do not use this
action on pages that contain information you do not want sent to Google. If a
key has been pasted into a chat, rotate it in Google AI Studio before use.

To install it locally:

1. Run the API at `http://127.0.0.1:8000` and open the frontend.
2. In Chrome, open `chrome://extensions`, turn on **Developer mode**, choose **Load unpacked**, and select `extensions/browser`.
3. Copy the extension ID shown by Chrome and add `MOSAIC_COLLECTOR_ORIGINS=chrome-extension://YOUR_EXTENSION_ID` to the repository-root `.env`. Restart the API.
4. Open the extension’s **Options**, confirm the API address, and opt into each desired source. Then enable the same source in Mosaic’s **Data Sources** page.

During ordinary collection, the extension records no page bodies, query strings,
URL fragments, cookies, credentials, or form data. The only page-text exception
is the separate, user-clicked **Understand this tab** flow above. Its options
page reports the latest delivery error; a 403 generally means the Mosaic source
still needs to be enabled.

## VS Code

The extension in `extensions/vscode` records only editor focus and save events. It sends the workspace-relative filename, language ID, and workspace name—never editor content, selection, diagnostics, or absolute paths.

From that directory, install the extension build dependencies and package it:

```powershell
npm install
npm run compile
npx @vscode/vsce package
```

Install the resulting `.vsix` in VS Code, enable the `vscode` source in Mosaic, then run **Mosaic Memory: Enable Metadata Collection** from the Command Palette. Use the corresponding Disable command to stop it immediately.

## Documents

The explicit CLI collector is intentionally pull-based: it processes only the paths you pass and reads file metadata rather than contents. Supported extensions are `.doc`, `.docx`, `.md`, `.odt`, `.pdf`, `.pptx`, `.rtf`, `.txt`, and `.xlsx`.

```powershell
# Inspect what would be sent; no event is created.
python scripts/collect_documents.py C:\Notes\plan.md --dry-run

# Collect a selected directory’s immediate supported files.
python scripts/collect_documents.py C:\Notes

# Recurse only when explicitly requested.
python scripts/collect_documents.py C:\Notes --recursive
```

Enable the `document` source first. The collector sends a filename, extension, byte size, and modified timestamp, with no path or document text.
