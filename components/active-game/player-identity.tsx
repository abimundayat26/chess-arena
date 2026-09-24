import { Bot, User } from "lucide-react"

import { ChessClock } from "./chess-clock"
import { ThinkingIndicator } from "./thinking-indicator"

interface PlayerIdentityProps {
  name: string
  subtitle?: string
  clockLabel: string
  isActiveTurn: boolean
  isThinking?: boolean
  variant: "human" | "model"
}

export function PlayerIdentity({
  name,
  subtitle,
  clockLabel,
  isActiveTurn,
  isThinking,
  variant,
}: PlayerIdentityProps) {
  const seconds = Number(clockLabel.split(":")[0]) * 60 + Number(clockLabel.split(":")[1])
  const low = seconds > 0 && seconds < 30

  return (
    <div className="flex items-center justify-between gap-3 rounded-sm border border-border bg-card px-4 py-3">
      <div className="flex items-center gap-3">
        <div className="flex size-9 items-center justify-center rounded-full border border-border bg-secondary">
          {variant === "human" ? (
            <User className="size-4 text-foreground" />
          ) : (
            <Bot className="size-4 text-foreground" />
          )}
        </div>
        <div>
          <p className="text-sm font-medium leading-tight text-foreground">{name}</p>
          {subtitle && (
            <p className="text-xs leading-tight text-muted-foreground">{subtitle}</p>
          )}
          {isThinking && <ThinkingIndicator />}
        </div>
      </div>
      <ChessClock label={clockLabel} active={isActiveTurn} low={low} />
    </div>
  )
}
