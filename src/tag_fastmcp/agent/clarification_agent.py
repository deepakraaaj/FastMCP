from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI

from tag_fastmcp.agent.prompts import AGENT_SYSTEM_PROMPT, SCHEMA_CONTEXT_TEMPLATE

if TYPE_CHECKING:
    from tag_fastmcp.core.app_router import AppContext


class ClarificationAgent:
    def __init__(self, base_url: str, model_name: str = "qwen-2.5-72b-instruct"):
        self.client = AsyncOpenAI(base_url=base_url, api_key="not-needed")
        self.model_name = model_name

    async def chat(self, app_ctx: AppContext, user_message: str, history: list[dict] | None = None) -> str:
        # 1. Discover schema to provide context
        schema = await app_ctx.schema_discovery.discover()
        manifest = app_ctx.domain_registry.manifest
        
        schema_context = SCHEMA_CONTEXT_TEMPLATE.format(
            app_id=app_ctx.app_id,
            schema_json=json.dumps(schema.model_dump(), indent=2),
            reports=list(manifest.reports.keys()),
            workflows=list(manifest.workflows.keys()),
        )

        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "system", "content": schema_context},
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,
            )
            return response.choices[0].message.content or "I'm sorry, I couldn't process that."
        except Exception:
            # Graceful fallback when the LLM endpoint is unreachable
            reports = list(manifest.reports.keys())
            workflows = list(manifest.workflows.keys())
            tables = list(schema.tables.keys())
            parts: list[str] = [
                f"I'm the {app_ctx.display_name} assistant for app '{app_ctx.app_id}'.",
                f"Available reports: {', '.join(reports) if reports else 'none'}.",
                f"Available workflows: {', '.join(workflows) if workflows else 'none'}.",
                f"Database tables: {', '.join(tables[:8]) if tables else 'none'}.",
                f"Try asking me to 'show overdue tasks' or 'create a task'.",
            ]
            return " ".join(parts)
