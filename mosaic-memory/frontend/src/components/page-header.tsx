import type { ReactNode } from "react";

interface PageHeaderProps {
    eyebrow: string;
    title: string;
    description: string;
    action?: ReactNode;
}

export function PageHeader({
    eyebrow,
    title,
    description,
    action,
}: PageHeaderProps) {
    return (
        <header className="flex flex-col gap-5 border-b border-[#e8e8e4] pb-8 sm:flex-row sm:items-end sm:justify-between">
            <div className="max-w-2xl">
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#6558f5]">
                    {eyebrow}
                </p>
                <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em] text-[#1d1e22] sm:text-[2.25rem]">
                    {title}
                </h1>
                <p className="mt-3 text-[15px] leading-6 text-[#747579]">
                    {description}
                </p>
            </div>
            {action}
        </header>
    );
}
