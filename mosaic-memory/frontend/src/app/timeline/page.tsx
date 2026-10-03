"use client";

import { useEffect, useState } from "react";

import { Icon } from "@/components/icons";
import { PageHeader } from "@/components/page-header";
import { SourceMark, sourceLabel } from "@/components/source-mark";
import { deleteEvent, getEvents } from "@/lib/api";
import type { MemoryEvent, Source } from "@/lib/types";

const sourceOptions: { value: Source | "all"; label: string }[] = [
    { value: "all", label: "All sources" },
    { value: "browser", label: "Browser" },
    { value: "youtube", label: "YouTube" },
    { value: "leetcode", label: "LeetCode" },
    { value: "vscode", label: "VS Code" },
    { value: "document", label: "Documents" },
    { value: "git", label: "Git" },
];

function formatDate(value: string) {
    return new Intl.DateTimeFormat("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(new Date(value));
}

function timeAgo(value: string) {
    const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000);
    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
    return formatDate(value);
}

/** An event is "recent" if its latest occurrence was in the last 2 hours. */
function isRecent(event: MemoryEvent): boolean {
    return Date.now() - new Date(event.occurred_at).getTime() < 2 * 60 * 60 * 1000;
}

export default function TimelinePage() {
    const [deletingEventId, setDeletingEventId] = useState<string | null>(null);
    const [events, setEvents] = useState<MemoryEvent[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [query, setQuery] = useState("");
    const [selectedSource, setSelectedSource] = useState<Source | "all">("all");

    async function removeEvent(event: MemoryEvent) {
        const approved = window.confirm(
            `Delete "${event.title ?? event.event_type}" permanently?`,
        );

        if (!approved) return;

        setDeletingEventId(event.event_id);
        setError(null);

        try {
            await deleteEvent(event.event_id);
            setEvents((current) =>
                current.filter((item) => item.event_id !== event.event_id),
            );
        } catch (caughtError) {
            setError(
                caughtError instanceof Error
                    ? caughtError.message
                    : "Could not delete the event.",
            );
        } finally {
            setDeletingEventId(null);
        }
    }

    useEffect(() => {
        async function loadTimeline() {
            setIsLoading(true);
            setError(null);

            try {
                const result = await getEvents(
                    selectedSource === "all" ? undefined : selectedSource,
                );
                setEvents(result);
            } catch (caughtError) {
                setError(
                    caughtError instanceof Error
                        ? caughtError.message
                        : "Could not load events.",
                );
            } finally {
                setIsLoading(false);
            }
        }

        void loadTimeline();
    }, [selectedSource]);

    const visibleEvents = events.filter((event) => {
        const searchableText = [event.title, event.event_type, event.source]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();

        return searchableText.includes(query.trim().toLowerCase());
    });

    // Split into recent (highlighted) vs older
    const recentEvents = visibleEvents.filter(isRecent);
    const olderEvents = visibleEvents.filter((e) => !isRecent(e));

    return (
        <section>
            <PageHeader
                description="A chronological record of activity from sources you have explicitly approved. Newest first. Repeated visits are automatically consolidated."
                eyebrow="Activity record"
                title="Timeline"
            />

            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                <label className="relative flex-1">
                    <span className="sr-only">Search your timeline</span>
                    <Icon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#949499]" name="search" />
                    <input
                        className="h-11 w-full rounded-xl border border-[#e4e4e0] bg-white pl-10 pr-4 text-sm text-[#303136] outline-none transition placeholder:text-[#a1a1a5] focus:border-[#a8a1ff]"
                        onChange={(event) => setQuery(event.target.value)}
                        placeholder="Search titles or activity types"
                        value={query}
                    />
                </label>
                <label className="relative">
                    <span className="sr-only">Filter by source</span>
                    <select
                        className="h-11 appearance-none rounded-xl border border-[#e4e4e0] bg-white py-0 pl-4 pr-10 text-sm font-medium text-[#4a4b4f] outline-none transition focus:border-[#a8a1ff]"
                        onChange={(event) =>
                            setSelectedSource(event.target.value as Source | "all")
                        }
                        value={selectedSource}
                    >
                        {sourceOptions.map((source) => (
                            <option key={source.value} value={source.value}>
                                {source.label}
                            </option>
                        ))}
                    </select>
                    <Icon className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#77777b]" name="chevron-down" />
                </label>
            </div>

            {error && (
                <div className="mt-6 flex gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                    <Icon className="mt-0.5 h-4 w-4 shrink-0" name="bolt" />
                    {error}
                </div>
            )}

            <div className="mt-6 overflow-hidden rounded-2xl border border-[#e8e8e4] bg-white">
                <div className="flex items-center justify-between border-b border-[#efefec] px-5 py-4 sm:px-6">
                    <p className="text-sm font-medium text-[#414247]">
                        {isLoading
                            ? "Loading activity"
                            : `${visibleEvents.length} ${visibleEvents.length === 1 ? "event" : "events"}`}
                    </p>
                    <div className="flex items-center gap-3">
                        {recentEvents.length > 0 && !isLoading && (
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f0efff] px-2.5 py-0.5 text-[10px] font-semibold text-[#5549db]">
                                <span className="h-1.5 w-1.5 rounded-full bg-[#6558f5] animate-pulse" />
                                {recentEvents.length} recent
                            </span>
                        )}
                        <p className="text-xs text-[#929297]">Deduplicated · Local only</p>
                    </div>
                </div>

                {isLoading && <TimelineSkeleton />}

                {!isLoading && !error && events.length === 0 && (
                    <EmptyTimeline message="No approved activity has arrived from this source yet." />
                )}

                {!isLoading && !error && events.length > 0 && visibleEvents.length === 0 && (
                    <EmptyTimeline message="No activity matches that search. Try another title or event type." />
                )}

                {/* Recent Events Section */}
                {!isLoading && recentEvents.length > 0 && (
                    <>
                        <div className="border-b border-[#f0f0ed] bg-[#fafaff] px-5 py-2 sm:px-6">
                            <p className="text-[10px] font-bold uppercase tracking-widest text-[#6558f5]">Recent activity</p>
                        </div>
                        {recentEvents.map((event) => (
                            <TimelineRow
                                key={event.event_id}
                                event={event}
                                isRecent={true}
                                deletingEventId={deletingEventId}
                                onDelete={removeEvent}
                            />
                        ))}
                    </>
                )}

                {/* Older Events Section */}
                {!isLoading && olderEvents.length > 0 && (
                    <>
                        {recentEvents.length > 0 && (
                            <div className="border-b border-[#f0f0ed] bg-[#f7f7f4] px-5 py-2 sm:px-6">
                                <p className="text-[10px] font-bold uppercase tracking-widest text-[#929297]">Earlier</p>
                            </div>
                        )}
                        {olderEvents.map((event) => (
                            <TimelineRow
                                key={event.event_id}
                                event={event}
                                isRecent={false}
                                deletingEventId={deletingEventId}
                                onDelete={removeEvent}
                            />
                        ))}
                    </>
                )}
            </div>
        </section>
    );
}

function TimelineRow({
    event,
    isRecent: recent,
    deletingEventId,
    onDelete,
}: {
    event: MemoryEvent;
    isRecent: boolean;
    deletingEventId: string | null;
    onDelete: (event: MemoryEvent) => void;
}) {
    const hasMultipleVisits = (event.visit_count ?? 1) > 1;
    return (
        <article
            className={`group flex gap-3 border-b border-[#f0f0ed] px-5 py-5 last:border-0 sm:items-center sm:px-6 transition-colors ${
                recent ? "bg-white" : "bg-white/70"
            }`}
            key={event.event_id}
        >
            <SourceMark source={event.source} />
            <div className="min-w-0 flex-1">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                    <div className="flex items-center gap-2 min-w-0">
                        <h2 className="truncate text-sm font-semibold text-[#303136]">
                            {event.title ?? event.event_type.replaceAll("_", " ")}
                        </h2>
                        {hasMultipleVisits && (
                            <span
                                className="shrink-0 inline-flex items-center gap-1 rounded-full bg-[#f0efff] px-2 py-0.5 text-[10px] font-bold text-[#5549db]"
                                title={`Seen ${event.visit_count} times${event.first_seen_at ? ` since ${formatDate(event.first_seen_at)}` : ""}`}
                            >
                                <Icon className="h-2.5 w-2.5" name="refresh" />
                                ×{event.visit_count}
                            </span>
                        )}
                        {recent && (
                            <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-[#6558f5]" title="Recent activity" />
                        )}
                    </div>
                    <time className="shrink-0 text-xs text-[#89898e]">
                        {recent ? timeAgo(event.occurred_at) : formatDate(event.occurred_at)}
                    </time>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className="text-xs text-[#77777b]">
                        {sourceLabel(event.source)} · {event.event_type.replaceAll("_", " ")}
                    </span>
                    <span className="h-1 w-1 rounded-full bg-[#c8c8c9]" />
                    <span className="rounded-md bg-[#f5f5f3] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#77777b]">
                        {event.retention_class.replaceAll("_", " ")}
                    </span>
                    {hasMultipleVisits && event.first_seen_at && (
                        <>
                            <span className="h-1 w-1 rounded-full bg-[#c8c8c9]" />
                            <span className="text-[10px] text-[#a0a0a5]">
                                First: {timeAgo(event.first_seen_at)}
                            </span>
                        </>
                    )}
                </div>
            </div>
            <button
                aria-label={`Delete ${event.title ?? event.event_type}`}
                className="ml-1 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[#a0a0a4] transition hover:bg-red-50 hover:text-red-600 disabled:cursor-wait disabled:opacity-60 sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100"
                disabled={deletingEventId === event.event_id}
                onClick={() => void onDelete(event)}
                title="Delete event"
            >
                {deletingEventId === event.event_id ? (
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                ) : (
                    <Icon className="h-4 w-4" name="trash" />
                )}
            </button>
        </article>
    );
}

function EmptyTimeline({ message }: { message: string }) {
    return (
        <div className="px-6 py-14 text-center">
            <span className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-[#f5f4ff] text-[#6558f5]">
                <Icon className="h-5 w-5" name="clock" />
            </span>
            <p className="mt-4 text-sm font-medium text-[#393a3e]">Your timeline is quiet</p>
            <p className="mx-auto mt-1 max-w-sm text-xs leading-5 text-[#8a8a8f]">{message}</p>
        </div>
    );
}

function TimelineSkeleton() {
    return (
        <div className="divide-y divide-[#f0f0ed]">
            {[0, 1, 2, 3].map((item) => (
                <div className="flex items-center gap-3 px-6 py-5" key={item}>
                    <span className="h-10 w-10 animate-pulse rounded-xl bg-[#f0f0ed]" />
                    <span className="h-9 flex-1 animate-pulse rounded-lg bg-[#f5f5f2]" />
                    <span className="h-3 w-24 animate-pulse rounded bg-[#f0f0ed]" />
                </div>
            ))}
        </div>
    );
}
