# Localhost DB Demo Runbook

Purpose: Run a short management demo that shows the current platform accessing a real localhost MySQL database safely through the plug-and-play contracts.

## Demo Goal

Show three things in under 3 minutes:

1. the platform can discover what capabilities are available for a real application
2. the platform can access a real localhost MySQL database through a safe report capability
3. the platform can guide a bot-style workflow by asking for missing fields and then completing the workflow state

## Demo Command

From the repository root:

```bash
uv run python scripts/demo_fits_bot.py
```

Current assumption for the localhost demo:

- `apps.local.yaml` is used automatically only when it contains the `remp_local` app entry
- the local override points at a real localhost MySQL database
- the current demo app is `remp_local` backed by the `remp-chat-bot` database
- the tracked manifest for this demo is `domains/remp_local.yaml`

If the localhost DB is slow and you want a quicker fallback:

```bash
uv run python scripts/demo_fits_bot.py --report-timeout-seconds 5
```

## What The Demo Does

The script:

1. creates a session
2. loads and prints the discovered `remp_local` capabilities
3. invokes the `scheduler_task_menu` report through `invoke_capability`
4. prints real rows from the localhost `remp-chat-bot` database
5. starts the `create_scheduler_task` workflow with only a title
6. shows the missing fields and the next prompt
7. continues the workflow using real IDs from the report output
8. shows the completed workflow payload

## Demo Talk Track

Use this while the script runs:

- "This first step shows the platform discovering capabilities for a localhost application from configuration and manifests, not from hardcoded logic."
- "Now the platform is invoking a report capability against a real localhost MySQL database. This is live application data coming through the internal core with policy enforcement."
- "Next, I’m showing a bot-style workflow. The system accepts a partial request, detects what is missing, and returns the next question instead of blindly continuing."
- "Finally, I continue the workflow using real identifiers returned from the database query, which shows how this can support guided enterprise actions."

## Fallback If The DB Is Unavailable

If the localhost database is temporarily unreachable:

- say the architecture and flow remain valid
- mention the demo depends on the local MySQL service and valid localhost credentials
- mention the demo now exits cleanly after the configured timeout instead of hanging
- if MySQL rejects the login, add or restore the `remp_local` entry in `apps.local.yaml` with a valid localhost user or fix the grant
- fall back to the local test-backed workflow and report examples already in the repository

## Expected Outcome

You should see:

- a created session id
- discovered report and workflow capability ids for `remp_local`
- rows from `report.remp_local.scheduler_task_menu`
- a pending workflow with missing fields
- a completed workflow payload after the second call
