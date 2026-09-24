"use client"

import { useEffect, useRef, useState } from "react"
import { Flag, Handshake } from "lucide-react"
import { toast } from "sonner"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"

interface GameControlsProps {
  disabled: boolean
  opponentName: string
  onResign: () => void
  onOfferDraw: (accepted: boolean) => Promise<void>
}

export function GameControls({
  disabled,
  opponentName,
  onResign,
  onOfferDraw,
}: GameControlsProps) {
  const drawTimer = useRef<number | undefined>(undefined)
  const [resignOpen, setResignOpen] = useState(false)
  const [offeringDraw, setOfferingDraw] = useState(false)

  useEffect(() => {
    return () => window.clearTimeout(drawTimer.current)
  }, [])

  function handleOfferDraw() {
    if (disabled || offeringDraw) return
    setOfferingDraw(true)
    toast(`Draw offer sent to ${opponentName}...`)
    drawTimer.current = window.setTimeout(() => {
      const accepted = Math.random() < 0.35
      void onOfferDraw(accepted).then(() => setOfferingDraw(false))
    }, 1400)
  }

  return (
    <div className="flex gap-2">
      <Button
        variant="outline"
        className="flex-1"
        disabled={disabled || offeringDraw}
        onClick={handleOfferDraw}
      >
        <Handshake data-icon="inline-start" />
        Offer Draw
      </Button>
      <Button
        variant="outline"
        className="flex-1 text-accent hover:text-accent"
        disabled={disabled}
        onClick={() => setResignOpen(true)}
      >
        <Flag data-icon="inline-start" />
        Resign
      </Button>

      <AlertDialog open={resignOpen} onOpenChange={setResignOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading">
              Resign this game?
            </AlertDialogTitle>
            <AlertDialogDescription>
              You will lose the game immediately. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onResign}>Resign</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
