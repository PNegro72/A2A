---
name: code-javascript
description: "JavaScript standards for React, Node.js, and frontend projects (no TypeScript-specific rules)."
when_to_use: "When writing or reviewing *.js or *.jsx files."
user-invocable: false
model: sonnet
effort: medium
hub-skill-ids: [implementation, review, refactoring]
---

# Skill: JavaScript

## Rules

REJECT if:
- `var` keyword used (use `const` or `let`)
- `==` used instead of `===` for equality checks
- Default exports (use named exports)

```javascript
// REJECT
export default function getData(x) {
  var result = x == null ? [] : x
  return result
}
```

REQUIRE:
- Named exports for all modules
- JSDoc `@param` and `@returns` on exported functions when types are non-obvious

```javascript
// REQUIRE
/**
 * @param {string[]} input
 * @returns {string[]}
 */
export function getData(input) {
  return input.filter(Boolean)
}
```

PREFER:
- `const` over `let`; never `var`
- Functional React components over class components
- `async`/`await` over `.then()` chains
- Nullish coalescing (`??`) over `||` for default values

```javascript
// PREFER
const timeout = config.timeout ?? 5000

async function fetchUser(id) {
  const res = await api.get(`/users/${id}`)
  return res.data
}
```
