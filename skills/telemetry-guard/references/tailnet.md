# Owned service, tailnet-only access

This is a guided workflow using the installed Tailscale CLI and app documentation. Never act on other machines, scan networks, enable SSH/T3 Connect, reset Serve globally, change unrelated services or infer ownership from account login. macOS/Linux commands below require installed Tailscale; Windows uses the installed `tailscale.exe` plus PowerShell's `Get-NetTCPConnection`. Installed `tailscale serve --help`, `tailscale funnel --help` and their `status --help` take precedence over these current syntax examples. Read help locally without user data. Unsupported syntax means stop and adapt from installed documentation, not guess.

## Gate and plan

Before any T3 service access change, search **filenames only** in installed skill roots (`~/.codex/skills`, `~/.agents/skills`, `~/.claude/skills` and their documented library links) for T3/access-gate guidance. Read the applicable installed T3 gate, including its referenced local instructions, and obey it; if the gate cannot be located/resolved or authorization is unclear, stop T3 mutation and report the missing gate. Do not embed machine IDs, policy IDs or private addresses in this reusable skill. A general Tailscale login never overrides a T3 gate.

Obtain exact local app, port, required paths, documented bind option, existing app-auth behavior, and user-confirmed device ownership. Have the user privately confirm exact source node identities from their device inventory. Do not infer “personal” from a tag, owner email or the same login. Keep node IDs/address policy and existing route snapshots **local-only** in a 0700 directory, 0600 files/user-only ACLs. Do not feed their raw contents to a model.

Inspect current local configuration with stdout/stderr redirected to private files:

```sh
tailscale serve status --json > "$PRIVATE_DIR/serve-before.json" 2> "$PRIVATE_DIR/serve-error"
tailscale funnel status --json > "$PRIVATE_DIR/funnel-before.json" 2> "$PRIVATE_DIR/funnel-error"
```

Status inspection itself must not change configuration. Project only booleans/counts: service route present, target loopback, public Funnel enabled, unrelated routes present. Do not paste raw status, peer inventory, cert paths or errors. A local human may inspect the private snapshot. Invalid/nonzero output is unknown; don't publish a traceback. Avoid `tailscale status --json` because it collects peer identities unnecessary for a local Serve check. Don't run `tailscale up`, login, install, broad `reset`, `serve reset`, or blindly enable anything.

Verify origin via app documentation and a **port-scoped local** observable, no process arguments:

```sh
# macOS: keep output local; report only loopback-only / wildcard / unknown.
lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -Fn > "$PRIVATE_DIR/listener" 2> "$PRIVATE_DIR/listener-error"
# Linux, no -p/process data:
ss -H -ltn "sport = :$PORT" > "$PRIVATE_DIR/listener" 2> "$PRIVATE_DIR/listener-error"
# Windows (local PowerShell), select only address state:
Get-NetTCPConnection -LocalPort $Port -State Listen | Select-Object LocalAddress,LocalPort
```

Do not print Windows output into the model; reduce it locally to loopback-only/wildcard/unknown. Inspect IPv4 **and** IPv6 listeners; `0.0.0.0`, `::`, LAN and tailnet-address bindings fail loopback-only. An empty result is unknown/down, not safe. A loopback HTTP origin is acceptable only with app auth and private Serve TLS. Do not send tokens in command arguments. Validate app authentication in a browser as unauthenticated and authorized sessions without reading content or identities; record only denied/allowed. Test WebSocket/API auth as applicable. If binding/auth changes require a live restart, obtain authorization for that exact change and preserve local dashboard access.

## Personal-device-only policy

Serve makes a service available to the tailnet under applicable policy; it does **not** by itself restrict access to personal devices. Review existing grants/ACLs locally with the policy owner. An additive restrictive rule cannot cancel a broader allow. Without inspecting all applicable broad user/group/tag/auto-approver/share rules and proving the resulting policy limits the exact destination port to the user-confirmed source nodes, the result remains **tailnet-accessible, personal-device-only unproven**.

Do not globally edit policy in this skill. The owner must approve the exact minimal policy delta, preserve unrelated service access, run the admin console policy tests including a confirmed allowed node and an excluded node, then provide a scrubbed result. Exact IP/node selectors must follow the installed/current policy documentation; identities/selector values stay local. Same-user devices, shared nodes and tagged servers require explicit ownership and policy review. Browser sessions from the origin host alone cannot prove remote restrictions. If no excluded-device test is available, record that limit and do not claim sole access.

## Apply, verify and undo a single owned route

Only after app auth, loopback origin, exact-node policy and gate pass, review a plan containing route port/path, previous route present/absent, Funnel state and preservation of other routes. Obtain authorization immediately before a live change. If the desired route/HTTPS port is already used, stop for reconciliation. Do not overwrite it. On supported versions, an unused dedicated HTTPS port can be configured as:

```sh
# PORT is the confirmed loopback origin; HTTPS_PORT is an unused supported Serve port.
tailscale serve --bg --https="$HTTPS_PORT" "http://127.0.0.1:$PORT"
# Read-only verification, retained locally:
tailscale serve status --json > "$PRIVATE_DIR/serve-after.json" 2> "$PRIVATE_DIR/serve-error"
tailscale funnel status --json > "$PRIVATE_DIR/funnel-after.json" 2> "$PRIVATE_DIR/funnel-error"
```

Do not use Funnel to enable anything. If Funnel already exposes this port, treat it as a confirmed public-sharing finding: obtain authorization to remove **that port only**, using installed help (typically `tailscale funnel --https="$HTTPS_PORT" off`), then verify it is absent. Preserve other routes and report any other exposure without changing it. Merely running Serve is not proof that existing Funnel is gone. Serve TLS certificate issuance may itself use the Tailscale control plane; do not claim offline/zero egress.

After apply, compare private before/after state for unrelated routes, repeat local IPv4/IPv6 listener and app-auth checks, confirm named route is loopback-targeted and no Funnel/public route exists for it, and have the user test the service from the exact approved personal device plus a confirmed excluded tailnet device. Test unauthorized application sessions on allowed nodes too. Public denial tests must be user-driven browser checks of the already known service, never network scanning. Record a concise pass/fail/untested matrix, no names, IPs or URLs.

Undo only the newly created route, after authorization and confirming its current state still equals the planned result. Installed-help-supported example:

```sh
tailscale serve --https="$HTTPS_PORT" off
```

This example is appropriate only for a dedicated initially unused HTTPS port, never a shared port/path. If any route has changed since apply, stop; no blind replay, no global reset, no automatic retries. A preexisting route or policy change requires an owner-reviewed exact restoration instead. Keep private snapshots only as needed for rollback; never distribute them. This skill has no automated tailnet policy mutation or device-ownership detector. Access guarantees require all checks above; report missing evidence precisely.
