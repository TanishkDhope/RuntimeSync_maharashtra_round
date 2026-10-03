import { python } from "@codemirror/lang-python"
import { oneDark } from "@codemirror/theme-one-dark"
import CodeMirror from "@uiw/react-codemirror"

/** Python editor for write_code answers. */
export function CodeEditor({ value, onChange, disabled }) {
  return (
    <div className="overflow-hidden rounded-md border">
      <CodeMirror
        value={value}
        onChange={onChange}
        readOnly={disabled}
        height="240px"
        theme={oneDark}
        extensions={[python()]}
        basicSetup={{
          lineNumbers: true,
          highlightActiveLine: !disabled,
          autocompletion: false,
          tabSize: 4,
        }}
        style={{ fontSize: "15px" }}
      />
    </div>
  )
}
