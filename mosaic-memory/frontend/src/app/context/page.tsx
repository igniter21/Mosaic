"use client";

import { FormEvent, useEffect, useState } from "react";

import { Icon } from "@/components/icons";
import { PageHeader } from "@/components/page-header";
import { SourceMark } from "@/components/source-mark";
import {
    askContext,
    createGoal,
    getContextSessions,
    getCurrentContext,
    getSessionDetail,
    getGoals,
    getLearningGraph,
    getPrivacyLedger,
    getProjects,
    reindexSemantic,
    rebuildContext,
    updateGoal,
} from "@/lib/api";
import type {
    ContextResult,
    ContextSession,
    Goal,
    LearningGraph,
    PrivacyLedgerEntry,
    Project,
    SessionDetail,
    Source,
} from "@/lib/types";

type Notice = {
    message: string;
    tone: "error" | "info" | "success";
};

const SAMPLE_QUERIES = [
    "What was I working on?",
    "Recent coding sessions",
    "Local retrieval research",
    "What did I practice?",
];

const KNOWN_SOURCES: Set<string> = new Set([
    "browser",
    "youtube",
    "leetcode",
    "vscode",
    "document",
    "git",
]);

function isKnownSource(source: string): source is Source {
    return KNOWN_SOURCES.has(source);
}

function formatDate(value: string) {
    return new Intl.DateTimeFormat("en-IN", {
        day: "numeric",
        month: "short",
        hour: "numeric",
        minute: "2-digit",
    }).format(new Date(value));
}

function formatDuration(startedAt: string, endedAt: string) {
    const diffMs = Math.max(0, new Date(endedAt).getTime() - new Date(startedAt).getTime());
    const mins = Math.round(diffMs / 60000);
    if (mins < 1) return "< 1m";
    if (mins < 60) return `${mins}m`;
    const hours = Math.floor(mins / 60);
    const remMins = mins % 60;
    return remMins > 0 ? `${hours}h ${remMins}m` : `${hours}h`;
}

function formatBytes(bytes: number) {
    if (bytes === 0) return "0 B";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ContextPage() {
    const [current, setCurrent] = useState<ContextSession | null>(null);
    const [sessions, setSessions] = useState<ContextSession[]>([]);
    const [projects, setProjects] = useState<Project[]>([]);
    const [goals, setGoals] = useState<Goal[]>([]);
    const [learning, setLearning] = useState<LearningGraph | null>(null);
    const [ledger, setLedger] = useState<PrivacyLedgerEntry[]>([]);
    const [sessionDetail, setSessionDetail] = useState<SessionDetail | null>(null);
    const [expandedMemoryId, setExpandedMemoryId] = useState<string | null>(null);
    const [query, setQuery] = useState("");
    const [result, setResult] = useState<ContextResult | null>(null);
    const [goalTitle, setGoalTitle] = useState("");
    const [selectedGoalId, setSelectedGoalId] = useState("");
    const [selectedProjectId, setSelectedProjectId] = useState("");
    const [isCreatingGoal, setIsCreatingGoal] = useState(false);
    const [isIndexing, setIsIndexing] = useState(false);
    const [isRebuilding, setIsRebuilding] = useState(false);
    const [isSearching, setIsSearching] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [loading, setLoading] = useState(true);
    const [notice, setNotice] = useState<Notice | null>(null);

    async function load(showFeedback = false) {
        if (showFeedback) setIsRefreshing(true);
        try {
            const [active, sessionRows, projectRows, goalRows, learningRow, ledgerRows] =
                await Promise.all([
                    getCurrentContext(),
                    getContextSessions(),
                    getProjects(),
                    getGoals(),
                    getLearningGraph(),
                    getPrivacyLedger(),
                ]);
            setCurrent(active);
            setSessions(sessionRows);
            setProjects(projectRows);
            setGoals(goalRows);
            setLearning(learningRow);
            setLedger(ledgerRows);
            if (showFeedback) {
                setNotice({ message: "Context data refreshed.", tone: "success" });
            }
        } catch (error) {
            setNotice({
                message: error instanceof Error ? error.message : "Could not load context.",
                tone: "error",
            });
        } finally {
            setLoading(false);
            if (showFeedback) setIsRefreshing(false);
        }
    }

    useEffect(() => {
        const loadTimer = window.setTimeout(() => {
            void load();
        }, 0);

        return () => window.clearTimeout(loadTimer);
    }, []);

    async function executeSearch(searchQuery: string, projectId?: string, goalId?: string) {
        const normalized = searchQuery.trim();
        if (normalized.length < 2) return;
        setNotice(null);
        setIsSearching(true);
        try {
            const searchResult = await askContext({
                query: normalized,
                limit: 8,
                agent_name: "ui",
                project_id: projectId || undefined,
                goal_id: goalId || undefined,
            });
            setResult(searchResult);
        } catch (error) {
            setNotice({
                message: error instanceof Error ? error.message : "Context search failed.",
                tone: "error",
            });
        } finally {
            setIsSearching(false);
        }
    }

    async function submitContext(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        await executeSearch(query, selectedProjectId, selectedGoalId);
    }

    function handleSampleClick(sampleQuery: string) {
        setQuery(sampleQuery);
        void executeSearch(sampleQuery, selectedProjectId, selectedGoalId);
    }

    async function addGoal(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (goalTitle.trim().length < 2) return;
        setIsCreatingGoal(true);
        setNotice(null);
        try {
            await createGoal(
                goalTitle.trim(),
                "Created from Mosaic Context OS",
                selectedProjectId || undefined,
            );
            setGoalTitle("");
            await load();
            setNotice({ message: "Goal added successfully.", tone: "success" });
        } catch (error) {
            setNotice({
                message: error instanceof Error ? error.message : "Could not create goal.",
                tone: "error",
            });
        } finally {
            setIsCreatingGoal(false);
        }
    }

    async function toggleGoal(goal: Goal) {
        const nextStatus = goal.status === "completed" ? "in_progress" : "completed";
        // Optimistic update
        setGoals((prev) =>
            prev.map((item) => (item.id === goal.id ? { ...item, status: nextStatus } : item)),
        );
        try {
            await updateGoal(goal.id, { status: nextStatus });
        } catch (error) {
            // Revert on error
            setGoals((prev) =>
                prev.map((item) => (item.id === goal.id ? { ...item, status: goal.status } : item)),
            );
            setNotice({
                message: error instanceof Error ? error.message : "Could not update goal status.",
                tone: "error",
            });
        }
    }

    async function rebuild() {
        setIsRebuilding(true);
        setNotice({ message: "Rebuilding sessions…", tone: "info" });
        try {
            const response = await rebuildContext();
            setNotice({
                message: `Rebuilt ${response.sessions_rebuilt} sessions.`,
                tone: "success",
            });
            await load();
        } catch (error) {
            setNotice({
                message: error instanceof Error ? error.message : "Rebuild failed.",
                tone: "error",
            });
        } finally {
            setIsRebuilding(false);
        }
    }

    async function openSession(sessionId: string) {
        if (sessionDetail?.id === sessionId) {
            setSessionDetail(null);
            return;
        }
        try {
            setSessionDetail(await getSessionDetail(sessionId));
        } catch (error) {
            setNotice({
                message: error instanceof Error ? error.message : "Could not open session.",
                tone: "error",
            });
        }
    }

    async function semanticIndex() {
        setIsIndexing(true);
        setNotice({ message: "Building the local semantic index…", tone: "info" });
        try {
            const response = await reindexSemantic();
            setNotice({
                message: `Indexed ${response.indexed_memories} memories locally. Fast semantic reranking enabled!`,
                tone: "success",
            });
        } catch (error) {
            setNotice({
                message:
                    error instanceof Error
                        ? error.message
                        : "Semantic indexing failed.",
                tone: "error",
            });
        } finally {
            setIsIndexing(false);
        }
    }

    function filterByProject(projectId: string) {
        setSelectedProjectId(projectId === selectedProjectId ? "" : projectId);
        if (query.trim().length >= 2) {
            void executeSearch(query, projectId === selectedProjectId ? "" : projectId, selectedGoalId);
        }
    }

    function filterByGoal(goalId: string) {
        setSelectedGoalId(goalId === selectedGoalId ? "" : goalId);
        if (query.trim().length >= 2) {
            void executeSearch(query, selectedProjectId, goalId === selectedGoalId ? "" : goalId);
        }
    }

    const activeGoalsCount = goals.filter((g) => g.status !== "completed").length;
    const completedGoalsCount = goals.filter((g) => g.status === "completed").length;

    return (
        <section aria-busy={loading} className="pb-16">
            <PageHeader
                description="Mosaic reconstructs work sessions, projects, goals, and learning signals from your private local timeline instead of treating every event as an isolated record."
                eyebrow="Context operating system"
                title="Understand what you were doing."
            />

            {/* Quick Metrics & Actions Bar */}
            <div className="mt-8 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex flex-wrap items-center gap-2">
                    <button
                        className="inline-flex items-center gap-2 rounded-xl bg-[#1d1e22] px-4 py-2.5 text-xs font-semibold text-white shadow-sm transition hover:bg-[#34353a] active:scale-[0.98] disabled:cursor-wait disabled:opacity-60"
                        disabled={isRebuilding || loading}
                        onClick={rebuild}
                        type="button"
                    >
                        <Icon className={`h-3.5 w-3.5 ${isRebuilding ? "animate-spin" : ""}`} name="refresh" />
                        <span>{isRebuilding ? "Rebuilding sessions…" : "Rebuild context"}</span>
                    </button>
                    <button
                        className="inline-flex items-center gap-2 rounded-xl border border-[#dfdcff] bg-white px-4 py-2.5 text-xs font-semibold text-[#5146d7] shadow-sm transition hover:bg-[#f7f6ff] active:scale-[0.98] disabled:cursor-wait disabled:opacity-60"
                        disabled={isIndexing || loading}
                        onClick={semanticIndex}
                        type="button"
                    >
                        <Icon className={`h-3.5 w-3.5 text-[#6558f5] ${isIndexing ? "animate-spin" : ""}`} name="sparkles" />
                        <span>{isIndexing ? "Indexing memories…" : "Build local semantic index"}</span>
                    </button>
                    <button
                        aria-label="Refresh context data"
                        className="inline-flex items-center gap-1.5 rounded-xl border border-[#e8e8e4] bg-white px-3 py-2.5 text-xs font-medium text-[#67676d] transition hover:bg-[#f7f7f4] active:scale-[0.98] disabled:cursor-wait disabled:opacity-60"
                        disabled={isRefreshing || loading}
                        onClick={() => void load(true)}
                        title="Refresh context data"
                        type="button"
                    >
                        <Icon className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin text-[#6558f5]" : ""}`} name="refresh" />
                        <span className="hidden sm:inline">Refresh</span>
                    </button>
                </div>

                {/* Compact Context Status Indicators */}
                <div className="flex flex-wrap items-center gap-2 text-xs">
                    <div className="inline-flex items-center gap-1.5 rounded-full border border-[#e8e8e4] bg-white px-3 py-1 text-[#4c4c51]">
                        <span
                            className={`h-2 w-2 rounded-full ${
                                current ? "bg-emerald-500 ring-2 ring-emerald-200 animate-pulse" : "bg-slate-300"
                            }`}
                        />
                        <span className="font-medium">{current ? "Session Active" : "Idle"}</span>
                    </div>
                    <div className="inline-flex items-center gap-1.5 rounded-full border border-[#e8e8e4] bg-white px-3 py-1 text-[#67676d]">
                        <span className="font-semibold text-[#1d1e22]">{sessions.length}</span>
                        <span>episodes</span>
                    </div>
                    <div className="inline-flex items-center gap-1.5 rounded-full border border-[#e8e8e4] bg-white px-3 py-1 text-[#67676d]">
                        <span className="font-semibold text-[#1d1e22]">{projects.length}</span>
                        <span>projects</span>
                    </div>
                    <div className="inline-flex items-center gap-1.5 rounded-full border border-[#e8e8e4] bg-white px-3 py-1 text-[#67676d]">
                        <span className="font-semibold text-[#1d1e22]">{activeGoalsCount}</span>
                        <span>active goals</span>
                    </div>
                </div>
            </div>

            {/* Notice Bar */}
            {notice && (
                <div
                    aria-live="polite"
                    className={`mt-4 flex items-center justify-between gap-3 rounded-xl border px-4 py-3 text-sm shadow-sm transition-all ${
                        notice.tone === "error"
                            ? "border-red-200 bg-red-50 text-red-800"
                            : notice.tone === "success"
                              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                              : "border-[#dfdcff] bg-[#f7f6ff] text-[#5d5794]"
                    }`}
                    role={notice.tone === "error" ? "alert" : "status"}
                >
                    <div className="flex items-center gap-2.5">
                        <Icon
                            className={`h-4 w-4 shrink-0 ${
                                notice.tone === "error"
                                    ? "text-red-600"
                                    : notice.tone === "success"
                                      ? "text-emerald-600"
                                      : "text-[#6558f5]"
                            }`}
                            name={notice.tone === "success" ? "check" : notice.tone === "error" ? "shield" : "sparkles"}
                        />
                        <span>{notice.message}</span>
                    </div>
                    <button
                        aria-label="Dismiss notification"
                        className="rounded-lg p-1 text-current opacity-70 transition hover:bg-black/5 hover:opacity-100"
                        onClick={() => setNotice(null)}
                        type="button"
                    >
                        <Icon className="h-4 w-4" name="x" />
                    </button>
                </div>
            )}

            {/* Context Reconstruction (Ask Context) Card */}
            <div className="mt-6 rounded-2xl border border-[#dfdcff] bg-white p-4 shadow-[0_8px_30px_rgba(101,88,245,0.05)] sm:p-5">
                <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                        <span className="grid h-7 w-7 place-items-center rounded-lg bg-[#f0efff] text-[#5e52df]">
                            <Icon className="h-4 w-4" name="search" />
                        </span>
                        <h2 className="text-sm font-bold uppercase tracking-wider text-[#6558f5]">Reconstruct Context</h2>
                    </div>
                    {(selectedProjectId || selectedGoalId) && (
                        <button
                            className="inline-flex items-center gap-1 text-xs font-medium text-[#747579] hover:text-[#1d1e22]"
                            onClick={() => {
                                setSelectedProjectId("");
                                setSelectedGoalId("");
                            }}
                            type="button"
                        >
                            <Icon className="h-3 w-3" name="x" />
                            <span>Clear active filters</span>
                        </button>
                    )}
                </div>

                <form className="mt-4" onSubmit={submitContext}>
                    <div className="flex flex-col gap-3 sm:flex-row">
                        <div className="relative min-w-0 flex-1">
                            <input
                                aria-label="Question about your context"
                                className="w-full rounded-xl bg-[#f7f7f4] py-3 pr-10 pl-4 text-sm text-[#303136] outline-none ring-0 placeholder:text-[#929297] focus:ring-2 focus:ring-[#c9c4ff]"
                                onChange={(event) => setQuery(event.target.value)}
                                placeholder="What was I trying to finish yesterday?"
                                value={query}
                            />
                            {query && (
                                <button
                                    aria-label="Clear query text"
                                    className="absolute top-1/2 right-3 -translate-y-1/2 rounded-full p-1 text-[#929297] hover:bg-[#e8e8e4] hover:text-[#303136]"
                                    onClick={() => setQuery("")}
                                    type="button"
                                >
                                    <Icon className="h-3.5 w-3.5" name="x" />
                                </button>
                            )}
                        </div>
                        <button
                            className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#5b50e7] px-5 py-3 text-xs font-semibold text-white shadow-sm transition hover:bg-[#4e43d5] active:scale-[0.98] disabled:cursor-wait disabled:opacity-60"
                            disabled={isSearching || query.trim().length < 2}
                            type="submit"
                        >
                            <Icon className={`h-4 w-4 ${isSearching ? "animate-spin" : ""}`} name={isSearching ? "refresh" : "sparkles"} />
                            <span>{isSearching ? "Reconstructing…" : "Reconstruct"}</span>
                        </button>
                    </div>

                    {/* Filter Pills */}
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        <label className="flex items-center gap-2 text-xs text-[#77777b]">
                            <span className="sr-only">Limit to a project</span>
                            <div className="relative w-full">
                                <select
                                    className={`h-10 w-full appearance-none rounded-xl border bg-white pr-8 pl-3 text-xs text-[#4c4c51] outline-none transition focus:border-[#a8a1ff] ${
                                        selectedProjectId ? "border-[#a8a1ff] bg-[#fcfbff] font-semibold text-[#5146d7]" : "border-[#e8e8e4]"
                                    }`}
                                    onChange={(event) => setSelectedProjectId(event.target.value)}
                                    value={selectedProjectId}
                                >
                                    <option value="">All projects</option>
                                    {projects.map((project) => (
                                        <option key={project.id} value={project.id}>
                                            📁 {project.name}
                                        </option>
                                    ))}
                                </select>
                                <Icon className="pointer-events-none absolute top-1/2 right-3 h-3.5 w-3.5 -translate-y-1/2 text-[#85858a]" name="chevron-down" />
                            </div>
                        </label>
                        <label className="flex items-center gap-2 text-xs text-[#77777b]">
                            <span className="sr-only">Limit to a goal</span>
                            <div className="relative w-full">
                                <select
                                    className={`h-10 w-full appearance-none rounded-xl border bg-white pr-8 pl-3 text-xs text-[#4c4c51] outline-none transition focus:border-[#a8a1ff] ${
                                        selectedGoalId ? "border-[#a8a1ff] bg-[#fcfbff] font-semibold text-[#5146d7]" : "border-[#e8e8e4]"
                                    }`}
                                    onChange={(event) => setSelectedGoalId(event.target.value)}
                                    value={selectedGoalId}
                                >
                                    <option value="">All goals</option>
                                    {goals.map((goal) => (
                                        <option key={goal.id} value={goal.id}>
                                            🎯 {goal.title} {goal.status === "completed" ? "(Completed)" : ""}
                                        </option>
                                    ))}
                                </select>
                                <Icon className="pointer-events-none absolute top-1/2 right-3 h-3.5 w-3.5 -translate-y-1/2 text-[#85858a]" name="chevron-down" />
                            </div>
                        </label>
                    </div>

                    {/* Quick Sample Prompts */}
                    <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-[#747579]">
                        <span className="mr-1 font-medium">Try asking:</span>
                        {SAMPLE_QUERIES.map((sample) => (
                            <button
                                className="rounded-lg bg-[#f7f7f4] px-2.5 py-1 text-[11px] font-medium text-[#5c5c63] transition hover:bg-[#eef0fc] hover:text-[#5146d7]"
                                key={sample}
                                onClick={() => handleSampleClick(sample)}
                                type="button"
                            >
                                {sample}
                            </button>
                        ))}
                    </div>
                </form>
            </div>

            {/* Context Search Results */}
            {result && (
                <section className="mt-6 rounded-2xl border border-[#dfdcff] bg-white p-5 shadow-sm">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#6558f5]">Synthesized context</p>
                                <span className="rounded-full bg-[#f5f4ff] px-2.5 py-0.5 text-[10px] font-semibold text-[#5549db]">
                                    {String(result.evidence_receipt.candidate_count ?? result.memories.length)} candidates
                                </span>
                            </div>
                            <h2 className="mt-2 text-base font-semibold leading-relaxed text-[#27282c]">
                                {result.answer}
                            </h2>
                        </div>
                    </div>

                    {/* Receipt Metadata Chips */}
                    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[#f0f0ed] pt-3 text-[10px] text-[#747579]">
                        <span className="font-medium text-[#4c4c51]">Retrieval:</span>
                        <span className="rounded-md bg-[#f7f7f4] px-2 py-0.5 font-medium">{result.retrieval_method}</span>
                        {Boolean(result.evidence_receipt.semantic_rerank) && (
                            <span className="rounded-md bg-[#eef0fc] px-2 py-0.5 font-semibold text-[#5146d7]">
                                ✨ Semantic Reranked
                            </span>
                        )}
                        {Boolean(result.evidence_receipt.recency_boost) && (
                            <span className="rounded-md bg-emerald-50 px-2 py-0.5 font-semibold text-emerald-700">
                                ⏱ Recency Boosted
                            </span>
                        )}
                        {Boolean(result.evidence_receipt.policy_filtered) && (
                            <span className="rounded-md bg-slate-100 px-2 py-0.5 font-semibold text-slate-700">
                                🛡 Privacy Guard Active
                            </span>
                        )}
                    </div>

                    {/* Memories Reconstructed */}
                    <div className="mt-4 space-y-3">
                        {result.memories.map((memory) => {
                            const isExpanded = expandedMemoryId === memory.id;
                            const hasEvidence = memory.evidence && memory.evidence.length > 0;
                            return (
                                <article
                                    className="rounded-xl border border-[#efefec] bg-[#fcfcfb] p-4 transition hover:border-[#dfdcff] hover:bg-white"
                                    key={memory.id}
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="flex items-center gap-2.5">
                                            {isKnownSource(memory.source) ? (
                                                <SourceMark size="small" source={memory.source} />
                                            ) : (
                                                <span className="rounded-lg bg-[#f5f5f2] px-2 py-1 text-[10px] font-semibold uppercase text-[#747579]">
                                                    {memory.source}
                                                </span>
                                            )}
                                            <div>
                                                <time className="text-[11px] text-[#8e8e94]">
                                                    {formatDate(memory.occurred_at)}
                                                </time>
                                                {memory.score !== undefined && (
                                                    <span className="ml-2 rounded-full bg-[#f4f3ff] px-2 py-0.5 text-[10px] font-semibold text-[#5c52dc]">
                                                        {Math.round(memory.score * 100)}% match
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        {hasEvidence && (
                                            <button
                                                className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium text-[#6558f5] hover:bg-[#f5f4ff]"
                                                onClick={() => setExpandedMemoryId(isExpanded ? null : memory.id)}
                                                type="button"
                                            >
                                                <span>{isExpanded ? "Hide evidence" : `Evidence (${memory.evidence.length})`}</span>
                                                <Icon className={`h-3 w-3 transition-transform ${isExpanded ? "rotate-180" : ""}`} name="chevron-down" />
                                            </button>
                                        )}
                                    </div>

                                    <p className="mt-2.5 text-sm font-medium text-[#303136]">{memory.summary}</p>

                                    {/* Topic Chips */}
                                    {memory.keywords && memory.keywords.length > 0 && (
                                        <div className="mt-2 flex flex-wrap gap-1">
                                            {memory.keywords.slice(0, 5).map((keyword) => (
                                                <span
                                                    className="rounded-md bg-[#f2f2ef] px-2 py-0.5 text-[10px] text-[#69696f]"
                                                    key={keyword}
                                                >
                                                    #{keyword}
                                                </span>
                                            ))}
                                        </div>
                                    )}

                                    {/* Expandable Raw Evidence */}
                                    {isExpanded && hasEvidence && (
                                        <div className="mt-3 space-y-2 rounded-lg border border-[#e8e8e4] bg-[#f9f9f7] p-3 text-xs">
                                            <p className="text-[10px] font-bold uppercase tracking-wider text-[#747579]">
                                                Underlying Private Events
                                            </p>
                                            {memory.evidence.map((item, idx) => (
                                                <div
                                                    className="flex flex-col gap-1 rounded-md bg-white p-2.5 shadow-2xs"
                                                    key={`${item.event.event_id}-${idx}`}
                                                >
                                                    <div className="flex items-center justify-between gap-2">
                                                        <span className="font-semibold text-[#303136]">
                                                            {item.event.title || item.event.event_type.replaceAll("_", " ")}
                                                        </span>
                                                        <span className="text-[10px] text-[#929298]">
                                                            {formatDate(item.event.occurred_at)}
                                                        </span>
                                                    </div>
                                                    {Boolean(item.event.payload.host) && (
                                                        <span className="text-[11px] text-[#717178]">
                                                            Host: <code className="rounded bg-[#f5f5f2] px-1 py-0.5">{String(item.event.payload.host)}</code>
                                                        </span>
                                                    )}
                                                    {Boolean(item.event.payload.repository_name) && (
                                                        <span className="text-[11px] text-[#717178]">
                                                            Repo: <code className="rounded bg-[#f5f5f2] px-1 py-0.5">{String(item.event.payload.repository_name)}</code>
                                                        </span>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </article>
                            );
                        })}
                        {result.memories.length === 0 && (
                            <p className="rounded-xl bg-[#f7f7f4] px-4 py-5 text-sm leading-6 text-[#747579]">
                                No matching local memories were found for this query. Try a broader question or remove a project/goal filter.
                            </p>
                        )}
                    </div>
                </section>
            )}

            {/* Memory Replay / Activity Episodes */}
            <section className="mt-8 rounded-2xl border border-[#e8e8e4] bg-white p-6 shadow-xs">
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#6558f5]">Memory replay</p>
                        <h2 className="mt-1 text-lg font-semibold text-[#27282c]">Activity episodes</h2>
                    </div>
                    <span className="rounded-full bg-[#f5f5f2] px-3 py-1 text-xs font-semibold text-[#67676d]">
                        {sessions.length} episodes
                    </span>
                </div>
                <p className="mt-1 text-xs text-[#85858a]">
                    Mosaic groups your private stream into focused episodes based on time proximity and source context.
                </p>

                <div className="mt-5 space-y-2.5">
                    {sessions.slice(0, 8).map((session) => {
                        const isSelected = sessionDetail?.id === session.id;
                        const focusPercent = Math.round(session.focus_score * 100);
                        const duration = formatDuration(session.started_at, session.ended_at);

                        return (
                            <div
                                className={`rounded-xl border transition-all ${
                                    isSelected
                                        ? "border-[#a8a1ff] bg-[#fbfaff] shadow-sm"
                                        : "border-[#efefec] bg-white hover:border-[#dfdcff] hover:bg-[#fafaff]"
                                }`}
                                key={session.id}
                            >
                                <button
                                    className="flex w-full items-center justify-between gap-3 p-4 text-left"
                                    onClick={() => void openSession(session.id)}
                                    type="button"
                                >
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2">
                                            <p className="truncate text-sm font-semibold text-[#303136]">
                                                {session.summary}
                                            </p>
                                        </div>
                                        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-[#89898e]">
                                            <time>{formatDate(session.started_at)}</time>
                                            <span>·</span>
                                            <span>{duration}</span>
                                            <span>·</span>
                                            <span>{session.event_count} events</span>
                                            {session.goal_hint && (
                                                <>
                                                    <span>·</span>
                                                    <span className="truncate text-[#6558f5]">
                                                        Hint: {session.goal_hint}
                                                    </span>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex shrink-0 items-center gap-3">
                                        <span
                                            className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                                                focusPercent >= 70
                                                    ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                                                    : focusPercent >= 40
                                                      ? "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200"
                                                      : "bg-amber-50 text-amber-700 ring-1 ring-amber-200"
                                            }`}
                                        >
                                            {focusPercent}% focus
                                        </span>
                                        <span className="text-xs font-semibold text-[#6558f5]">
                                            {isSelected ? "Hide" : "Inspect"}
                                        </span>
                                    </div>
                                </button>

                                {/* Session Detail Accordion */}
                                {isSelected && sessionDetail && (
                                    <div className="border-t border-[#f0efff] bg-[#fbfaff] p-4">
                                        <div className="flex items-center justify-between gap-2 border-b border-[#ecebff] pb-3">
                                            <div>
                                                <p className="text-xs font-semibold text-[#303136]">
                                                    Detailed Activity Trace ({sessionDetail.events.length} events)
                                                </p>
                                                <p className="text-[11px] text-[#8e8e94]">
                                                    {formatDate(sessionDetail.started_at)} → {formatDate(sessionDetail.ended_at)}
                                                </p>
                                            </div>
                                            <button
                                                className="rounded-lg px-2 py-1 text-xs font-medium text-[#6558f5] hover:bg-[#f0efff]"
                                                onClick={() => setSessionDetail(null)}
                                                type="button"
                                            >
                                                Close Trace
                                            </button>
                                        </div>

                                        <div className="mt-3 max-h-96 space-y-2 overflow-y-auto pr-1">
                                            {sessionDetail.events.map((event) => (
                                                <div
                                                    className="flex items-center gap-3 rounded-lg border border-[#f0f0ee] bg-white p-3 shadow-2xs"
                                                    key={event.event_id}
                                                >
                                                    {isKnownSource(event.source) ? (
                                                        <SourceMark size="small" source={event.source} />
                                                    ) : (
                                                        <span className="rounded-md bg-[#f5f4ff] px-2 py-1 text-[9px] font-semibold uppercase text-[#5c52dc]">
                                                            {event.source}
                                                        </span>
                                                    )}
                                                    <div className="min-w-0 flex-1">
                                                        <p className="truncate text-xs font-semibold text-[#303136]">
                                                            {event.title || event.event_type.replaceAll("_", " ")}
                                                        </p>
                                                        {Boolean(event.payload?.path) && (
                                                            <p className="truncate text-[11px] text-[#85858a]">
                                                                {String(event.payload.path)}
                                                            </p>
                                                        )}
                                                    </div>
                                                    <time className="shrink-0 text-[10px] text-[#9a9a9f]">
                                                        {formatDate(event.occurred_at)}
                                                    </time>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}

                    {!loading && sessions.length === 0 && (
                        <div className="rounded-xl bg-[#f7f7f4] p-6 text-center text-sm text-[#747579]">
                            <p className="font-medium text-[#303136]">No activity sessions reconstructed yet.</p>
                            <p className="mt-1 text-xs text-[#85858a]">
                                Rebuild context after collecting events from your browser, VS Code, Git, or LeetCode.
                            </p>
                            <button
                                className="mt-4 rounded-xl bg-[#1d1e22] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#34353a]"
                                disabled={isRebuilding}
                                onClick={rebuild}
                                type="button"
                            >
                                Rebuild context now
                            </button>
                        </div>
                    )}
                </div>
            </section>

            {/* Context Pillars Grid */}
            <div className="mt-8 grid gap-5 xl:grid-cols-2">
                {/* Resume Current Context */}
                <section className="flex flex-col justify-between rounded-2xl border border-[#e8e8e4] bg-white p-6 shadow-xs">
                    <div>
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#6558f5]">Resume</p>
                                <h2 className="mt-1 text-lg font-semibold text-[#27282c]">Current context</h2>
                            </div>
                            <span className="grid h-8 w-8 place-items-center rounded-xl bg-[#f5f4ff] text-[#6558f5]">
                                <Icon className="h-4 w-4" name="clock" />
                            </span>
                        </div>

                        {current ? (
                            <div className="mt-5 space-y-3">
                                <div className="rounded-xl border border-[#e9e7ff] bg-[#fafaff] p-4">
                                    <div className="flex items-center gap-2">
                                        <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                                        <p className="text-xs font-bold uppercase tracking-wider text-[#5549db]">Live Session</p>
                                    </div>
                                    <p className="mt-2 text-sm font-semibold text-[#303136]">{current.summary}</p>
                                    <p className="mt-1.5 text-xs text-[#7d7d84]">
                                        {formatDate(current.started_at)} → {formatDate(current.ended_at)} · {formatDuration(current.started_at, current.ended_at)} · {current.event_count} events
                                    </p>
                                    <div className="mt-3 flex items-center gap-2">
                                        <div className="h-2 flex-1 rounded-full bg-[#e8e7fa] overflow-hidden">
                                            <div
                                                className="h-full rounded-full bg-[#6558f5]"
                                                style={{ width: `${Math.round(current.focus_score * 100)}%` }}
                                            />
                                        </div>
                                        <span className="text-[11px] font-bold text-[#5549db]">
                                            {Math.round(current.focus_score * 100)}% focus
                                        </span>
                                    </div>
                                </div>

                                {current.goal_hint && (
                                    <div className="flex items-start gap-2.5 rounded-xl bg-[#f7f7f4] p-3.5 text-xs text-[#525257]">
                                        <Icon className="mt-0.5 h-4 w-4 shrink-0 text-[#6558f5]" name="target" />
                                        <div>
                                            <span className="font-semibold text-[#303136]">Inferred goal:</span>{" "}
                                            <span>{current.goal_hint}</span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="mt-5 rounded-xl bg-[#f7f7f4] p-5 text-center text-sm text-[#85858a]">
                                <Icon className="mx-auto h-6 w-6 text-[#9a9a9f]" name="clock" />
                                <p className="mt-2 font-medium text-[#4c4c51]">No live session reconstructed yet</p>
                                <p className="mt-1 text-xs">
                                    Continue your usual work, and Mosaic will cluster upcoming events into an active episode.
                                </p>
                            </div>
                        )}
                    </div>

                    <div className="mt-5 border-t border-[#f0f0ed] pt-4">
                        <button
                            className="w-full rounded-xl bg-[#f7f7f4] py-2.5 text-xs font-semibold text-[#4c4c51] transition hover:bg-[#eef0fc] hover:text-[#5146d7]"
                            onClick={() => {
                                setQuery("What was I working on recently?");
                                void executeSearch("What was I working on recently?", selectedProjectId, selectedGoalId);
                            }}
                            type="button"
                        >
                            Ask Mosaic to summarize recent context
                        </button>
                    </div>
                </section>

                {/* Where Your Work Lives (Projects) */}
                <section className="flex flex-col justify-between rounded-2xl border border-[#e8e8e4] bg-white p-6 shadow-xs">
                    <div>
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#6558f5]">Projects</p>
                                <h2 className="mt-1 text-lg font-semibold text-[#27282c]">Where your work lives</h2>
                            </div>
                            <span className="rounded-full bg-[#f5f5f2] px-3 py-1 text-xs font-semibold text-[#67676d]">
                                {projects.length}
                            </span>
                        </div>
                        <p className="mt-1 text-xs text-[#85858a]">
                            Workspaces and repositories identified from local file and git activity.
                        </p>

                        <div className="mt-5 space-y-2">
                            {projects.slice(0, 5).map((project) => {
                                const isSelected = selectedProjectId === project.id;
                                return (
                                    <div
                                        className={`flex items-center justify-between gap-3 rounded-xl border p-3 transition ${
                                            isSelected
                                                ? "border-[#a8a1ff] bg-[#f9f8ff]"
                                                : "border-[#f0f0ee] bg-[#f7f7f4] hover:border-[#dfdcff] hover:bg-white"
                                        }`}
                                        key={project.id}
                                    >
                                        <div className="min-w-0 flex-1">
                                            <div className="flex items-center gap-2">
                                                <span className="grid h-6 w-6 place-items-center rounded-md bg-[#eef0fc] text-xs font-bold text-[#5549db]">
                                                    {project.name.charAt(0).toUpperCase()}
                                                </span>
                                                <p className="truncate text-sm font-semibold text-[#303136]">{project.name}</p>
                                            </div>
                                            <p className="mt-1 truncate text-xs text-[#85858a]">
                                                {project.repository || project.workspace_name || project.slug}
                                            </p>
                                        </div>
                                        <button
                                            className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                                                isSelected
                                                    ? "bg-[#6558f5] text-white"
                                                    : "bg-white text-[#6558f5] ring-1 ring-[#e8e8e4] hover:bg-[#f5f4ff]"
                                            }`}
                                            onClick={() => filterByProject(project.id)}
                                            type="button"
                                        >
                                            {isSelected ? "Filtered" : "Filter"}
                                        </button>
                                    </div>
                                );
                            })}
                            {!loading && projects.length === 0 && (
                                <p className="rounded-xl bg-[#f7f7f4] p-4 text-xs leading-5 text-[#747579]">
                                    Projects appear automatically when Mosaic sees Git commits or workspace events.
                                </p>
                            )}
                        </div>
                    </div>
                </section>

                {/* What You Are Trying to Accomplish (Goals) */}
                <section className="flex flex-col justify-between rounded-2xl border border-[#e8e8e4] bg-white p-6 shadow-xs">
                    <div>
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#6558f5]">Goals</p>
                                <h2 className="mt-1 text-lg font-semibold text-[#27282c]">What you are trying to accomplish</h2>
                            </div>
                            <div className="flex items-center gap-1.5 text-xs text-[#85858a]">
                                <span className="font-semibold text-emerald-700">{completedGoalsCount} done</span>
                                <span>·</span>
                                <span className="font-semibold text-[#1d1e22]">{activeGoalsCount} active</span>
                            </div>
                        </div>

                        {/* Add Goal Form */}
                        <form className="mt-4 flex gap-2" onSubmit={addGoal}>
                            <input
                                className="min-w-0 flex-1 rounded-xl bg-[#f7f7f4] px-3.5 py-2.5 text-xs text-[#303136] outline-none placeholder:text-[#929297] focus:ring-2 focus:ring-[#c9c4ff]"
                                onChange={(event) => setGoalTitle(event.target.value)}
                                placeholder="e.g. Optimize local vector retrieval"
                                value={goalTitle}
                            />
                            <button
                                className="rounded-xl bg-[#1d1e22] px-4 py-2.5 text-xs font-semibold text-white shadow-sm transition hover:bg-[#34353a] disabled:cursor-wait disabled:opacity-60"
                                disabled={isCreatingGoal || goalTitle.trim().length < 2}
                                type="submit"
                            >
                                {isCreatingGoal ? "Adding…" : "Add Goal"}
                            </button>
                        </form>

                        {/* Goals List with Toggleable Status */}
                        <div className="mt-4 space-y-2">
                            {goals.slice(0, 6).map((goal) => {
                                const isCompleted = goal.status === "completed";
                                const isSelected = selectedGoalId === goal.id;
                                return (
                                    <div
                                        className={`flex items-center justify-between gap-3 rounded-xl border p-3 transition ${
                                            isSelected
                                                ? "border-[#a8a1ff] bg-[#fbfaff]"
                                                : "border-[#f0f0ee] bg-[#f7f7f4] hover:bg-white hover:border-[#dfdcff]"
                                        }`}
                                        key={goal.id}
                                    >
                                        <div className="flex min-w-0 flex-1 items-center gap-3">
                                            <button
                                                aria-label={isCompleted ? "Mark goal as active" : "Mark goal as completed"}
                                                className={`grid h-5 w-5 shrink-0 place-items-center rounded-md border transition ${
                                                    isCompleted
                                                        ? "border-emerald-600 bg-emerald-600 text-white"
                                                        : "border-[#c4c4be] bg-white text-transparent hover:border-[#6558f5]"
                                                }`}
                                                onClick={() => void toggleGoal(goal)}
                                                type="button"
                                            >
                                                <Icon className="h-3.5 w-3.5" name="check" />
                                            </button>
                                            <span
                                                className={`truncate text-xs font-medium ${
                                                    isCompleted ? "text-[#8e8e94] line-through" : "text-[#303136]"
                                                }`}
                                            >
                                                {goal.title}
                                            </span>
                                        </div>
                                        <div className="flex shrink-0 items-center gap-2">
                                            <button
                                                className={`rounded-lg px-2 py-0.5 text-[10px] font-semibold transition ${
                                                    isSelected
                                                        ? "bg-[#6558f5] text-white"
                                                        : "bg-white text-[#747579] ring-1 ring-[#e8e8e4] hover:text-[#5146d7]"
                                                }`}
                                                onClick={() => filterByGoal(goal.id)}
                                                type="button"
                                            >
                                                {isSelected ? "Filtered" : "Filter"}
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                            {!loading && goals.length === 0 && (
                                <p className="rounded-xl bg-[#f7f7f4] p-4 text-xs leading-5 text-[#747579]">
                                    Add your active goals to help Mosaic connect relevant events and guide context retrieval.
                                </p>
                            )}
                        </div>
                    </div>
                </section>

                {/* Exposure → Practice → Implementation (Learning Graph) */}
                <section className="flex flex-col justify-between rounded-2xl border border-[#e8e8e4] bg-white p-6 shadow-xs">
                    <div>
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#6558f5]">Learning graph</p>
                                <h2 className="mt-1 text-lg font-semibold text-[#27282c]">Exposure → practice → implementation</h2>
                            </div>
                            <span className="grid h-8 w-8 place-items-center rounded-xl bg-[#f5f4ff] text-[#6558f5]">
                                <Icon className="h-4 w-4" name="sparkles" />
                            </span>
                        </div>
                        <p className="mt-1 text-xs text-[#85858a]">
                            Concepts tracked from what you read, practiced, and implemented in code.
                        </p>

                        {learning && (
                            <>
                                <div className="mt-4 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                                    {learning.concepts.slice(0, 6).map((concept) => (
                                        <button
                                            className="group rounded-xl border border-[#efefec] bg-[#fafaf8] p-3 text-left transition hover:border-[#dfdcff] hover:bg-white hover:shadow-2xs"
                                            key={concept.concept}
                                            onClick={() => {
                                                setQuery(concept.concept);
                                                void executeSearch(concept.concept, selectedProjectId, selectedGoalId);
                                            }}
                                            title={`Search context for ${concept.concept}`}
                                            type="button"
                                        >
                                            <div className="flex items-center justify-between">
                                                <p className="truncate text-xs font-bold text-[#303136] group-hover:text-[#5549db]">
                                                    {concept.concept}
                                                </p>
                                                <Icon className="h-3 w-3 text-[#b4b4ba] opacity-0 transition group-hover:opacity-100 group-hover:text-[#5549db]" name="search" />
                                            </div>
                                            <div className="mt-2 space-y-1 text-[10px] text-[#85858a]">
                                                <div className="flex justify-between">
                                                    <span>Exposure</span>
                                                    <span className="font-semibold text-[#4c4c51]">{concept.exposure_count}</span>
                                                </div>
                                                <div className="flex justify-between">
                                                    <span>Practice</span>
                                                    <span className="font-semibold text-amber-700">{concept.practice_count}</span>
                                                </div>
                                                <div className="flex justify-between">
                                                    <span>Build</span>
                                                    <span className="font-semibold text-indigo-700">{concept.implementation_count}</span>
                                                </div>
                                            </div>
                                        </button>
                                    ))}
                                </div>

                                {learning.suggestions.length > 0 && (
                                    <div className="mt-4 flex items-start gap-2.5 rounded-xl border border-[#dfdcff] bg-[#f7f6ff] p-3 text-xs leading-5 text-[#5146d7]">
                                        <Icon className="mt-0.5 h-4 w-4 shrink-0 text-[#6558f5]" name="sparkles" />
                                        <p>{learning.suggestions[0]}</p>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </section>
            </div>

            {/* Privacy Ledger */}
            <section className="mt-8 rounded-2xl border border-[#e8e8e4] bg-white p-6 shadow-xs">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <div className="flex items-center gap-2">
                            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#6558f5]">Privacy ledger</p>
                            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-emerald-200">
                                Zero-Leak Protected
                            </span>
                        </div>
                        <h2 className="mt-1 text-lg font-semibold text-[#27282c]">What left this machine?</h2>
                    </div>
                    <span className="text-xs text-[#85858a]">External network actions recorded with byte-level fidelity</span>
                </div>

                <div className="mt-5 overflow-x-auto">
                    <table className="w-full min-w-[720px] text-left text-xs">
                        <thead className="border-b border-[#efefec] text-[#8a8a90]">
                            <tr>
                                <th className="px-3 py-2.5 font-semibold">Time</th>
                                <th className="px-3 py-2.5 font-semibold">Direction</th>
                                <th className="px-3 py-2.5 font-semibold">Provider</th>
                                <th className="px-3 py-2.5 font-semibold">Action</th>
                                <th className="px-3 py-2.5 font-semibold">Data Size</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[#f1f1ef]">
                            {ledger.slice(0, 12).map((row, index) => (
                                <tr className="hover:bg-[#fafaf8]" key={`${row.occurred_at}-${index}`}>
                                    <td className="px-3 py-3 text-[#737379]">{formatDate(row.occurred_at)}</td>
                                    <td className="px-3 py-3 font-semibold">
                                        <span
                                            className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-bold uppercase ${
                                                row.direction === "outbound"
                                                    ? "bg-amber-50 text-amber-700"
                                                    : "bg-emerald-50 text-emerald-700"
                                            }`}
                                        >
                                            {row.direction}
                                        </span>
                                    </td>
                                    <td className="px-3 py-3 font-medium text-[#303136]">{row.provider}</td>
                                    <td className="px-3 py-3 text-[#525258]">{row.action}</td>
                                    <td className="px-3 py-3 font-mono text-xs text-[#525258]">
                                        {formatBytes(row.bytes_count)}
                                    </td>
                                </tr>
                            ))}
                            {!loading && ledger.length === 0 && (
                                <tr>
                                    <td className="px-3 py-6 text-center text-[#747579]" colSpan={5}>
                                        <div className="flex flex-col items-center justify-center">
                                            <Icon className="h-6 w-6 text-emerald-600" name="shield" />
                                            <p className="mt-2 font-medium text-[#303136]">No external egress recorded</p>
                                            <p className="text-xs text-[#85858a]">All context reconstruction and memory search operations are executed entirely on-device.</p>
                                        </div>
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            {/* Architecture Footer Note */}
            <div className="mt-8 rounded-2xl border border-[#e8e8e4] bg-[#f7f7f4] p-5 text-xs leading-6 text-[#727278]">
                <strong className="text-[#303136]">Privacy Guarantees:</strong> Mosaic Context OS reconstructs work sessions, projects, and learning graphs from approved timeline metadata only. Editor code buffers and private document contents never leave this device.
            </div>
        </section>
    );
}
