import type { ReactNode } from "react"

export function AppShell({ children, onHome }: { children: ReactNode; onHome: () => void }) {
  return (
    <div className="min-h-svh bg-background">
      <header className="border-b border-border/70">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-baseline gap-2">
            <button
              type="button"
              onClick={onHome}
              className="font-heading text-lg font-semibold tracking-tight text-foreground hover:text-primary focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              aria-label="Chess Arena — back to game setup"
            >
              Chess Arena
            </button>
            <span className="hidden text-xs text-muted-foreground sm:inline">
              multi-model chess study
            </span>
          </div>
          <span className="text-xs text-muted-foreground">Play & review</span>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</main>
    </div>
  )
}
