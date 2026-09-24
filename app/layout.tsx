import type { Metadata, Viewport } from "next"
import { Geist, Geist_Mono, Source_Serif_4 } from "next/font/google"

import "./globals.css"
import { ThemeProvider } from "@/components/theme-provider"
import { Toaster } from "@/components/ui/sonner"
import { cn } from "@/lib/utils"

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" })

const fontMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
})

const sourceSerif = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-heading",
  weight: ["500", "600", "700"],
})

export const metadata: Metadata = {
  title: "Multi-Model Chess Arena",
  description:
    "Play timed chess against AI language models in a warm, chess-club inspired study.",
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#e7dfcd",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={cn(
        "antialiased",
        fontMono.variable,
        "font-sans",
        geist.variable,
        sourceSerif.variable,
      )}
    >
      <body>
        <ThemeProvider>
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  )
}
