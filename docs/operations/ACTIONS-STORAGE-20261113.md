# Actions artifact storage maintenance — 13 November 2026

Dani explicitly authorised account-wide Actions storage cleanup and direct workflow optimisation on 2026-11-13. This is bounded CI maintenance; no product feature, database, installed application, agent runtime, architecture implementation, paid upgrade or budget increase is authorised by this change.

## Business rule

Temporary Actions outputs expire after **3 days**. Installers intended for long-term use belong in Releases; source, tags, published release assets and important acceptance evidence must be preserved. The repository-wide retention setting is not shortened because it also governs workflow runs, checks and statuses.

Workflow: `.github/workflows/ci.yml`.
Baseline commit: `4057c17a2fa7cb5725375e92097bf79f40f0f278`; original workflow blob: `c780adc7f00d3ac11ae8af8ad2bf5def9999eb33`.

Existing build/test jobs, matrices, commands, artifact names and paths, same-run downloads, deployment conditions and signing configuration are preserved. All existing jobs were compared structurally after removing only the retention value; the GVML release guard is the documented exception below.

The existing release publication contract is retained.

## Verification and rollback

Local YAML parsing and semantic checks passed for all 12 maintenance workflows / 16 upload steps. Existing test/build jobs and same-run consumers remain equivalent; new release gates and checksum steps are checked. This is static workflow validation, not a new APK/device, IIS, WordPress production or Orca GUI acceptance claim. Check the CI run associated with the applied commit for runtime evidence; failure must not be called a passing build.

Rollback: restore the original workflow blob above in a new commit after checking the current branch. Do not reset history, remove Releases or restore an old production database. The local account inventory and installer backup receipts are retained under outputs/github-storage-20261113 in the authorised operator workspace; no credentials are included in repository evidence.

Keep future upload-artifact steps at 3 days. A justified diagnostic extension may use at most 7 days and must state why. Avoid uploading broad build directories or duplicate installed dependencies. Use same-run artifacts for job transport and Releases for durable product retrieval. Concurrent large builds can still exceed 500 MB; a retention period is not an account-wide byte reservation. Billing's included-storage display is not an exact live artifact-byte measurement.
