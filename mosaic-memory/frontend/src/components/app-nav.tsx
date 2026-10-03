"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Icon, type IconName } from "@/components/icons";

const navigation: { href: string; label: string; icon: IconName }[] = [
    { href: "/", label: "Overview", icon: "home" },
    { href: "/timeline", label: "Timeline", icon: "clock" },
    { href: "/ask", label: "Ask memory", icon: "message" },
    { href: "/context", label: "Context OS", icon: "sparkles" },
    { href: "/sources", label: "Data sources", icon: "database" },
    { href: "/privacy", label: "Privacy", icon: "shield" },
];

function Brand() {
    return (
        <Link className="flex items-center gap-3" href="/">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#1d1e22] text-sm font-semibold text-white shadow-sm">
                M
            </span>
            <span>
                <span className="block text-[15px] font-semibold tracking-[-0.025em] text-[#1d1e22]">
                    Mosaic
                </span>
                <span className="block text-[11px] text-[#909095]">Memory, locally</span>
            </span>
        </Link>
    );
}

function NavigationLinks({ compact = false }: { compact?: boolean }) {
    const pathname = usePathname();

    return (
        <div className={compact ? "flex items-center gap-1" : "space-y-1"}>
            {navigation.map((item) => {
                const isActive = pathname === item.href;

                return (
                    <Link
                        aria-current={isActive ? "page" : undefined}
                        aria-label={compact ? item.label : undefined}
                        className={
                            compact
                                ? `inline-flex h-9 w-9 items-center justify-center rounded-lg transition ${
                                      isActive
                                          ? "bg-[#edecff] text-[#5247dc]"
                                          : "text-[#77777b] hover:bg-white hover:text-[#1d1e22]"
                                  }`
                                : `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                                      isActive
                                          ? "bg-[#eeedff] text-[#5247dc]"
                                          : "text-[#66676b] hover:bg-white hover:text-[#1d1e22]"
                                  }`
                        }
                        href={item.href}
                        key={item.href}
                        title={compact ? item.label : undefined}
                    >
                        <Icon className="h-[18px] w-[18px]" name={item.icon} />
                        {!compact && item.label}
                    </Link>
                );
            })}
        </div>
    );
}

export function AppNav() {
    return (
        <>
            <aside className="fixed inset-y-0 left-0 z-20 hidden w-[17rem] flex-col border-r border-[#e8e8e4] bg-[#f7f7f4] px-4 py-5 lg:flex">
                <Brand />
                <nav aria-label="Main navigation" className="mt-10">
                    <NavigationLinks />
                </nav>
                <div className="mt-auto rounded-2xl border border-[#e8e8e4] bg-white p-4">
                    <div className="flex items-center gap-2 text-xs font-medium text-[#36363a]">
                        <span className="h-2 w-2 rounded-full bg-[#4caf75]" />
                        Local storage active
                    </div>
                    <p className="mt-2 text-xs leading-5 text-[#85858a]">
                        Your activity stays on this device until you choose otherwise.
                    </p>
                </div>
            </aside>

            <header className="sticky top-0 z-20 flex items-center justify-between border-b border-[#e8e8e4] bg-[#f7f7f4]/95 px-5 py-3 backdrop-blur lg:hidden">
                <Brand />
                <nav aria-label="Main navigation">
                    <NavigationLinks compact />
                </nav>
            </header>
        </>
    );
}
