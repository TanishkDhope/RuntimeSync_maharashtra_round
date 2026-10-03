import { Link } from "react-router"

import { EmptyState } from "@/components/EmptyState"

export function NotFound() {
  return (
    <div className="px-6 py-20">
      <EmptyState
        eyebrow="404"
        title="Nothing lives at this address"
        action={
          <Link to="/" className="font-medium text-accent underline underline-offset-4">
            Back to the start
          </Link>
        }
      >
        <p>The page may have moved, or the link was mistyped.</p>
      </EmptyState>
    </div>
  )
}
