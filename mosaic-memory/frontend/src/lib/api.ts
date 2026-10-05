import type {
    AskMemoryResponse,
    DeletionResult,
    GlobalEraseResult,
    ContextResult,
    ContextSession,
    Goal,
    LearningGraph,
    LifecyclePreview,
    LifecycleRunResult,
    MemoryEvent,
    PrivacyLedgerEntry,
    Project,
    SessionDetail,
    Source,
    SourceSetting,
    ResumeContext,
} from "@/lib/types";

const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://127.0.0.1:8000/api/v1";

async function request<T>(
    path: string,
    options?: RequestInit,
): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, options);

    if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? "Request failed.");
    }

    return response.json();
}

export function getEvents(source?: Source): Promise<MemoryEvent[]> {
    const params = new URLSearchParams({ limit: "50" });

    if (source) {
        params.set("source", source);
    }

    return request<MemoryEvent[]>(`/events?${params.toString()}`);
}

export function getSources(): Promise<SourceSetting[]> {
    return request<SourceSetting[]>("/sources");
}

export function setSourceEnabled(
    source: Source,
    enabled: boolean,
): Promise<SourceSetting> {
    return request<SourceSetting>(`/sources/${source}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
    });
}

export function deleteEvent(eventId: string): Promise<DeletionResult> {
    return request<DeletionResult>(`/events/${eventId}`, {
        method: "DELETE",
    });
}

export function deleteEvents(filters: {
    source?: Source;
    from?: string;
    to?: string;
}): Promise<DeletionResult> {
    const params = new URLSearchParams();

    if (filters.source) params.set("source", filters.source);
    if (filters.from) params.set("from", filters.from);
    if (filters.to) params.set("to", filters.to);

    if (params.size === 0) {
        throw new Error("Choose a source, a date range, or both.");
    }

    return request<DeletionResult>(`/events?${params.toString()}`, {
        method: "DELETE",
    });
}

export function eraseAllMemory(
    confirmation: string,
): Promise<GlobalEraseResult> {
    return request<GlobalEraseResult>("/privacy/erase-all", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation }),
    });
}

export function askMemory(
    query: string,
    limit = 5,
): Promise<AskMemoryResponse> {
    return request<AskMemoryResponse>("/memory/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, limit }),
    });
}

export function askMemoryWithGemini(
    query: string,
    limit = 5,
): Promise<AskMemoryResponse> {
    return request<AskMemoryResponse>("/memory/ask-with-gemini", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, limit }),
    });
}
export function getContextSessions(limit = 20): Promise<ContextSession[]> {
    return request<ContextSession[]>(`/context/sessions?limit=${limit}`);
}

export function getCurrentContext(): Promise<ContextSession | null> {
    return request<ContextSession | null>("/context/resume");
}

export function askContext(input: {
    query: string;
    project_id?: string;
    goal_id?: string;
    agent_name?: string;
    limit?: number;
}): Promise<ContextResult> {
    return request<ContextResult>("/context/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
    });
}

export function rebuildContext(): Promise<{ sessions_rebuilt: number }> {
    return request<{ sessions_rebuilt: number }>("/context/rebuild", { method: "POST" });
}

export function getProjects(): Promise<Project[]> {
    return request<Project[]>("/context/projects");
}

export function getGoals(): Promise<Goal[]> {
    return request<Goal[]>("/context/goals");
}

export function createGoal(title: string, description: string, project_id?: string): Promise<Goal> {
    return request<Goal>("/context/goals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, description, project_id: project_id ?? null }),
    });
}

export function updateGoal(
    goalId: string,
    updates: { status?: string; description?: string },
): Promise<Goal> {
    return request<Goal>(`/context/goals/${goalId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
    });
}

export function getLearningGraph(): Promise<LearningGraph> {
    return request<LearningGraph>("/context/learning");
}

export function getPrivacyLedger(limit = 100): Promise<PrivacyLedgerEntry[]> {
    return request<PrivacyLedgerEntry[]>(`/context/privacy-ledger?limit=${limit}`);
}

export function previewLifecycle(): Promise<LifecyclePreview> {
    return request<LifecyclePreview>("/context/lifecycle/preview");
}

export function runLifecycle(execute: boolean): Promise<LifecycleRunResult> {
    return request<LifecycleRunResult>("/context/lifecycle/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ execute }),
    });
}

export function reindexSemantic(): Promise<{ indexed_memories: number }> {
    return request<{ indexed_memories: number }>("/context/reindex-semantic", { method: "POST" });
}

export function getSessionDetail(sessionId: string): Promise<SessionDetail> {
    return request<SessionDetail>(`/context/sessions/${sessionId}`);
}

export function getResumeContext(): Promise<ResumeContext> {
    return request<ResumeContext>(
        "/context/resume-summary",
    );
}