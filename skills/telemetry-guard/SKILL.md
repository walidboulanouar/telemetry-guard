---
name: telemetry-guard
description: Audit local optional vendor telemetry and remote sharing, reversibly disable supported analytics settings, and check owned services for private Tailscale access. Use for an app audit, local open-app and settings survey, telemetry opt-out, or personal-device access review.
---

# Telemetry guard

Use only local evidence. No provider queries carrying local data, uploads, packet capture, remote scans, remote agent changes, new dependencies, monitor/firewall installation, broad domain blocking, or security/audit/EDR/SIEM/incident-log suppression. Never promise zero egress or a complete inventory. Preserve requested functions, local dashboards and approved model routes. External model calls, update checks, confirmed optional analytics and unknown traffic are separate findings.

## Choose scope

- “Audit this app”: identify the named installed product/version from its bundle manifest or trusted installed help, then inspect only the documented control. Don't read arbitrary files, logs, histories, credentials, environments, process arguments or raw user content. A settings file may be parsed locally to project allowlisted scalar controls; never expose the rest to a model.
- “Audit this host”: run the host survey. On macOS it lists open regular GUI apps and separately lists accessory apps installed directly in Applications. It uses AppKit locally, retaining only display names, app roles, the snapshot time and a match to a supported settings control. Nested helpers and other services are outside this inventory. A separate section checks stable VS Code user settings and the saved Chrome stable usage statistics and crash-reporting preference on macOS. Chrome is read-only. Its saved preference does not establish effective policy or upload activity. The survey reports Next.js as unknown until its installed-version settings location is confirmed. An open app with no check is unassessed. Missing controls and unavailable inventories remain unknown.
- “Disable confirmed optional telemetry”: read [settings.md](references/settings.md), make a scoped plan, obtain authorization for the exact setting immediately before applying, then verify and retain local undo state. Building/testing the skill grants no live settings authorization.
- “Only my personal devices through Tailscale”: read [tailnet.md](references/tailnet.md). App auth, loopback binding, tailnet policy and device ownership all matter. Same login does not establish ownership. If policy/browser/device proof is missing, report partial verification and stop before making a sole-access claim.

## Offline helper

Use installed Python 3, standard library only. Set `GUARD` to this skill's `scripts/guard.py`. Choose a fresh output directory under a private local temporary directory created with `umask 077; mktemp -d`; do not use synced/shared folders. On macOS, canonicalize the newly created private temporary directory with `PRIVATE_DIR=$(cd "$PRIVATE_DIR" && pwd -P)` before use: `/var` and `/tmp` aliases are symlinks and are deliberately refused. Do not resolve an arbitrary preexisting settings symlink to bypass the refusal. Do not print full paths, commands with secrets, subprocess output, config contents or environments to models.

```sh
python3 "$GUARD" audit --app host --out "$PRIVATE_DIR/report"
python3 "$GUARD" audit --app vscode --out "$PRIVATE_DIR/app-report"
# A confirmed, explicitly chosen Next.js settings file:
python3 "$GUARD" audit --app nextjs --settings "$SETTINGS" --out "$PRIVATE_DIR/next-report"
```

The CLI returns counts and status for audits. Host reports also contain local app display names. Keep `summary.json` and `summary.html` private and review them before sharing. The inventory excludes window titles, URLs, bundle paths, process arguments and account data. App-specific reports skip the open-app inventory. Transaction JSON is **local-only sensitive**: it includes the settings path, hashes and prior allowlisted value. Never ship transactions/backups in a report or skill. The helper changes only the existing control token. Unrelated bytes, including numeric values and whitespace, stay intact. Undo restores the previous scalar value. No whole-file backup is made. Preserve undo state until accepted; delete it only with authorization.

The helper rejects symlinks, non-owned files, malformed/duplicate JSON, unexpected value types, unsupported JSONC and changed settings. Close/stop the app's config writer only with authorization before an edit; it does not coordinate with arbitrary app writers. Its operating-system lock covers the settings directory and is released when the helper exits. Other apps may still write independently. Do not retry blindly: a conflict requires rereading the allowlisted control and a fresh plan; I/O errors require local diagnosis without raw stderr. There are no automatic retries.

For arbitrary apps and unsupported versions, find installed documentation and version evidence first. Use official public documentation only without any local data in queries. No invented keys, silent fallback adapters, changing unknown controls, or disabling shared services. Browser consent/cloud sharing and daemons require separate checks; a desktop flag does not establish their state. Use [settings.md](references/settings.md) for the verification matrix.

## Verification and scope limits

Run `python3 scripts/test_guard.py` after helper changes. The settings writer targets macOS and Linux. The regression suite exercises disposable settings on macOS and Linux, including permission modes and extended attributes. Reports use POSIX private directory and file permissions. Windows VS Code path selection exists, but helpers refuse output/mutation there until user-only ACLs and atomic primitives have a tested adapter; use the documented app UI and PowerShell observables instead. Strict JSON only; VS Code JSONC, enterprise policy, profiles, extensions, remote hosts, containers and browser consent are guided. Next.js requires an installed-version-confirmed explicit Conf file with an existing boolean `telemetry.enabled`; CI/environment-only controls are guided. Tailnet changes are deliberate documented CLI steps, not an automatic broad reset.

Example invocation: `$telemetry-guard audit this app: VS Code, read-only` or `$telemetry-guard disable confirmed optional telemetry for this Next.js installation; show me the scoped plan first` or `$telemetry-guard check this owned dashboard is accessible solely by my confirmed personal devices through Tailscale`.
