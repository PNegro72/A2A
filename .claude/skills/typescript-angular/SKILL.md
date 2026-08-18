---
name: typescript-angular
description: "Angular 18 standalone + Signals conventions for the frontend PWA: components, services, SSE/polling transport, build output, and the known backend contract gap. Use when writing or reviewing frontend/**."
when_to_use: "Any file under frontend/src/."
user-invocable: false
model: sonnet
---

# Skill: TypeScript — Angular 18 Frontend

Verified 2026-08-04: `@angular/core ^18.2.0`, **0** `NgModule`, **8** `standalone: true` components,
Signals in real use (`signal(` ×5, `computed(` ×3, `inject(` ×12). The standalone + Signals
convention is real here, not aspirational — hold the line on it.

## Structure

```
frontend/src/app/
  core/services/      # orchestrator.service, config.service, conversation store, theme
  features/chat/      # chat-page, message list, bubble, thinking-indicator, input
  shared/             # reusable UI
```

REJECT if:
- An `NgModule` is introduced — the app is 100% standalone
- `any` where a real type exists (backend contracts are Pydantic models; mirror them as interfaces)
- Transport or business logic inside a component — it belongs in `core/services/`
- An `EventSource` / subscription created without teardown on destroy
- The backend base URL is hardcoded — it comes from `environment.orchestratorBaseUrl`
- `console.log` left in committed code

REQUIRE:
- Signals (`signal`, `computed`, `effect`) for component state; no ad-hoc `BehaviorSubject` for
  local UI state
- `inject()` over constructor injection in new code
- User-facing strings in Spanish
- Signals-driven, `OnPush`-compatible code; no manual `ChangeDetectorRef.detectChanges()` hacks

PREFER:
- `@if` / `@for` control flow over `*ngIf` / `*ngFor`
- Typed reactive forms
- Small presentational components; state stays in the conversation store

## Transport — read this before touching the stream

`OrchestratorService.streamResponse()` picks its transport from `environment.transportMode`
(`'sse' | 'polling'`), at config time. Both backend routes now exist:
`GET /chat/stream/{request_id}` (SSE) and `GET /chat/status/{request_id}` (cumulative polling).

**Do not add an automatic SSE→polling `catchError` failover.** A `request_id` is consumed by the
first transport that claims it; once SSE has taken it, a polling retry gets a 404. A real failover
needs a new `request_id`, i.e. re-posting the message — decide that deliberately, not as a
`catchError`.

Polling contract: `{ status: 'running' | 'done' | 'error', steps: AgentStep[], final?, error? }`.
`steps` is **cumulative** — the client keeps a `seenStepCount` and slices off what it already
rendered. The client must stop polling on `done` or `error`; the backend guarantees a terminal
status even when the agent produces no final message (`NO_FINAL_RESPONSE`).

## Environment

`frontend/src/environments/environment.ts` — real keys:
`production`, `orchestratorBaseUrl` (`http://localhost:8000`), `chatEndpoint` (`/chat`),
`streamEndpoint` (`/chat/stream`), `agentName` (`SAPE`), `agentTagline`, `agentAvatarInitials`,
`transportMode`, `pollingIntervalMs`, `requestTimeoutMs`.

Add new config here rather than inlining constants in services.

## Commands

```bash
cd frontend && npm start        # dev server :4200
cd frontend && npm test         # ng test (Karma)
cd frontend && npm run build    # outputPath: dist/frontend  (angular.json:20)
```

`angular.json` declares `"outputPath": "dist/frontend"`. The Angular 18 application builder emits
the browser bundle into a `browser/` subfolder underneath it — so deployment artifacts land at
`dist/frontend/browser/`. Do not change `outputPath` without updating the deployment target.
