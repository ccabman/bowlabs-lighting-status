# BowLabs Lighting Status — private installation candidate 0.1.0

A separate Home Assistant custom integration for an explicitly approved, read-only
summary of BowLighting's existing local diagnostics. It does not replace
BowLighting or change the Mac-only `bowlabs_status` integration.

This candidate has been installed and tested only in disposable HA 2026.10.2 on
Python 3.14 with synthetic sensor entities. No household installation or service
restart is authorized by this artifact. This new domain now passes its own Linux
CI and official hassfest validation. Full HACS validation is blocked: the official
action refuses this private repository. It has not been made public.

Validated code: `8f67d7291231106222853a0fdd7e2c646736d6c0` in
[run 39716229408](https://github.com/ccabman/bowlabs-lighting-status/actions/runs/39716229408).
The aggregate workflow is red solely because HACS rejects private repositories;
the Linux and hassfest jobs pass. No HACS success is claimed. The manifest now
points to this standalone repository rather than the separate Mac pilot.

## Scope and approval

1. Add **BowLabs Lighting Status** from Settings → Devices & services.
2. Select 1–32 BowLighting zone **Status** sensors and the **Active alerts** sensor.
3. Review the exact selection and check the read-only approval checkbox.

The integration verifies registry ownership, source config-entry identity and the
expected diagnostic unique IDs; arbitrary sensors, targets, light entities,
duplicate selections and swapped zone/alert roles are refused. It reads no source
state before approval. It does not import or activate the BowLighting controller.

Approval is stored in this integration's native config entry and persists until
explicitly revoked. This deliberately differs from the temporary ten-minute leases
in the earlier host experiment; the setup screen states the lifetime before
approval. There is no shared Mac/TV credential, network listener, remote token,
Concierge connection, service call, audio, media or personal-library capability.

One diagnostic sensor exports coarse operating/readiness labels and bounded zone,
hold, alert, override and issue counts. Full attributes, selected light IDs, room
names, hold records, restoration details and raw errors are excluded. Its evidence
is application-reported HA state, not independent physical verification. In the
lab the underlying HA application is a synthetic fixture, never the real controller.

The adapter observes selected state and entity-registry changes, plus a 30-second
fallback refresh. Missing/invalid source states clear current details. Registry
identity changes fail closed; they cannot silently move approval to a replacement
entity. A renamed selection must be reviewed again (or restored to its original
identity). It never clears holds or resumes adaptation to make status healthy.

## Revocation and rollback

Open the integration's **Configure** options, select **revoke**, and confirm.
Revocation persists before runtime shutdown/reload; current details are cleared,
listeners and periodic reads stop, and the sensor reads `revoked`. A process restart
keeps it revoked. Use **review** to select and explicitly approve again.

To roll back an installation, revoke first, then delete this integration entry
through Home Assistant. Its summary sensor/device are removed; BowLighting keeps
running unchanged. Delete only `custom_components/bowlabs_lighting_status` if also
removing the code, followed by a full HA restart. Never delete `bow_lighting` or
`bowlabs_status`. Restore only this candidate's folder from its previous ZIP when
rolling back a code update. Do not restore household configuration wholesale.

Any eventual household installation needs an agreed backup, exact target HA
version, selected diagnostics, code-copy boundary and **full HA restart approval**.
No restart of BowLighting's separate application or changes to household automations,
frame or Music workaround are required by the status reader.

## Isolated validation

The lab uses its own `work/lighting-install.nosync/` and loopback port **18168**.
It copies candidate code and a static fake `bow_lighting` SensorEntity platform
into that disposable config before starting HA. The real source application is
never copied or imported. The lab guard blocks external networking and child
processes; optional HA framework/UI attempts were blocked (the report records the count). It is an accidental
contact guard for trusted test code, not an OS sandbox.

```sh
python3 LightingStatus/tools/test.py
work/mac-lab.nosync/ha/bin/python LightingStatus/tools/run_lab.py
work/mac-lab.nosync/ha/bin/python LightingStatus/tools/check_install.py
```

The first command passes five pure production-projection tests with every socket
and child process prohibited. The last command passes 16 native config/options
flow assertions and leaves an entry revoked. Stop/restart only the owned lab
process, then run:

```sh
work/mac-lab.nosync/ha/bin/python LightingStatus/tools/check_install.py after-restart
```

Seven additional assertions prove revoked persistence, explicit reapproval,
removal without another restart, sensor removal and unchanged synthetic sources.
The UI was then used to reinstall the candidate, approve and revoke it visually.
With that entry present, `tools/check_identity.py` passes six further assertions
for registry rename/identity protection and restores the source and revoked state.
Total: **5 pure tests and 29 native HA assertions**, plus visual end-to-end setup.
Ruff and formatting checks pass. The same 29 native assertions also pass on Linux,
followed by candidate code removal and a clean HA boot with the synthetic lighting
source unchanged. The five pure tests also pass on Linux. Official hassfest passes;
full HACS remains unvalidated due to private repository visibility.

Open <http://127.0.0.1:18168/config/integrations> while the lab runs. Test-only
administrator: `lighting-admin` / `bowlabs-synthetic-admin`; viewer:
`suite-viewer` / `bowlabs-synthetic-viewer`. These belong only to this loopback lab;
never reuse them. Private runtime tokens stay mode 600 under the mode-700 lab
directory and are excluded from the install and source ZIPs.

## Portable Linux CI

The CI runner preinstalls HA's pinned default/frontend/auth dependencies before
enabling the runtime network/process guard. It then starts a fresh test HA, runs
all native checks, restarts to prove revocation persistence, removes the entry and
candidate code, and boots again. All files live in a temporary directory. The
fixture and guard are standalone; no sibling workspace source is uploaded.

```sh
python tools/prepare_linux.py
python tools/test.py
python tools/check_linux.py
```

The official HACS action is enabled with no ignored checks and comments disabled.
It stops at the private-repository prerequisite; no result is bypassed or presented
as a pass. Publication requires separate approval. A household installation also
still requires an agreed backup, sensor selection and full HA restart boundary.

## Package boundaries

The install ZIP contains only `custom_components/bowlabs_lighting_status/`.
The private source ZIP additionally includes this guide, test tools and the clearly
marked fake fixture. It excludes work directories, credentials, private keys,
caches, sibling applications and household data. The source is not published.
The public status-integration repository and its existing release remain unchanged.
