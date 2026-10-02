"use client";

import { useEffect, useState } from "react";

import { Icon } from "@/components/icons";
import { PageHeader } from "@/components/page-header";
import { SourceMark, sourceLabel } from "@/components/source-mark";
import { getSources, setSourceEnabled } from "@/lib/api";
import type { Source, SourceSetting } from "@/lib/types";

const sourceDetails: Record<Source, { description: string; collects: string }> = {
    browser: {
        description: "Keep a record of pages you intentionally browse.",
        collects: "Host, page path, and title",
    },
    youtube: {
        description: "Remember videos you watched while learning or researching.",
        collects: "Video ID and page title",
    },
    leetcode: {
        description: "Track the problems you open while practising.",
        collects: "Problem slug and title",
    },
    vscode: {
        description: "Capture high-level coding activity from your editor.",
        collects: "Relative filename and language",
    },
    document: {
        description: "Index the document metadata you explicitly choose to collect.",
        collects: "Name, type, size, and modified time",
    },
};

export default function SourcesPage() {
    const [sources, setSources] = useState<SourceSetting[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [updatingSource, setUpdatingSource] = useState<Source | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        async function loadSources() {
            try {
                setSources(await getSources());
            } catch (caughtError) {
                setError(
                    caughtError instanceof Error
                        ? caughtError.message
                        : "Could not load source settings.",
                );
            } finally {
                setIsLoading(false);
            }
        }

        void loadSources();
    }, []);

    async function toggleSource(setting: SourceSetting) {
        setUpdatingSource(setting.source);
        setError(null);

        try {
            const updated = await setSourceEnabled(
                setting.source,
                !setting.enabled,
            );

            setSources((current) =>
                current.map((source) =>
                    source.source === updated.source ? updated : source,
                ),
            );
        } catch (caughtError) {
            setError(
                caughtError instanceof Error
                    ? caughtError.message
                    : "Could not update this source.",
            );
        } finally {
            setUpdatingSource(null);
        }
    }

    return (
        <section>
            <PageHeader
                description="Each source is off until you turn it on. Approved metadata is routed through its matching local model, then stored in one shared evidence and retrieval pipeline."
                eyebrow="Collection settings"
                title="Data sources"
            />

            <div className="mt-7 flex items-start gap-3 rounded-2xl border border-[#dfdcff] bg-[#f7f6ff] px-4 py-3.5">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-[#e9e7ff] text-[#594cde]">
                    <Icon className="h-4 w-4" name="shield" />
                </span>
                <p className="pt-0.5 text-sm leading-5 text-[#5d5794]">
                    <span className="font-semibold">You choose the scope.</span> You can
                    disable a source at any time. Mosaic rejects new events from disabled
                    sources.
                </p>
            </div>

            {error && (
                <p className="mt-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                    {error}
                </p>
            )}

            <div className="mt-7 grid gap-4 md:grid-cols-2">
                {isLoading && <SourceSkeleton />}
                {!isLoading &&
                    sources.map((setting) => {
                        const details = sourceDetails[setting.source];
                        const isUpdating = updatingSource === setting.source;

                        return (
                            <article
                                className="rounded-2xl border border-[#e8e8e4] bg-white p-5 transition hover:border-[#dad9d4]"
                                key={setting.source}
                            >
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex items-center gap-3">
                                        <SourceMark source={setting.source} />
                                        <div>
                                            <h2 className="text-sm font-semibold text-[#2c2d31]">
                                                {sourceLabel(setting.source)}
                                            </h2>
                                            <p className="mt-1 text-xs font-medium text-[#86868b]">
                                                {setting.enabled ? "Collection allowed" : "Collection paused"}
                                            </p>
                                        </div>
                                    </div>
                                    <button
                                        aria-checked={setting.enabled}
                                        aria-label={`${setting.enabled ? "Disable" : "Enable"} ${sourceLabel(setting.source)}`}
                                        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition disabled:cursor-wait disabled:opacity-60 ${
                                            setting.enabled ? "bg-[#6558f5]" : "bg-[#ddddda]"
                                        }`}
                                        disabled={isUpdating}
                                        onClick={() => void toggleSource(setting)}
                                        role="switch"
                                    >
                                        <span
                                            className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition ${
                                                setting.enabled ? "translate-x-6" : "translate-x-1"
                                            }`}
                                        />
                                    </button>
                                </div>

                                    <p className="mt-5 text-sm leading-6 text-[#6f7075]">
                                        {details.description}
                                    </p>
                                    <div className="mt-4 rounded-xl bg-[#f7f6ff] px-3 py-2.5">
                                        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#8178c8]">
                                            Processing route
                                        </p>
                                        <p className="mt-1 text-xs font-medium text-[#514b88]">
                                            {setting.model_label} · {setting.modality}
                                        </p>
                                    </div>
                                    <div className="mt-5 border-t border-[#f0f0ed] pt-4">
                                    <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#a0a0a4]">
                                        What it collects
                                    </p>
                                    <p className="mt-1.5 text-xs text-[#65666b]">{details.collects}</p>
                                </div>
                            </article>
                        );
                    })}
            </div>
        </section>
    );
}

function SourceSkeleton() {
    return (
        <>
            {[0, 1, 2, 3].map((item) => (
                <div className="h-60 animate-pulse rounded-2xl border border-[#e8e8e4] bg-white" key={item} />
            ))}
        </>
    );
}
