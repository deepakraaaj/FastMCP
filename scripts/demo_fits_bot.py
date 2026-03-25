from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import anyio
from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastmcp.utilities.logging import configure_logging
import yaml

from tag_fastmcp.app import create_app
from tag_fastmcp.settings import AppSettings, PROJECT_ROOT


DEMO_APP_ID = "remp_local"
DEMO_REPORT_TAG = "scheduler_task_menu"
DEMO_WORKFLOW_TAG = "create_scheduler_task"
DEMO_WORKFLOW_ID = f"workflow.{DEMO_APP_ID}.{DEMO_WORKFLOW_TAG}"
LOCAL_APPS_CONFIG_PATH = PROJECT_ROOT / "apps.local.yaml"


def _print_title(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_json(label: str, payload: Any) -> None:
    print(f"\n{label}:")
    print(json.dumps(payload, indent=2, default=str))


def _is_mysql_access_denied(error: Exception) -> bool:
    return "Access denied for user" in str(error)


async def _call_with_timeout(client: Client, tool_name: str, arguments: dict[str, Any], timeout_seconds: float = 10.0):
    with anyio.fail_after(timeout_seconds):
        return await client.call_tool(tool_name, arguments)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the localhost database management demo.")
    parser.add_argument(
        "--report-timeout-seconds",
        type=float,
        default=5.0,
        help="Maximum time to wait for the live localhost report before exiting cleanly.",
    )
    return parser.parse_args()


def _configure_demo_logging() -> None:
    configure_logging(
        level="CRITICAL",
        logger=logging.getLogger("fastmcp"),
        enable_rich_tracebacks=False,
    )


def _apps_config_contains_app(path: Path, app_id: str) -> bool:
    if not path.exists():
        return False
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    apps = payload.get("apps") or {}
    return app_id in apps


def _resolve_demo_settings() -> AppSettings:
    if _apps_config_contains_app(LOCAL_APPS_CONFIG_PATH, DEMO_APP_ID):
        apps_config_path = LOCAL_APPS_CONFIG_PATH
    else:
        apps_config_path = PROJECT_ROOT / "apps.yaml"
    return AppSettings(
        apps_config_path=apps_config_path,
        root_path=PROJECT_ROOT,
    )


async def main(report_timeout_seconds: float) -> None:
    _configure_demo_logging()
    settings = _resolve_demo_settings()
    app = create_app(settings=settings)

    async with Client(app) as client:
        _print_title("1. Start Session")
        session_result = await _call_with_timeout(client, "start_session", {"actor_id": "management-demo"})
        session_payload = session_result.structured_content
        session_id = session_payload["session"]["session_id"]
        print(f"Session ID: {session_id}")
        print(f"Apps config: {Path(settings.apps_config_path).name}")

        _print_title("2. Discover Localhost Capabilities")
        capabilities_result = await _call_with_timeout(client, "describe_capabilities", {"app_id": DEMO_APP_ID})
        capabilities_payload = capabilities_result.structured_content["registry"]
        report_ids = [
            item["capability_id"]
            for item in capabilities_payload["capabilities"]
            if item["kind"] == "report"
        ]
        workflow_ids = [
            item["capability_id"]
            for item in capabilities_payload["capabilities"]
            if item["kind"] == "workflow"
        ]
        print("Reports:", ", ".join(report_ids))
        print("Workflows:", ", ".join(workflow_ids))

        _print_title("3. Read Live Localhost DB Data Through a Safe Report")
        print(f"Waiting up to {report_timeout_seconds:.1f} seconds for the localhost database response...")
        try:
            report_result = await _call_with_timeout(
                client,
                "invoke_capability",
                {
                    "request": {
                        "app_id": DEMO_APP_ID,
                        "session_id": session_id,
                        "kind": "report",
                        "tags": [DEMO_REPORT_TAG],
                    }
                },
                timeout_seconds=report_timeout_seconds,
            )
        except TimeoutError:
            print(f"Localhost database access timed out after {report_timeout_seconds:.1f} seconds.")
            print("Use the local fallback demo path if the project DB or network is slow.")
            return
        except ToolError as exc:
            if _is_mysql_access_denied(exc):
                print("Localhost database authentication failed.")
                print("Update apps.local.yaml with a localhost-valid MySQL user or grant access for the configured user.")
                return
            raise
        report_payload = report_result.structured_content
        report_output = report_payload["routing"]["output"]["report"]
        print(f"Report status: {report_payload['status']}")
        print(f"Rows returned: {report_output['row_count']}")
        preview_rows = report_output["rows_preview"][:3]
        _print_json("Preview rows", preview_rows)

        if not preview_rows:
            raise RuntimeError("The localhost report returned no rows. Cannot continue the workflow demo.")

        first_row = preview_rows[0]

        _print_title("4. Start a Bot-Style Guided Workflow")
        workflow_start = await _call_with_timeout(
            client,
            "invoke_capability",
            {
                "request": {
                    "app_id": DEMO_APP_ID,
                    "session_id": session_id,
                    "kind": "workflow",
                    "tags": [DEMO_WORKFLOW_TAG],
                    "arguments": {
                        "title": "Management demo scheduler task",
                    },
                }
            },
        )
        workflow_start_payload = workflow_start.structured_content
        _print_json(
            "Workflow start",
            workflow_start_payload["routing"]["output"]["workflow"],
        )

        _print_title("5. Continue Workflow Using Real IDs From Localhost Data")
        workflow_continue = await _call_with_timeout(
            client,
            "invoke_capability",
            {
                "request": {
                    "app_id": DEMO_APP_ID,
                    "session_id": session_id,
                    "capability_id": DEMO_WORKFLOW_ID,
                    "arguments": {
                        "facility_id": first_row["facility_id"],
                        "schedule_id": first_row["schedule_id"],
                        "task_description_id": first_row["task_description_id"],
                        "priority": first_row["priority"] or 1,
                    },
                }
            },
        )
        workflow_continue_payload = workflow_continue.structured_content
        _print_json(
            "Workflow completed",
            workflow_continue_payload["routing"]["output"]["workflow"],
        )

        _print_title("Demo Summary")
        print("The platform discovered localhost app capabilities, queried the real local MySQL DB,")
        print("and completed a guided workflow using identifiers returned from live data.")


if __name__ == "__main__":
    args = _parse_args()
    try:
        anyio.run(main, args.report_timeout_seconds)
    except KeyboardInterrupt:
        print("\nDemo interrupted manually before the timeout path completed.")
        print("If you want a quicker exit, rerun with: uv run python scripts/demo_fits_bot.py --report-timeout-seconds 5")
