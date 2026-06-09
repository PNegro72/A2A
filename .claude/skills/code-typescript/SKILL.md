---
name: code-typescript
description: "TypeScript-specific standards. Layers on top of code-javascript rules where applicable."
when_to_use: "When writing or reviewing *.ts or *.tsx files."
user-invocable: false
model: sonnet
effort: medium
hub-skill-ids: [implementation, review, refactoring]
---

# Skill: TypeScript

Note: TypeScript files also follow all `code-javascript` rules. This skill adds TS-specific requirements on top.

## Rules

REJECT if:
- `any` used without `// @ts-expect-error` and a justification comment
- Missing explicit return types on exported functions and React components
- Runtime imports of types (use `import type` for type-only imports)

```typescript
// REJECT
import { User } from "./types"  // type-only — should be `import type`

export function getUser(id: any) {  // any without justification
  return repo.find(id)             // missing return type
}
```

REQUIRE:
- `strict: true` in `tsconfig.json`
- Explicit return types on all exported functions and React components
- `import type { ... }` for type-only imports

```typescript
// REQUIRE
import type { User } from "./types"

export function getUser(id: string): User | null {
  return repo.find(id)
}

export const UserCard = ({ user }: { user: User }): JSX.Element => (
  <span>{user.name}</span>
)
```

PREFER:
- Discriminated unions over loose `string` enums
- `readonly` on properties and arrays that should not mutate
- `unknown` over `any` when the type is genuinely uncertain

```typescript
// PREFER
type Result =
  | { kind: "ok"; value: string }
  | { kind: "err"; error: Error }

function handle(r: Result): string {
  return r.kind === "ok" ? r.value : r.error.message
}
```
