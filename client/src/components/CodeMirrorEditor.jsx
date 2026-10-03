import { python } from "@codemirror/lang-python"
import { syntaxHighlighting } from "@codemirror/language"
import { Prec } from "@codemirror/state"
import { keymap } from "@codemirror/view"
import { classHighlighter } from "@lezer/highlight"
import CodeMirror from "@uiw/react-codemirror"
import { useMemo } from "react"

const BASIC_SETUP = {
  lineNumbers: true,
  foldGutter: false,
  highlightActiveLine: true,
  highlightActiveLineGutter: true,
  autocompletion: false,
  tabSize: 4,
}

/** Loaded lazily by CodeEditor. Same tok-* classes as the read-only viewer. */
export default function CodeMirrorEditor({ value, onChange, disabled, onSubmit, autoFocus, placeholder }) {
  const extensions = useMemo(
    () => [
      python(),
      syntaxHighlighting(classHighlighter),
      Prec.highest(
        keymap.of([
          {
            key: "Mod-Enter",
            run: () => {
              onSubmit?.()
              return true
            },
          },
        ]),
      ),
    ],
    [onSubmit],
  )

  return (
    <CodeMirror
      value={value}
      onChange={onChange}
      readOnly={disabled}
      editable={!disabled}
      autoFocus={autoFocus}
      placeholder={placeholder}
      height="240px"
      theme="none"
      basicSetup={BASIC_SETUP}
      extensions={extensions}
    />
  )
}
