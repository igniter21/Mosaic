import * as vscode from "vscode";

type EventKind = "editor_focused" | "document_saved";

const DEDUPLICATION_WINDOW_MS = 60_000;
const recentlyRecorded = new Map<string, number>();

function setting<T>(name: string): T {
    return vscode.workspace.getConfiguration("mosaicMemory").get<T>(name)!;
}

function wasRecentlyRecorded(document: vscode.TextDocument, kind: EventKind): boolean {
    const key = `${kind}:${document.uri.toString()}`;
    const now = Date.now();
    const previous = recentlyRecorded.get(key);
    recentlyRecorded.set(key, now);
    return previous !== undefined && now - previous < DEDUPLICATION_WINDOW_MS;
}

async function recordDocument(document: vscode.TextDocument, kind: EventKind): Promise<void> {
    if (!setting<boolean>("enabled") || document.uri.scheme !== "file") return;
    if (wasRecentlyRecorded(document, kind)) return;

    const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
    // Standalone files could make `asRelativePath` return an absolute path.
    // Skipping them preserves the extension's no-absolute-path guarantee.
    if (!workspaceFolder) return;

    const filename = vscode.workspace.asRelativePath(document.uri, false);
    const baseUrl = setting<string>("apiBaseUrl").replace(/\/$/, "");
    const payload = {
        language_id: document.languageId,
        file_extension: filename.includes(".") ? filename.split(".").pop() : null,
        workspace_name: workspaceFolder?.name ?? null,
        // Keep only a relative path: content, absolute paths, selections, and
        // diagnostics are intentionally never collected by this extension.
        relative_path: filename,
    };

    try {
        const response = await fetch(`${baseUrl}/api/v1/events`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                event_id: crypto.randomUUID(),
                occurred_at: new Date().toISOString(),
                source: "vscode",
                event_type: kind,
                title: filename,
                payload,
                privacy_level: "normal",
                retention_class: "short_term",
            }),
        });

        if (!response.ok) {
            throw new Error(`Mosaic API returned ${response.status}`);
        }
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        void vscode.window.showWarningMessage(`Mosaic Memory did not record activity: ${message}`);
    }
}

export function activate(context: vscode.ExtensionContext): void {
    context.subscriptions.push(
        vscode.commands.registerCommand("mosaicMemory.enable", async () => {
            await vscode.workspace.getConfiguration("mosaicMemory").update("enabled", true, vscode.ConfigurationTarget.Global);
            void vscode.window.showInformationMessage("Mosaic Memory metadata collection is enabled.");
        }),
        vscode.commands.registerCommand("mosaicMemory.disable", async () => {
            await vscode.workspace.getConfiguration("mosaicMemory").update("enabled", false, vscode.ConfigurationTarget.Global);
            void vscode.window.showInformationMessage("Mosaic Memory metadata collection is disabled.");
        }),
        vscode.window.onDidChangeActiveTextEditor((editor) => {
            if (editor) void recordDocument(editor.document, "editor_focused");
        }),
        vscode.workspace.onDidSaveTextDocument((document) => {
            void recordDocument(document, "document_saved");
        }),
    );

    if (vscode.window.activeTextEditor) {
        void recordDocument(vscode.window.activeTextEditor.document, "editor_focused");
    }
}

export function deactivate(): void {
    recentlyRecorded.clear();
}
