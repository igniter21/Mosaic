"use client";

import { FormEvent, useState } from "react";

import { Icon } from "@/components/icons";
import { eraseAllMemory } from "@/lib/api";

const CONFIRMATION_PHRASE = "ERASE ALL LOCAL MEMORY";

export function EraseAllMemory() {
    const [confirmation, setConfirmation] = useState("");
    const [message, setMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isErasing, setIsErasing] = useState(false);

    async function handleErase(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setError(null);
        setMessage(null);

        if (confirmation !== CONFIRMATION_PHRASE) {
            setError(`Type exactly: ${CONFIRMATION_PHRASE}`);
            return;
        }

        const approved = window.confirm(
            "This permanently removes all local activity data. Continue?",
        );

        if (!approved) return;

        setIsErasing(true);

        try {
            const result = await eraseAllMemory(confirmation);

            setMessage(
                `Deleted ${result.raw_events_deleted} event(s), ` +
                `${result.derived_memories_deleted} derived memory record(s), ` +
                `${result.audit_logs_deleted} audit log(s), and disabled ` +
                `${result.sources_disabled} source(s).`,
            );

            setConfirmation("");

            if (!result.vacuum_performed) {
                setError(
                    "Data was deleted, but SQLite compaction could not run. " +
                    "Close database viewers and retry later.",
                );
            }
        } catch (caughtError) {
            setError(
                caughtError instanceof Error
                    ? caughtError.message
                    : "Could not erase local memory.",
            );
        } finally {
            setIsErasing(false);
        }
    }

    return (
        <article className="mt-8 overflow-hidden rounded-2xl border border-[#efcbd0] bg-white">
            <div className="border-b border-[#f2d8db] bg-[#fff7f7] px-5 py-5 sm:px-6">
                <div className="flex items-start gap-3">
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[#fae4e6] text-[#bd3544]">
                        <Icon className="h-4 w-4" name="trash" />
                    </span>
                    <div>
                        <h2 className="font-semibold tracking-[-0.025em] text-[#712630]">
                            Erase all local memory
                        </h2>
                        <p className="mt-1 text-sm leading-6 text-[#91444d]">
                            This permanently deletes every stored event and audit log,
                            then disables all sources. It cannot be undone.
                        </p>
                    </div>
                </div>
            </div>

            <form className="p-5 sm:p-6" onSubmit={handleErase}>
                <label className="block">
                    <span className="text-xs font-semibold text-[#6e3b42]">
                        Type <span className="font-mono text-[11px]">{CONFIRMATION_PHRASE}</span> to continue
                    </span>

                    <input
                        className="mt-2 h-11 w-full rounded-xl border border-[#eebfc5] bg-white px-3 text-sm text-[#542c31] outline-none transition placeholder:text-[#b98b90] focus:border-[#d96874]"
                        placeholder="Confirmation phrase"
                        value={confirmation}
                        onChange={(event) => setConfirmation(event.target.value)}
                    />
                </label>

                <button
                    className="mt-5 inline-flex h-10 items-center gap-2 rounded-xl bg-[#c83745] px-4 text-sm font-semibold text-white transition hover:bg-[#ae2d3a] disabled:cursor-not-allowed disabled:opacity-45"
                    disabled={
                        isErasing || confirmation !== CONFIRMATION_PHRASE
                    }
                    type="submit"
                >
                    {isErasing ? (
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/70 border-t-white" />
                    ) : (
                        <Icon className="h-4 w-4" name="trash" />
                    )}
                    {isErasing ? "Erasing…" : "Erase all local memory"}
                </button>
            </form>

            {message && (
                <p className="mx-5 mb-5 rounded-xl bg-emerald-50 px-3 py-2.5 text-sm text-emerald-800 sm:mx-6 sm:mb-6">
                    {message}
                </p>
            )}

            {error && (
                <p className="mx-5 mb-5 rounded-xl bg-red-50 px-3 py-2.5 text-sm text-red-800 sm:mx-6 sm:mb-6">
                    {error}
                </p>
            )}
        </article>
    );
}
