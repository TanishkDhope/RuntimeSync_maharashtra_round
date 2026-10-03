import { Moon, Sun } from "lucide-react"
import { motion } from "motion/react"
import { Link, useLocation } from "react-router"

import { cn } from "@/lib/cn"
import { initials, useCurrentLearner } from "@/lib/learner"
import { spring } from "@/lib/motion"
import { readJson } from "@/lib/storage"
import { useTheme } from "@/lib/theme"

export function Header({ health }) {
  const learner = useCurrentLearner()
  const { pathname } = useLocation()
  const lastSession = readJson("local", "relearn.session")
  const learnTo = lastSession?.learnerId === learner?.id && lastSession?.id ? `/learn/${lastSession.id}` : "/"

  return (
    <header className="sticky top-0 z-30 border-b border-rule bg-paper/90 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-[1240px] items-center gap-6 px-6 lg:px-10">
        <Wordmark />
        <nav aria-label="Main" className="flex items-center gap-1">
          <NavItem to={learnTo} active={pathname === "/" || pathname.startsWith("/learn/")}>
            Learn
          </NavItem>
          <NavItem
            to={learner ? `/learners/${learner.id}` : "/"}
            active={pathname.startsWith("/learners")}
            title={learner ? undefined : "Pick a learner first"}
          >
            History
          </NavItem>
          <NavItem to="/evaluation" active={pathname.startsWith("/evaluation")}>
            Evaluation
          </NavItem>
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <DiagnoserStatus health={health} />
          <ThemeToggle />
          {learner && (
            <Link
              to={`/learners/${learner.id}`}
              title={`${learner.name}: learner history`}
              className="grid size-9 place-items-center rounded-full border border-rule-strong bg-surface text-small font-semibold text-ink-2 hover:border-ink-2/50"
            >
              {initials(learner.name)}
            </Link>
          )}
        </div>
      </div>
    </header>
  )
}

function Wordmark() {
  return (
    <Link to="/" className="font-serif text-[23px] font-semibold tracking-tight text-ink" aria-label="Re:Learn, home">
      Re<span className="text-accent">:</span>Learn
    </Link>
  )
}

function NavItem({ to, active, children, title }) {
  return (
    <Link
      to={to}
      title={title}
      aria-current={active ? "page" : undefined}
      className="relative rounded-control px-3 py-1.5 text-[15px] font-medium"
    >
      <span className={cn("transition-colors", active ? "text-ink" : "text-muted hover:text-ink")}>{children}</span>
      {active && (
        <motion.span
          layoutId="nav-underline"
          transition={spring}
          className="absolute inset-x-3 -bottom-[11px] h-[2px] rounded-full bg-ink"
        />
      )}
    </Link>
  )
}

/** Which diagnoser is live. The full stub warning is a strip under the header. */
function DiagnoserStatus({ health }) {
  if (health.isPending) {
    return <span className="hidden text-small text-muted md:inline">Checking backend…</span>
  }
  if (health.isError) {
    return (
      <span className="inline-flex h-8 items-center gap-2 rounded-full border border-active/30 bg-active-soft px-3 text-small font-medium text-active">
        <span className="size-2 rounded-full bg-active" aria-hidden="true" />
        Backend offline
      </span>
    )
  }
  const data = health.data
  return data.diagnoser_is_real_model ? (
    <span
      title={data.model_path}
      className="inline-flex h-8 items-center gap-2 rounded-full border border-accent/30 bg-accent-soft px-3 text-small font-medium text-accent"
    >
      <span className="size-2 rounded-full bg-accent" aria-hidden="true" />
      Trained model
      <span className="hidden font-normal text-accent/75 lg:inline">· {data.library_size} beliefs</span>
    </span>
  ) : (
    <span className="inline-flex h-8 items-center gap-2 rounded-full border border-hazard/60 bg-hazard/25 px-3 text-small font-semibold text-hazard-ink dark:text-hazard">
      <svg viewBox="0 0 10 10" className="size-2.5" aria-hidden="true">
        <path d="M5 1 9.2 9H.8Z" fill="currentColor" />
      </svg>
      Stub
    </span>
  )
}

function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const dark = theme === "dark"
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      title={dark ? "Light theme (best on a projector)" : "Dark theme"}
      className="grid size-9 place-items-center rounded-full text-muted transition-colors hover:bg-surface-2 hover:text-ink"
    >
      <motion.span key={theme} initial={{ rotate: -40, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} transition={spring}>
        {dark ? <Sun className="size-[18px]" strokeWidth={1.5} /> : <Moon className="size-[18px]" strokeWidth={1.5} />}
      </motion.span>
    </button>
  )
}
