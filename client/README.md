# Re:Learn frontend

React + Vite. The backend owns the flow: every response carries a `step`
field, and this app renders whichever step it is handed. There is no flow
logic here, which is why new steps (probe, intervention, reassessment) need
no changes to `src/api/client.js`.

```bash
npm install
npm run dev     # http://localhost:5173
npm run build
npm run lint
```

`VITE_API_BASE` points at the backend; it defaults to
`http://localhost:8000`. See `.env.example`.

Setup and the stub/model switch are documented in the repository README.
