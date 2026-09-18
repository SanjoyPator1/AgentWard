"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

// Chat is the default surface (root redirects here); Worklist is the
// secondary view someone switches to, so it's listed second and never
// implied by an unmatched path.
const links = [
  { href: "/chat", label: "Chat" },
  { href: "/worklist", label: "Worklist" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <Link href="/chat" className="flex items-baseline gap-2">
          <span className="text-sm font-semibold text-foreground">AgentWard</span>
          <span className="text-xs text-foreground-faint">F1 · Care Gap Hunter</span>
        </Link>
        <nav className="flex items-center gap-0.5 rounded-full border border-border bg-surface-muted p-0.5">
          {links.map((link) => {
            const active = pathname?.startsWith(link.href) ?? link.href === "/chat";
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                  active
                    ? "bg-surface text-foreground shadow-sm"
                    : "text-foreground-faint hover:text-foreground-muted",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
