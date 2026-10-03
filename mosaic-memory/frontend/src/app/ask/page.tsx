"use client";

import { FormEvent, useState } from "react";

import { Icon } from "@/components/icons";
import { PageHeader } from "@/components/page-header";
import { SourceMark, sourceLabel } from "@/components/source-mark";
import { askMemory, askMemoryWithGemini } from "@/lib/api";
import type { AskMemoryResponse } from "@/lib/types";

const examples = [
    "What was I learning about Python?",
    "What did I do last week?",
    "Show my LeetCode practice",
];

function formatDate(value: string) {
    return new Intl.DateTimeFormat("en-IN", {
        day: "numeric",
        month: "short",
        hour: "numeric",
        minute: "2-digit",
    }).format(new Date(value));
}

export default function AskMemoryPage() {
    const [query, setQuery] = useState("");
    const [result, setResult] = useState<AskMemoryResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isAsking, setIsAsking] = useState(false);

    async function submitQuestion(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const normalizedQuery = query.trim();

        if (normalizedQuery.length < 2) {
            setError("Enter at least two characters to search your local activity.");
            return;
        }

        setIsAsking(true);
        setError(null);

        try {
            setResult(await askMemory(normalizedQuery));
        } catch (caughtError) {
            setError(
                caughtError instanceof Error
                    ? caughtError.message
                    : "Mosaic could not search your local memory.",
            );
        } finally {
            setIsAsking(false);
        }
    }

    async function askWithGemini() {
        const normalizedQuery = query.trim();
        if (normalizedQuery.length < 2) {
            setError("Enter at least two characters before asking Gemini.");
            return;
        }

        setIsAsking(true);
        setError(null);
        try {
            setResult(await askMemoryWithGemini(normalizedQuery));
        } catch (caughtError) {
            setError(
                caughtError instanceof Error
                    ? caughtError.message
                    : "Gemini could not answer from the selected tab evidence.",
            );
        } finally {
            setIsAsking(false);
        }
    }

    return (
        <section>
            <PageHeader
                description="Search your approved activity in plain language. Mosaic generates a local, evidence-backed response and shows every event it relied on."
                eyebrow="Private retrieval"
                title="Ask your memory"
            />

            <form className="mt-8" onSubmit={submitQuestion}>
                <div className="rounded-2xl border border-[#dfdcff] bg-white p-2 shadow-[0_8px_32px_rgba(70,62,150,0.06)]">
                    <label className="flex items-center gap-3">
                        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#f0efff] text-[#5e52df]">
                            <Icon className="h-5 w-5" name="sparkles" />
                        </span>
                        <span className="sr-only">Ask a question about your activity</span>
                        <input
                            className="min-w-0 flex-1 bg-transparent py-3 text-sm text-[#303136] outline-none placeholder:text-[#a0a0a5]"
                            disabled={isAsking}
                            onChange={(event) => setQuery(event.target.value)}
                            placeholder="What would you like to remember?"
                            value={query}
                        />
                        <button
                            className="inline-flex h-10 shrink-0 items-center gap-2 rounded-xl bg-[#1d1e22] px-4 text-sm font-semibold text-white transition hover:bg-[#393a3f] disabled:cursor-wait disabled:opacity-60"
                            disabled={isAsking}
                            type="submit"
                        >
                            {isAsking ? (
                                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/60 border-t-white" />
                            ) : (
                                <Icon className="h-4 w-4" name="arrow-right" />
                            )}
                            Ask
                        </button>
                    </label>
                </div>
            </form>

            <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="mr-1 text-xs text-[#929297]">Try:</span>
                {examples.map((example) => (
                    <button
                        className="rounded-lg border border-[#e5e4e1] bg-white px-2.5 py-1.5 text-xs text-[#67686d] transition hover:border-[#c9c5ff] hover:text-[#574ade]"
                        key={example}
                        onClick={() => setQuery(example)}
                        type="button"
                    >
                        {example}
                    </button>
                ))}
            </div>

            <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-[#e5e1ff] bg-[#faf9ff] px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-5 text-[#625d91]">
                    <span className="font-semibold">Ask with Gemini</span> sends your question and up to 6,000 characters from the top matching tabs you explicitly understood to Gemini. It never sends ordinary browsing activity.
                </p>
                <button
                    className="shrink-0 rounded-xl border border-[#beb7ff] bg-white px-3.5 py-2 text-xs font-semibold text-[#574ade] transition hover:bg-[#f2f0ff] disabled:cursor-wait disabled:opacity-60"
                    disabled={isAsking}
                    onClick={() => void askWithGemini()}
                    type="button"
                >
                    Ask with Gemini
                </button>
            </div>

            {error && (
                <div className="mt-6 flex gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                    <Icon className="mt-0.5 h-4 w-4 shrink-0" name="bolt" />
                    {error}
                </div>
            )}

            {!result && !error && (
                <div className="mt-10 grid gap-4 md:grid-cols-3">
                    <Principle icon="lock" text="Runs against your local Mosaic database." title="Local retrieval" />
                    <Principle icon="eye" text="Every result reveals its raw source events." title="Evidence first" />
                    <Principle icon="sparkles" text="Uses deterministic local ranking—no cloud model." title="Transparent method" />
                </div>
            )}

            {result && (
                <div className="mt-8 space-y-5">
                    <section className="rounded-2xl border border-[#e8e8e4] bg-white p-5 sm:p-6">
                        <div className="flex items-center justify-between gap-4">
                            <div className="flex items-center gap-2 text-xs font-semibold text-[#5b4fdf]">
                                <Icon className="h-4 w-4" name="sparkles" />
                                {result.retrieval_method.startsWith("local retrieval + Gemini")
                                    ? "Gemini answer"
                                    : "Local answer"}
                            </div>
                            <p className="text-xs text-[#98989d]">{formatDate(result.generated_at)}</p>
                        </div>
                        <p className="mt-4 text-lg font-medium leading-8 tracking-[-0.025em] text-[#303136]">
                            {result.answer}
                        </p>
                        <p className="mt-5 border-t border-[#f0f0ed] pt-4 text-xs text-[#8b8b90]">
                            Method: {result.retrieval_method}. {result.retrieval_method.startsWith("local retrieval + Gemini")
                                ? "Gemini received only the click-approved excerpts used for this answer."
                                : "This is a local ranking, not a generated claim beyond the evidence below."}
                        </p>
                    </section>

                    <section className="overflow-hidden rounded-2xl border border-[#e8e8e4] bg-white">
                        <div className="flex items-center justify-between border-b border-[#efefec] px-5 py-4 sm:px-6">
                            <div>
                                <h2 className="text-sm font-semibold text-[#34353a]">Evidence</h2>
                                <p className="mt-1 text-xs text-[#89898e]">
                                    {result.memories.length === 0
                                        ? "No local events matched this question."
                                        : `${result.memories.length} ranked local ${result.memories.length === 1 ? "memory" : "memories"}`}
                                </p>
                            </div>
                            <span className="rounded-lg bg-[#f5f4ff] px-2 py-1 text-[10px] font-bold uppercase tracking-[0.1em] text-[#6255e5]">
                                Verifiable
                            </span>
                        </div>

                        {result.memories.length === 0 ? (
                            <div className="px-6 py-10 text-center text-xs text-[#89898e]">
                                No local activity was found matching this question.
                            </div>
                        ) : (
                            result.memories.map((memory) => (
                            <article className="border-b border-[#f0f0ed] px-5 py-5 last:border-0 sm:px-6" key={memory.id}>
                                <div className="flex gap-3">
                                    <SourceMark source={memory.source} />
                                    <div className="min-w-0 flex-1">
                                        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                                            <h3 className="text-sm font-semibold text-[#303136]">{memory.summary}</h3>
                                            <span className="shrink-0 text-xs text-[#88888d]">
                                                {formatDate(memory.occurred_at)}
                                            </span>
                                        </div>
                                        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[#78797e]">
                                            <span>{sourceLabel(memory.source)}</span>
                                            <span className="h-1 w-1 rounded-full bg-[#c6c6ca]" />
                                            <span>{Math.round(memory.score * 100)}% relevance</span>
                                            <span className="h-1 w-1 rounded-full bg-[#c6c6ca]" />
                                            <span>
                                                {memory.model_id
                                                    .replace(/^local-/, "")
                                                    .replace(/-v\d+$/, "")
                                                    .replaceAll("-", " ")}
                                            </span>
                                            {memory.links.length > 0 && (
                                                <>
                                                    <span className="h-1 w-1 rounded-full bg-[#c6c6ca]" />
                                                    <span>{memory.links.length} related {memory.links.length === 1 ? "memory" : "memories"}</span>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                <details className="mt-4 rounded-xl bg-[#fafaf8] px-3 py-2.5 text-xs text-[#6f7075]">
                                    <summary className="cursor-pointer font-semibold text-[#535459]">
                                        Show raw evidence ({memory.evidence.length})
                                    </summary>
                                    <div className="mt-3 space-y-2 border-t border-[#eeeeeb] pt-3">
                                        {memory.evidence.map(({ event }) => (
                                            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between" key={event.event_id}>
                                                <span>{event.title ?? event.event_type.replaceAll("_", " ")}</span>
                                                <span className="text-[#97979b]">{event.event_type.replaceAll("_", " ")}</span>
                                            </div>
                                        ))}
                                    </div>
                                </details>
                            </article>
                            ))
                        )}
                    </section>
                </div>
            )}
        </section>
    );
}

function Principle({
    icon,
    title,
    text,
}: {
    icon: "eye" | "lock" | "sparkles";
    title: string;
    text: string;
}) {
    return (
        <article className="rounded-2xl border border-[#e8e8e4] bg-white p-5">
            <Icon className="h-4 w-4 text-[#6558f5]" name={icon} />
            <h2 className="mt-5 text-sm font-semibold text-[#36373b]">{title}</h2>
            <p className="mt-1 text-xs leading-5 text-[#85858a]">{text}</p>
        </article>
    );
}
