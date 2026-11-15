# TraceroAI web

The landing page, docs, and dashboard. Next.js App Router; the dashboard pages render on
the server and read the TraceroAI API with a server-side key.

```bash
npm install
npm run dev        # http://localhost:3000
```

Against a local API in development mode no configuration is needed. Otherwise set:

| Variable | Read when | Purpose |
|---|---|---|
| `TRACEROAI_API_URL` | request time, server only | API address for server rendering. Can be internal, e.g. `http://api:8000`. |
| `NEXT_PUBLIC_TRACEROAI_API_URL` | build time, sent to browsers | API address for browser code (the docs playground). Falls back for the server too. |
| `TRACEROAI_API_KEY` | request time, server only | Key the dashboard reads with. An admin key shows every project; a project key shows one. |
| `TRACEROAI_DASHBOARD_PASSWORD` | request time, server only | If set, `/dashboard` requires this password. |
| `NEXT_PUBLIC_SHOW_COST` | build time | `false` hides cost figures. |

Without a password the dashboard shows everything `TRACEROAI_API_KEY` can read to anyone
who can reach it. Set one before exposing a dashboard that holds an admin key.

See `AGENTS.md` before changing framework code: this Next.js version differs from older
releases (for example, `src/proxy.ts` replaces `middleware.ts`).
