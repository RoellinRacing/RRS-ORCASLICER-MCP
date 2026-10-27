---
name: engineering
description: Automatically use for programming, bug fixes, refactoring, MCP tools, WordPress plugins, C# healthcare systems, 3D printing integrations and CLI development.
---
# Engineering with reusable checkpoints and business logic
1. Read local AGENTS.md/CLAUDE.md, active authorization/STOP, README, STATUS or WORK_STATE, the owner task, source and prior accepted commits. Repository-local safety and permission rules take precedence.
2. State the product behavior and WHY before HOW: affected customer workflow, invariant, permission boundary, idempotency/rollback, integration limitations, compatibility and operational costs. Store it alongside source in docs/BUSINESS_LOGIC.md or a scoped design note.
3. Work in small resumable slices. Save generation scripts/configuration BEFORE expensive builds or experiments; never recreate successful artifacts on restart.
4. Write source, tests, regression checks, business-rationale update and exact evidence in the SAME change. Run only relevant validations first; use review/CI gates for broader scope.
5. Never claim unrun tests passed or a remote agent deployed. Never widen credentials, provider billing, patient access, production release permissions or machine privileges from a Skill.
6. For each finished slice save files, real outputs, test command/results, commit SHA, last success, blocker and next step. Check STOP and re-read branch before any resumed write.
Business reason: prevents fragile handoffs and makes the project understandable after changing AI agents or tool versions.
