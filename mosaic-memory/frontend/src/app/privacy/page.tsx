"use client";

import { FormEvent, useState } from "react";

import { EraseAllMemory } from "@/components/erase-all-memory";
import { Icon } from "@/components/icons";
import { PageHeader } from "@/components/page-header";
import { deleteEvents } from "@/lib/api";
import type { Source } from "@/lib/types";

const sourceOptions: Source[] = [
    "browser",
    "youtube",
    "leetcode",
    "vscode",
    "document",
    "git",
];

export default function PrivacyPage() {
    const [source, setSource] = useState<Source | "">("");
    const [fromTime, setFromTime] = useState("");
    const [toTime, setToTime] = useState("");
    const [message, setMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    async function handleDelete(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setError(null);
        setMessage(null);

        if (!source && !fromTime && !toTime) {
            setError("Choose a source, a date range, or both.");
            return;
        }

        const approved = window.confirm(
            "This permanently deletes matching raw events. Continue?",
        );

        if (!approved) return;

        setIsDeleting(true);

        try {
            const result = await deleteEvents({
                source: source || undefined,
                from: fromTime ? new Date(fromTime).toISOString() : undefined,
                to: toTime ? new Date(toTime).toISOString() : undefined,
            });

            setMessage(`${result.deleted_count} event(s) deleted.`);
            setFromTime("");
            setToTime("");
        } catch (caughtError) {
            setError(
                caughtError instanceof Error
                    ? caughtError.message
                    : "Could not delete matching events.",
            );
        } finally {
            setIsDeleting(false);
        }
    }

    return (
        <section>
            <PageHeader
                description="Your activity stays controllable. Remove a selected slice of data, or erase the local record entirely when you need a clean slate."
                eyebrow="Your data, your rules"
                title="Privacy controls"
            />

            <div className="mt-7 grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(17rem,0.75fr)]">
                <section className="rounded-2xl border border-[#e8e8e4] bg-white p-5 sm:p-6">
                    <div className="flex items-start gap-3">
                        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[#f5f4ff] text-[#6558f5]">
                            <Icon className="h-4 w-4" name="trash" />
                        </span>
                        <div>
                            <h2 className="font-semibold tracking-[-0.025em] text-[#303136]">
                                Delete selected activity
                            </h2>
                            <p className="mt-1 text-sm leading-6 text-[#77787d]">
                                Choose a source, a time range, or both. Empty deletion
                                requests are blocked by the interface and the API.
                            </p>
                        </div>
                    </div>

                    <form className="mt-7" onSubmit={handleDelete}>
                        <div className="grid gap-4 sm:grid-cols-2">
                            <label className="block sm:col-span-2">
                                <span className="text-xs font-semibold text-[#4a4b4f]">Source</span>
                                <div className="relative mt-2">
                        <select
                                        className="h-11 w-full appearance-none rounded-xl border border-[#e4e4e0] bg-white px-3 pr-10 text-sm text-[#424348] outline-none transition focus:border-[#a8a1ff]"
                            value={source}
                            onChange={(event) =>
                                setSource(event.target.value as Source | "")
                            }
                        >
                            <option value="">Any source</option>
                            {sourceOptions.map((option) => (
                                <option key={option} value={option}>
                                    {option}
                                </option>
                            ))}
                        </select>
                                    <Icon className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#77777b]" name="chevron-down" />
                                </div>
                    </label>

                    <label className="block">
                                <span className="text-xs font-semibold text-[#4a4b4f]">From</span>
                        <input
                                    className="mt-2 h-11 w-full rounded-xl border border-[#e4e4e0] bg-white px-3 text-sm text-[#424348] outline-none transition focus:border-[#a8a1ff]"
                            type="datetime-local"
                            value={fromTime}
                            onChange={(event) => setFromTime(event.target.value)}
                        />
                    </label>

                    <label className="block">
                                <span className="text-xs font-semibold text-[#4a4b4f]">To</span>
                        <input
                                    className="mt-2 h-11 w-full rounded-xl border border-[#e4e4e0] bg-white px-3 text-sm text-[#424348] outline-none transition focus:border-[#a8a1ff]"
                            type="datetime-local"
                            value={toTime}
                            onChange={(event) => setToTime(event.target.value)}
                        />
                    </label>
                        </div>

                    <button
                            className="mt-6 inline-flex h-10 items-center gap-2 rounded-xl bg-[#c83745] px-4 text-sm font-semibold text-white transition hover:bg-[#ae2d3a] disabled:cursor-wait disabled:opacity-60"
                        disabled={isDeleting}
                        type="submit"
                    >
                            {isDeleting ? (
                                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/70 border-t-white" />
                            ) : (
                                <Icon className="h-4 w-4" name="trash" />
                            )}
                        {isDeleting ? "Deleting…" : "Delete selected events"}
                    </button>
                </form>

                {message && (
                        <p className="mt-5 rounded-xl bg-emerald-50 px-3 py-2.5 text-sm text-emerald-800">
                        {message}
                    </p>
                )}

                {error && (
                        <p className="mt-5 rounded-xl bg-red-50 px-3 py-2.5 text-sm text-red-800">
                        {error}
                    </p>
                )}
                </section>

                <aside className="rounded-2xl border border-[#e8e8e4] bg-[#f1f0ed] p-6">
                    <span className="grid h-9 w-9 place-items-center rounded-xl bg-white text-[#56575b] shadow-sm">
                        <Icon className="h-4 w-4" name="lock" />
                    </span>
                    <h2 className="mt-7 text-lg font-semibold tracking-[-0.03em] text-[#333438]">
                        Built for reversibility
                    </h2>
                    <ul className="mt-4 space-y-3 text-sm leading-6 text-[#747579]">
                        <li className="flex gap-2.5"><Icon className="mt-1 h-3.5 w-3.5 shrink-0 text-[#5d50df]" name="check" />Source controls stop new events immediately.</li>
                        <li className="flex gap-2.5"><Icon className="mt-1 h-3.5 w-3.5 shrink-0 text-[#5d50df]" name="check" />Deleted records leave the local timeline.</li>
                        <li className="flex gap-2.5"><Icon className="mt-1 h-3.5 w-3.5 shrink-0 text-[#5d50df]" name="check" />No cloud copy is created by Mosaic.</li>
                    </ul>
                </aside>
            </div>

            <EraseAllMemory />
        </section>
    );
}
