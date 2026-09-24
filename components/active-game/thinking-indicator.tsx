export function ThinkingIndicator() {
  return (
    <p className="mt-0.5 flex items-center gap-1 text-xs text-primary">
      <span>Thinking</span>
      <span className="flex gap-0.5">
        <span className="size-1 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
        <span className="size-1 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
        <span className="size-1 animate-bounce rounded-full bg-primary" />
      </span>
    </p>
  )
}
