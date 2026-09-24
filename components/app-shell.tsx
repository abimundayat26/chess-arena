import type { ReactNode } from "react"

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-svh bg-background">
      <header className="border-b border-border/70">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-baseline gap-2">
            <span className="font-heading text-lg font-semibold tracking-tight text-foreground">
              Chess Arena
            </span>
            <span className="hidden text-xs text-muted-foreground sm:inline">
              multi-model chess study
            </span>
          </div>
          <span className="text-xs text-muted-foreground">Local preview</span>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</main>
    </div>
  )
}
