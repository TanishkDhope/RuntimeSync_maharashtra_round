import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MotionConfig } from "motion/react"
import { useState } from "react"

import { base } from "@/lib/motion"

export function Providers({ children }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 10_000 } },
      }),
  )
  return (
    <QueryClientProvider client={client}>
      {/* "user": honour prefers-reduced-motion (transforms off, opacity kept). */}
      <MotionConfig reducedMotion="user" transition={base}>
        {children}
      </MotionConfig>
    </QueryClientProvider>
  )
}
