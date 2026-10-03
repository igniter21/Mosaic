"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon } from "@/components/icons";
import { SourceMark, sourceLabel } from "@/components/source-mark";
import { getEvents, getSources } from "@/lib/api";
import type { MemoryEvent, SourceSetting } from "@/lib/types";

function formatEventTime(value: string) {
    return new Intl.DateTimeFormat("en-IN", {
        day: "numeric",
        month: "short",
        hour: "numeric",
        minute: "2-digit",
    }).format(new Date(value));
}

export default function DashboardPage() {
    const [events, setEvents] = useState<MemoryEvent[]>([]);
    const [sources, setSources] = useState<SourceSetting[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [hasConnectionError, setHasConnectionError] = useState(false);

    useEffect(() => {
        async function loadOverview() {
            try {
                const [eventResults, sourceResults] = await Promise.all([
                    getEvents(),
                    getSources(),
                ]);
                setEvents(eventResults);
                setSources(sourceResults);
            } catch {
                setHasConnectionError(true);
            } finally {
                setIsLoading(false);
            }
        }

        void loadOverview();
    }, []);

    const enabledSources = sources.filter((source) => source.enabled).length;

    return (
        <section>
            <div className="grid gap-8 border-b border-[#e8e8e4] pb-10 lg:grid-cols-[minmax(0,1fr)_14rem] lg:items-end">
                <div className="max-w-3xl">
                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#6558f5]">
                        Your private activity record
                    </p>
                    <h1 className="mt-4 text-4xl font-semibold tracking-[-0.055em] text-[#1d1e22] sm:text-5xl">
                        A calmer way to remember what mattered.
                    </h1>
                    <p className="mt-5 max-w-2xl text-[15px] leading-7 text-[#747579]">
                        Mosaic keeps an evidence-based timeline of the activity you
                        choose to collect—stored on this device, under your control.
                    </p>
                </div>

                <div className="rounded-2xl border border-[#dfdcff] bg-[#eeedff] p-4">
                    <div className="flex items-center gap-2 text-xs font-semibold text-[#4d43cb]">
                        <Icon className="h-4 w-4" name="lock" />
                        Private by default
                    </div>
                    <p className="mt-2 text-xs leading-5 text-[#6861a7]">
                        No account, cloud sync, or collector starts without your approval.
                    </p>
                </div>
            </div>

            {hasConnectionError && (
                <div className="mt-6 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    <Icon className="mt-0.5 h-4 w-4 shrink-0" name="bolt" />
                    <p>
                        Mosaic can&apos;t reach the local API yet. Start it to see your
                        live activity and source status.
                    </p>
                </div>
            )}

            <div className="mt-8 grid gap-3 sm:grid-cols-3">
                <MetricCard
                    detail="approved events in your latest view"
                    isLoading={isLoading}
                    label="Activity recorded"
                    value={events.length.toString()}
                />
                <MetricCard
                    detail="collectors currently allowed to send data"
                    isLoading={isLoading}
                    label="Sources enabled"
                    value={enabledSources.toString()}
                />
                <MetricCard
                    detail="your data lives in local SQLite storage"
                    isLoading={isLoading}
                    label="Storage mode"
                    value="On this device"
                />
            </div>

            <div className="mt-10 grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(17rem,0.85fr)]">
                <section className="rounded-2xl border border-[#e8e8e4] bg-white">
                    <div className="flex items-center justify-between border-b border-[#efefec] px-5 py-4 sm:px-6">
                        <div>
                            <h2 className="font-semibold tracking-[-0.025em] text-[#27282c]">
                                Recent activity
                            </h2>
                            <p className="mt-1 text-xs text-[#85858a]">
                                The latest evidence from your enabled sources
                            </p>
                        </div>
                        <Link
                            className="inline-flex items-center gap-1 text-xs font-semibold text-[#5549db] transition hover:text-[#352aa9]"
                            href="/timeline"
                        >
                            View timeline
                            <Icon className="h-3.5 w-3.5" name="arrow-right" />
                        </Link>
                    </div>

                    <div className="divide-y divide-[#f0f0ed]">
                        {isLoading && <ActivitySkeleton />}
                        {!isLoading && events.length === 0 && (
                            <div className="px-6 py-12 text-center">
                                <span className="mx-auto grid h-10 w-10 place-items-center rounded-xl bg-[#f5f4ff] text-[#6558f5]">
                                    <Icon className="h-5 w-5" name="sparkles" />
                                </span>
                                <p className="mt-4 text-sm font-medium text-[#333439]">
                                    Nothing collected yet
                                </p>
                                <p className="mx-auto mt-1 max-w-xs text-xs leading-5 text-[#85858a]">
                                    Enable a source when you&apos;re ready. Mosaic will only
                                    record activity you&apos;ve opted into.
                                </p>
                                <Link
                                    className="mt-4 inline-flex text-xs font-semibold text-[#5549db]"
                                    href="/sources"
                                >
                                    Configure sources
                                </Link>
                            </div>
                        )}
                        {!isLoading &&
                            events.slice(0, 5).map((event) => (
                                <article
                                    className="flex items-center gap-3 px-5 py-4 sm:px-6"
                                    key={event.event_id}
                                >
                                    <SourceMark size="small" source={event.source} />
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <p className="truncate text-sm font-medium text-[#303136]">
                                                {event.title ?? event.event_type}
                                            </p>
                                            {(event.visit_count ?? 1) > 1 && (
                                                <span
                                                    className="shrink-0 inline-flex items-center rounded-full bg-[#f0efff] px-1.5 py-0.5 text-[10px] font-bold text-[#5549db]"
                                                    title={`Seen ${event.visit_count} times`}
                                                >
                                                    ×{event.visit_count}
                                                </span>
                                            )}
                                        </div>
                                        <p className="mt-1 text-xs text-[#89898e]">
                                            {sourceLabel(event.source)} · {event.event_type.replaceAll("_", " ")}
                                        </p>
                                    </div>
                                    <time className="shrink-0 text-right text-xs text-[#89898e]">
                                        {formatEventTime(event.occurred_at)}
                                    </time>
                                </article>
                            ))}
                    </div>
                </section>

                <aside className="rounded-2xl bg-[#1d1e22] p-6 text-white">
                    <span className="grid h-10 w-10 place-items-center rounded-xl bg-white/10 text-[#d7d2ff]">
                        <Icon className="h-5 w-5" name="shield" />
                    </span>
                    <h2 className="mt-10 text-xl font-semibold tracking-[-0.04em]">
                        Your memory has an off switch.
                    </h2>
                    <p className="mt-3 text-sm leading-6 text-[#c5c5c9]">
                        Disable a source, remove one event, or erase every locally
                        stored record whenever you need to.
                    </p>
                    <Link
                        className="mt-8 inline-flex items-center gap-2 text-sm font-semibold text-white transition hover:text-[#d7d2ff]"
                        href="/privacy"
                    >
                        Review privacy controls
                        <Icon className="h-4 w-4" name="arrow-right" />
                    </Link>
                </aside>
            </div>
        </section>
    );
}

function MetricCard({
    label,
    value,
    detail,
    isLoading,
}: {
    label: string;
    value: string;
    detail: string;
    isLoading: boolean;
}) {
    return (
        <article className="rounded-2xl border border-[#e8e8e4] bg-white p-5">
            <p className="text-xs font-medium text-[#85858a]">{label}</p>
            {isLoading ? (
                <div className="mt-3 h-7 w-20 animate-pulse rounded bg-[#f0f0ed]" />
            ) : (
                <p className="mt-2 text-xl font-semibold tracking-[-0.035em] text-[#27282c]">
                    {value}
                </p>
            )}
            <p className="mt-2 text-xs leading-5 text-[#97979b]">{detail}</p>
        </article>
    );
}

function ActivitySkeleton() {
    return (
        <div className="space-y-4 px-6 py-5">
            {[0, 1, 2].map((item) => (
                <div className="flex items-center gap-3" key={item}>
                    <span className="h-8 w-8 animate-pulse rounded-xl bg-[#f0f0ed]" />
                    <span className="h-8 flex-1 animate-pulse rounded-lg bg-[#f5f5f2]" />
                    <span className="h-3 w-14 animate-pulse rounded bg-[#f0f0ed]" />
                </div>
            ))}
        </div>
    );
}
