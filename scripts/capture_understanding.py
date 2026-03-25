from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import yaml

from tag_fastmcp.core.container import build_container
from tag_fastmcp.core.understanding_capture import UnderstandingCaptureService
from tag_fastmcp.settings import PROJECT_ROOT, get_settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect one app, preview sample rows, ask targeted questions, and write an understanding workbook.",
    )
    parser.add_argument("--app-id", required=True, help="Configured app_id from apps.yaml or apps.local.yaml.")
    parser.add_argument(
        "--apps-config-path",
        type=Path,
        default=None,
        help="Optional apps config path override. Defaults to TAG_FASTMCP_APPS_CONFIG_PATH or apps.yaml.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "understanding",
        help="Directory where the YAML and Markdown workbook files should be written.",
    )
    parser.add_argument(
        "--max-tables",
        type=int,
        default=8,
        help="Maximum number of tables to summarize and interview around.",
    )
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=3,
        help="Number of sample rows to preview per summarized table.",
    )
    return parser.parse_args()


def _prompt(question: str) -> str:
    return input(f"{question}\n> ").strip()


async def _main(args: argparse.Namespace) -> int:
    settings = get_settings()
    if args.apps_config_path is not None:
        settings = settings.model_copy(update={"apps_config_path": args.apps_config_path})

    container = build_container(settings)
    try:
        app_ctx = container.app_router.resolve(args.app_id)
        service = UnderstandingCaptureService()
        workbook = await service.build_workbook(
            app_ctx,
            max_tables=args.max_tables,
            sample_rows_per_table=args.sample_rows,
        )

        print(f"\n=== Understanding Capture: {workbook.display_name} ({workbook.app_id}) ===")
        print("\nGenerated Overview:")
        print(workbook.understanding_doc.overview)

        if workbook.table_samples:
            print("\nSample Rows:")
            for sample in workbook.table_samples:
                print(f"- {sample.table_name}: {sample.sample_row_count} sample rows")
                for row in sample.sample_rows:
                    print(f"  {row}")

        print("\nAnswer the prompts below. Press Enter to skip any optional question.\n")
        answers: dict[str, str] = {}
        for question in workbook.questions:
            print(f"[{question.question_id}]")
            if question.context:
                print(f"Context: {question.context}")
            if question.sample_values:
                print(f"Sample hints: {', '.join(question.sample_values)}")
            answer = _prompt(question.prompt)
            if answer:
                answers[question.question_id] = answer
            print("")

        completed_workbook = service.apply_answers(workbook, answers)
        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = output_dir / f"{args.app_id}.understanding.yaml"
        markdown_path = output_dir / f"{args.app_id}.understanding.md"

        with yaml_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(
                completed_workbook.model_dump(mode="json"),
                handle,
                sort_keys=False,
                allow_unicode=False,
            )
        markdown_path.write_text(completed_workbook.markdown, encoding="utf-8")

        print("Understanding files written:")
        print(f"- {yaml_path}")
        print(f"- {markdown_path}")
        return 0
    finally:
        await container.close()


def main() -> int:
    return asyncio.run(_main(_parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
