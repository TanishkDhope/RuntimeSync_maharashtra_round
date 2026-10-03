import "@fontsource-variable/ibm-plex-sans"
import "@fontsource-variable/jetbrains-mono"
import "@fontsource-variable/source-serif-4"
import "@fontsource-variable/source-serif-4/wght-italic.css"
import "@/styles/globals.css"

import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { createBrowserRouter, RouterProvider } from "react-router"

import { EvaluationPage } from "@/features/evaluation/EvaluationPage"
import { HistoryPage } from "@/features/history/HistoryPage"
import { LearnPage } from "@/features/learn/LearnPage"
import { StartPage } from "@/features/start/StartPage"

import { NotFound } from "./NotFound"
import { Providers } from "./Providers"
import { Shell } from "./Shell"

const router = createBrowserRouter([
  {
    element: <Shell />,
    children: [
      { index: true, element: <StartPage /> },
      { path: "learn/:sessionId", element: <LearnPage /> },
      { path: "learners/:learnerId", element: <HistoryPage /> },
      { path: "evaluation", element: <EvaluationPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
])

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  </StrictMode>,
)
