import type { Source } from "@/lib/types";

import { Icon, type IconName } from "@/components/icons";

const sourceAppearance: Record<
    Source,
    { label: string; icon: IconName; className: string }
> = {
    browser: { label: "Browser", icon: "browser", className: "bg-sky-50 text-sky-700 ring-sky-100" },
    youtube: { label: "YouTube", icon: "video", className: "bg-rose-50 text-rose-700 ring-rose-100" },
    leetcode: { label: "LeetCode", icon: "code", className: "bg-amber-50 text-amber-700 ring-amber-100" },
    vscode: { label: "VS Code", icon: "bolt", className: "bg-indigo-50 text-indigo-700 ring-indigo-100" },
    document: { label: "Document", icon: "file", className: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
    git: { label: "Git", icon: "code", className: "bg-slate-50 text-slate-700 ring-slate-100" },
};

interface SourceMarkProps {
    source: Source;
    size?: "small" | "regular";
}

export function SourceMark({ source, size = "regular" }: SourceMarkProps) {
    const appearance = sourceAppearance[source];
    const dimensions = size === "small" ? "h-8 w-8" : "h-10 w-10";

    return (
        <span
            aria-label={appearance.label}
            className={`inline-flex shrink-0 items-center justify-center rounded-xl ring-1 ${dimensions} ${appearance.className}`}
            title={appearance.label}
        >
            <Icon className={size === "small" ? "h-4 w-4" : "h-5 w-5"} name={appearance.icon} />
        </span>
    );
}

export function sourceLabel(source: Source) {
    return sourceAppearance[source].label;
}
