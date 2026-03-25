from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from tag_fastmcp.agent.prompts import (
    STRUCTURED_SQL_CONTEXT_TEMPLATE,
    STRUCTURED_SQL_PLANNER_PROMPT,
)
from tag_fastmcp.models.contracts import ChatExecutionPlan

if TYPE_CHECKING:
    from tag_fastmcp.core.app_router import AppContext


class StructuredChatAgent:
    def __init__(self, base_url: str, model_name: str = "qwen-2.5-72b-instruct"):
        self.client = AsyncOpenAI(base_url=base_url, api_key="not-needed")
        self.model_name = model_name

    async def plan(
        self,
        app_ctx: AppContext,
        user_message: str,
        *,
        history: list[dict[str, str]] | None = None,
    ) -> ChatExecutionPlan:
        schema = await app_ctx.schema_discovery.discover()
        manifest = app_ctx.domain_registry.manifest
        prompt_context = STRUCTURED_SQL_CONTEXT_TEMPLATE.format(
            app_id=app_ctx.app_id,
            allow_mutations=str(app_ctx.sql_policy.allow_mutations).lower(),
            require_select_where=str(app_ctx.sql_policy.require_select_where).lower(),
            allowed_tables=", ".join(sorted(app_ctx.sql_policy.allowed_tables)),
            protected_tables=", ".join(sorted(app_ctx.sql_policy.protected_tables)),
            reports=", ".join(sorted(manifest.reports.keys())) or "none",
            workflows=", ".join(sorted(manifest.workflows.keys())) or "none",
            schema_json=json.dumps(schema.model_dump(), indent=2),
        )
        messages = [
            {"role": "system", "content": STRUCTURED_SQL_PLANNER_PROMPT},
            {"role": "system", "content": prompt_context},
        ]
        if history:
            messages.extend(history[-8:])
        messages.append({"role": "user", "content": user_message})

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.0,
            )
            content = response.choices[0].message.content or ""
            return ChatExecutionPlan.model_validate(self._extract_json(content))
        except Exception:
            return ChatExecutionPlan(intent="manual_answer")

    @staticmethod
    def _extract_json(content: str) -> dict:
        normalized = content.strip()
        if normalized.startswith("```"):
            lines = [line for line in normalized.splitlines() if not line.strip().startswith("```")]
            normalized = "\n".join(lines).strip()
        start = normalized.find("{")
        end = normalized.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Structured planner did not return a JSON object.")
        return json.loads(normalized[start : end + 1])
