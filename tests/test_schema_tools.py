import pytest
from fastmcp import Client

@pytest.mark.asyncio
async def test_discover_schema_tool(test_app):
    async with Client(test_app) as client:
        result = await client.call_tool(
            "discover_schema",
            {
                "request": {
                    "app_id": "maintenance"
                }
            }
        )
        
        content = result.structured_content
        assert content["app_id"] == "maintenance"
        assert "schema" in content
        schema = content["schema"]
        assert "tasks" in schema["tables"]
        assert "facilities" in schema["tables"]
        
        tasks_table = schema["tables"]["tasks"]
        columns = {c["name"] for c in tasks_table["columns"]}
        assert "id" in columns
        assert "title" in columns
        assert "status" in columns
