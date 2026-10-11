[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/11 15:48:37.050848 )
[//]: # (+ Revised: 	2026/10/11 17:36:52.358334 )
[//]: # ( ---------------------------------------------------------------------- )

Thank you for your interest in contributing.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)
- [Submitting Changes](#submitting-changes)
- [Backlog](#backlog)
- [Commit Style](#commit-style)
- [License](#license)

---

## Code of Conduct

We expect all contributors to treat each other with respect. Harassment, discrimination, and bad-faith participation of any kind will not be tolerated.

---

## Reporting Bugs

Open an issue and include:

- A clear, descriptive title
- Step-by-step reproduction instructions
- Expected behaviour vs. actual behaviour
- Your environment (OS, relevant versions)

---

## Suggesting Features

Open an issue and include:

- The problem you are trying to solve
- Your proposed solution
- Alternatives you considered

---

## Submitting Changes

1. Fork the repository
2. Branch from `main`
3. Make your change
4. Commit following the style below
5. Open a pull request against `main` and describe *why* the change is needed

One concern per PR — do not bundle unrelated changes.

---

## Backlog

Planned work lives in [TODO.md](TODO.md), one self-contained item each, in priority order (first = next).

---

## Commit Style

Commits use a bracketed title line followed by a Conventional Commits body.

**Bracket table:**

| Bracket | Conventional type | Meaning |
|---------|-------------------|---------|
| `[A]` | `feat` | New feature |
| `[F]` | `fix` | Bug fix |
| `[R]` | `refactor` | Refactor — no behaviour change |
| `[D]` | `docs` | Documentation only |
| `[T]` | `test` | Add or update tests |
| `[C]` | `chore` | Maintenance, tooling, housekeeping |
| `[P]` | `perf` | Performance improvement |
| `[B]` | `build` | Build system or dependency change |
| `[S]` | `style` | Formatting — no code meaning change |

**Rules:**

- Title line: `[BRACKET] Short description` (≤ 72 chars, no trailing period)
- Body: Conventional Commits style with a lowercase imperative verb (`feat: add …`, `fix: handle …`); scope is optional
- Breaking changes: `feat!` / `fix!` in the body or a `BREAKING CHANGE:` footer
- Reference issues with `Closes #N` or `Refs #N` in the body

---

## License

This project is distributed under the [PayBack License (PBL)](LICENSE).

Contributing does not transfer copyright. Non-trivial contributions may entitle contributors to a revenue share, subject to being listed in `CONTRIBUTORS` and a quorum vote among existing contributors.

Personal and non-commercial use is free. Commercial use requires a revenue-share agreement per the PBL terms.
