import { Moon, Sun } from "lucide-react"
import { motion } from "motion/react"
import { Link, useLocation } from "react-router"

import { cn } from "@/lib/cn"
import { initials, setCurrentLearner, useCurrentLearner } from "@/lib/learner"
import { spring } from "@/lib/motion"
import { clearCurrentSession, useCurrentSession } from "@/lib/session"
import { useTheme } from "@/lib/theme"

export function Header({ health }) {
  const learner = useCurrentLearner()
  const { pathname } = useLocation()
  const session = useCurrentSession()
  // An open session belonging to whoever this browser is working as.
  const open = session?.id && session.learnerId === learner?.id ? session : null
  // History and the profile button are earned: there is nothing behind them
  // until a session has been started. The learner is set at that moment and
  // stays set, so finishing a session doesn't take them away again.
  const started = Boolean(learner)

  /**
   * Going home signs out. Nothing is destroyed: the session stays open on the
   * backend, so picking the same name again offers to continue it. This only
   * forgets who this browser is working as, which is what takes History and
   * the profile button back off the bar.
   */
  function signOut() {
    setCurrentLearner(null)
    clearCurrentSession()
  }

  return (
    <header className="sticky top-0 z-30 border-b border-rule bg-paper/90 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-[1240px] items-center gap-6 px-6 lg:px-10">
        <Wordmark onClick={signOut} signsOut={started} />
        <nav aria-label="Main" className="flex items-center gap-1">
          <NavItem
            to={open ? `/learn/${open.id}` : "/"}
            active={pathname === "/" || pathname.startsWith("/learn/")}
            title={open ? "Your session is still open" : undefined}
          >
            {open ? "Session" : "Learn"}
            {open && (
              <span
                aria-hidden="true"
                className="ml-1.5 inline-block size-1.5 translate-y-[-1px] rounded-full bg-accent align-middle"
              />
            )}
          </NavItem>
          {started && (
            <NavItem to={`/learners/${learner.id}`} active={pathname.startsWith("/learners")}>
              History
            </NavItem>
          )}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <DiagnoserStatus health={health} />
          <ThemeToggle />
          {started && (
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

function Wordmark({ onClick, signsOut }) {
  return (
    <Link
      to="/"
      onClick={onClick}
      title={signsOut ? "Home - this signs you out of the session" : undefined}
      className="font-serif text-[23px] font-semibold tracking-tight text-ink"
      aria-label={signsOut ? "Re:Learn, home and sign out" : "Re:Learn, home"}
    >
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
      {/* <span className="hidden font-normal text-accent/75 lg:inline">· {data.library_size} beliefs</span> */}
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
