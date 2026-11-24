# Supported settings and reversible operation

## Evidence before planning

Record product family, installed version and documentation provenance as short non-identifying notes. Read bundle metadata for VS Code instead of launching arbitrary executables; don't invoke unknown package-manager commands. Read only installed documentation/known CLI help, with stdout/stderr retained locally and projected to needed facts. Never dump subprocess failures. Do not invoke a repo's npm scripts or use npx. No repository edits are needed.

VS Code documents `telemetry.telemetryLevel` values `all`, `error`, `crash`, `off`; `off` opts out of its optional product telemetry and crash reporting. Reference: https://code.visualstudio.com/docs/configure/telemetry . Stable user settings paths are selected per OS by the helper. Insiders, VSCodium, enterprise policy, extension analytics and remote settings require separate documentation. JSONC is common: use the app's Settings UI to change the exact control and record a minimal prior scalar locally, or request a separate tested JSONC adapter. Never strip comments with regex or replace the whole file blindly.

Next.js documents `next telemetry status/disable/enable` and `NEXT_TELEMETRY_DISABLED=1`: https://nextjs.org/telemetry . Its Conf storage representation in supported versions is nested `{"telemetry":{"enabled":false}}`. Confirm this against the installed `next/dist/telemetry/storage` implementation and its installed Conf version/path resolution, without printing contents or unique identifiers. Select the actual file explicitly; do not guess locations, create it, change `telemetryId`/salt, or assume all versions use the same location. Existing boolean required. Absent controls, read-only installs, CI and environment overrides are guided. Never inspect environment values; ask whether an override is intentionally managed. This opt-out does not change application analytics integrations or model endpoints.

## Plan, apply, verify, undo

Set local variables to the confirmed file and private directory without exposing them. The commands below run actual deterministic adapters, not arbitrary shell templates:

```sh
python3 "$GUARD" plan --app vscode --settings "$SETTINGS" --out "$PRIVATE_DIR/change"
# Or --app nextjs, after installed-version/storage evidence.
# Review projected plan and get authorization for this exact control.
python3 "$GUARD" apply --transaction "$PRIVATE_DIR/change/transaction.json" --authorized
python3 "$GUARD" audit --app vscode --settings "$SETTINGS" --out "$PRIVATE_DIR/after"
# Undo only when authorized:
python3 "$GUARD" undo --transaction "$PRIVATE_DIR/change/transaction.json" --authorized
```

Apply checks the planned whole-file hash and replaces only the existing JSON scalar. It keeps the settings file’s permission mode and copies supported access metadata. It refuses read-only or multiply linked settings files. Reports and journals are created with mode 0600. Apply and undo both journal the expected resulting hash before changing settings. If interrupted in `applying` or `undoing`, an authorized undo can recover either the previous or the matching written state. Never hand-edit journal hashes. Full-file divergence refuses undo even if unrelated, preserving newer work. Re-plan/reconcile locally after explicit review, never force overwrite. Directory symlinks are refused. The operating system releases the directory lock when the process exits. An old-version lock file is honored; establish whether that older helper is still active before any manual cleanup. Atomic writes reduce corruption but cannot guarantee isolation from an app concurrently rewriting its settings; close its writer first. On Windows, confirm the private directory has user-only ACLs; POSIX modes alone are not an ACL guarantee.

## Verification matrix and sharing

1. Re-read the allowlisted control after apply; restart only with authorization and recheck after normal startup. A persisted setting is not network-flow proof.
2. For signed-in/browser features, inspect the product's documented privacy/sharing UI without reading account identity, content, tokens or browser databases. Check the named signed-in profile as well as signed-out behavior when applicable, with user participation. Record only control name/state and test status. Do not change account-wide sharing merely because local telemetry was requested.
3. Check the separately documented daemon control when a daemon exists. Desktop and daemon settings are independent; if no documented control/evidence exists, mark daemon unknown. Don't dump launch/service environments or arguments.
4. Cloud sharing is guided: distinguish existing public links, link audiences, automatic uploads/sync and collaboration. Confirm the exact resource and required function with the user, record prior audience locally, revoke only that resource/optional upload control using the app UI, verify with an unauthenticated browser and approved authenticated persona, and restore that prior audience only if rollback is authorized. Don't open raw content, enumerate remote accounts or query providers with local data. If these checks need prohibited provider access, report untested and have the user perform them. Neither supported settings adapter disables cloud sharing.
5. Classify separately: confirmed optional analytics setting; required/approved external model request; update check; unknown flow. Never reclassify a domain as telemetry solely because it is external. Preserve security and incident logging.

Report product, control, before/after state, evidence type, test status and uncovered surfaces, using enums where possible. No peer names/IPs, account identifiers, full paths, raw logs, config values outside the control or local transaction data belong in shareable summaries. Safe unknown is preferable to invented coverage.

## Optional trace/crash exporters outside the adapters

VS Code's `off` covers its documented optional product telemetry/crash reporting, not arbitrary crash agents. For a named app's trace exporter, first establish from installed-version documentation that the export is optional product diagnostics, which component owns it (browser, desktop or daemon), its exact destination/control and the documented prior/default behavior. Do not enumerate environment values to find endpoints, inspect trace bodies, or assume OpenTelemetry/Sentry/SIEM controls are optional. A trace/export setting with security, audit, incident, compliance or unknown purpose is out of scope for mutation.

For a confirmed optional exporter, make a guided change record containing only control name, scalar prior/new state, documented scope, expected restart and supported undo action. Obtain authorization; use the documented app UI or exact local setting with an app-specific tested adapter, not a generated arbitrary shell command. Keep local tracing/dashboard behavior and approved model routes intact. Re-read only the control, verify the separate browser/daemon surface if it owns the exporter, and use the app's documented diagnostics-status screen rather than capturing payloads. If the control also disables required local observability or its undo is unknown, stop at a finding. This skill ships no automated exporter adapter beyond the two products listed above.
