import { ScrollArea } from "@/components/ui/scroll-area"

interface MoveListProps {
  sanHistory: string[]
}

export function MoveList({ sanHistory }: MoveListProps) {
  const rows: { number: number; white?: string; black?: string }[] = []
  for (let i = 0; i < sanHistory.length; i += 2) {
    rows.push({
      number: i / 2 + 1,
      white: sanHistory[i],
      black: sanHistory[i + 1],
    })
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden rounded-sm border border-border bg-card">
      <div className="border-b border-border px-3 py-2">
        <h3 className="font-heading text-sm font-semibold text-foreground">Moves</h3>
      </div>
      <ScrollArea className="h-40 flex-1">
        {rows.length === 0 ? (
          <p className="px-3 py-3 text-xs text-muted-foreground">
            The game log will appear here once play begins.
          </p>
        ) : (
          <ol className="divide-y divide-border/60">
            {rows.map((row) => (
              <li
                key={row.number}
                className="grid grid-cols-[2rem_1fr_1fr] gap-2 px-3 py-1.5 font-mono text-sm"
              >
                <span className="text-muted-foreground">{row.number}.</span>
                <span className="text-foreground">{row.white}</span>
                <span className="text-foreground">{row.black ?? ""}</span>
              </li>
            ))}
          </ol>
        )}
      </ScrollArea>
    </div>
  )
}
