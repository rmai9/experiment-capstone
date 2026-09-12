# Contributing Guidelines (CSE120 Student Repository)

> Adapt this file only if instructed. It encodes the expected workflow for this course.

## Workflow Overview
1. Open an Issue for every distinct unit of work (lab task, feature, bug, refactor, research).
2. Create a branch from `main` named after the Issue: `<type>/short-kebab` (e.g., `feat/auth-endpoints`).
3. Commit changes incrementally with semantic commit messages.
4. Open a Pull Request early (draft) and link the Issue.
5. Request peer review (if required) before merging.
6. Squash merge or rebase to keep `main` linear (unless told otherwise).

## Semantic Commit Messages
Format:
```
<type>(optional scope): <imperative summary>
```
Allowed types:
- feat: new functionality
- fix: bug fix
- docs: documentation only
- style: formatting / lint (no logic)
- refactor: code restructuring w/o behavior change
- test: add or modify tests only
- chore: tooling / maintenance
- perf: performance improvement
- build: build system changes
- ci: continuous integration changes

Examples:
```
feat(auth): add login and token refresh endpoints
fix(api): handle empty search results gracefully
test(search): add pagination edge cases
refactor: extract validation helpers from handlers
```
Body (optional) should explain rationale, constraints, trade-offs. Reference Issues:
```
Closes issue 12
```

## Pull Requests
A PR should include:
- Clear title (semantic)
- Linked Issue(s)
- Summary of approach
- Testing evidence (commands + output snippet)
- Risks / potential regressions
- Checklist completion

### PR Checklist (Keep in Template)
- [ ] Follows semantic title
- [ ] Issue linked
- [ ] Builds / compiles locally
- [ ] Tests pass / added
- [ ] Docs updated
- [ ] No debug artifacts committed
- [ ] Reviewer(s) assigned (if required)

## Issue Labels
| Label | Purpose |
|-------|---------|
| Bug | Defect in existing code |
| Feature | New capability or enhancement |
| Task | Maintenance, refactor, docs, infra |
| Documentation | README / wiki / design-doc change |
| Discussion | Design / conceptual thread |

## Coding Practices
- Prefer clarity first; optimize only with justification.
- Add function/module doc comments: purpose, inputs, outputs, error modes, side effects.
- Handle error paths explicitly; avoid silently swallowing exceptions.
- Keep configuration (env vars, endpoints) externalized; never hardcode secrets.
- Make concurrency explicit (threading, async boundaries, shared-state access).
- Add tests for boundary cases: empty input, max capacity, invalid input, error paths.

## Testing Expectations
Write tests as you implement features. Cover the critical user flows and the API
contract. If your stack has a test runner, wire it into CI so the suite runs on
every PR.

## Academic Integrity
Do not copy full solutions. You may:
- Discuss high-level design strategies.
- Cite external references (papers, docs) in `docs/research/`.
You must not submit code you did not author (unless provided by instructor).

## Communication Patterns
Use Issues for traceability. Use Discussions or `Discussion` Issues for
architectural debates; summarize decisions in the Issue before closing.

## Tooling Suggestions (Optional)
If allowed, you may configure:
- Formatter (black, prettier, eslint, gofmt, etc.)
- Linting (ruff, eslint, golangci-lint, etc.)
- Pre-commit hooks for formatting / test runs

## Merging Strategy
Default: squash merge. Ensure final squash commit message follows semantic format.

## Handling Large Changes
Break into: data layer, core logic, integration, tests. Submit sequential PRs each
building on the last to reduce review load.

## Security / Safety
Never commit secrets, API keys, or private test data. Treat input as untrusted in
user-facing endpoints. Keep `.env` files out of version control.

---
Questions? Open a `Discussion` Issue before proceeding with uncertain design choices.
