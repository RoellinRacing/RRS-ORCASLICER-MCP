---
name: release-review
description: Automatically use for PR reviews, final acceptance, GitHub Actions results, packaging, deployment, publication and rollback planning.
---
# Release and acceptance gate
1. Identify exact authorisation, branch, base/head commits, target version, artifacts and acceptance checklist. An external reviewer (e.g. Claude) is not an implied deployment permission.
2. Verify code diff, security boundary, business-rationale documentation, tests and immutable provenance of built packages. Compare actual published/downloaded bytes to source where requested.
3. Distinguish planned, built, CI passed, reviewed, merged, released, deployed and production-verified states. Never collapse them into a single success flag.
4. Publication, customer messages, site changes and monetary operations require an explicitly scoped mandate and protected secrets. Never install or enable reach through a release job.
5. Record commit SHA, artifact digests, test run links, limitations, rollback step, last successful step and next step.
Business reason: protects customers and reputation when switching builders, supervisors or reviewers.
