# Summary Notes: Integrated AI Engineering Skills

We recently integrated a comprehensive suite of AI Engineering skills (from the `skills-AIMattPoc` repository) into your local development environment. These skills act as intelligent sub-agents that follow disciplined, well-documented workflows to help you build, test, and maintain high-quality software.

Below is a categorized summary of the newly added skills most relevant to **Software Development**, **Testing**, and **Deployments / GitOps**.

---

## 🏗️ Software Development & Architecture

These skills focus on planning, writing code, improving structure, and prototyping.

- **`improve-codebase-architecture`**: Deepens the codebase architecture by finding refactoring opportunities, consolidating tightly-coupled modules, and making the codebase more testable and AI-navigable. It aligns changes with the project's domain language and architectural decision records (ADRs).
- **`request-refactor-plan`**: Creates a highly detailed refactoring plan broken down into tiny, safe commits via an interactive user interview, then automatically files it as an issue/RFC.
- **`prototype`**: Builds throwaway prototypes to flesh out a design before committing to it. It can build a runnable terminal app for testing business logic, or generate several radically different UI variations you can toggle between.
- **`design-an-interface`**: Generates multiple radically different API/interface designs in parallel, allowing you to explore and compare module shapes before implementation.
- **`ubiquitous-language`**: Extracts a Domain-Driven Design (DDD) style ubiquitous language glossary from conversations. It flags ambiguities, proposes canonical terms, and saves them to a standard `UBIQUITOUS_LANGUAGE.md` file.
- **`zoom-out`**: Provides broader context and high-level perspective when you're unfamiliar with a section of code or need to understand how components fit together globally.

---

## 🧪 Testing, Quality Assurance & Review

These skills enforce quality, track down bugs, and ensure test coverage.

- **`tdd` (Test-Driven Development)**: Executes a disciplined red-green-refactor loop. It asks you for requirements, writes failing tests first, implements the minimum code to pass them, and then refactors.
- **`diagnose`**: Runs a rigorous diagnosis loop for hard bugs and performance regressions: Reproduce → Minimise → Hypothesise → Instrument → Fix → Regression-test. 
- **`qa` (QA Session)**: Facilitates an interactive QA session where you report bugs or issues conversationally. The agent explores the codebase in the background for context and files accurate GitHub issues.
- **`review`**: Reviews changes since a fixed point (commit/branch/merge-base) along two axes in parallel: 
  1. **Standards**: Does it follow the repo's documented coding standards? 
  2. **Spec**: Does the code match the originating PRD/issue requirements?
- **`migrate-to-shoehorn`**: A specialized utility skill that migrates test files away from unsafe TypeScript `as` type assertions to `@total-typescript/shoehorn` for better mock data handling.

---

## 🚀 Deployments, GitOps & Project Management

These skills handle repository safety, commit hygiene, and translating ideas into actionable tickets.

- **`setup-pre-commit`**: Sets up Husky pre-commit hooks with `lint-staged` (Prettier), type checking, and tests in the current repository to ensure no broken code gets committed.
- **`git-guardrails-claude-code`**: Installs safety hooks to block dangerous git commands (e.g., `push --force`, `reset --hard`, `clean`, `branch -D`) before they execute, preventing destructive repository operations.
- **`to-prd`**: Turns the current conversational context and ideas into a formal Product Requirements Document (PRD) and publishes it to the project's issue tracker.
- **`to-issues`**: Breaks down a plan, spec, or PRD into independently-grabbable issues using tracer-bullet vertical slices.
- **`triage`**: Triages issues through a state machine. It helps review incoming bugs or feature requests, prepare issues for execution, and manage workflow.

---

> [!TIP]
> **How to trigger them:** You can trigger any of these skills naturally in conversation (e.g., *"Let's do some TDD on this feature"* or *"I need to diagnose a performance regression"*) or you can mention them directly by name.
