from tag_fastmcp.core.sql_policy import SQLPolicyValidator


def test_blocks_delete() -> None:
    validator = SQLPolicyValidator(
        allowed_tables={"tasks"},
        protected_tables={"schema_migrations"},
        allow_mutations=False,
        require_select_where=True,
    )
    decision = validator.validate("DELETE FROM tasks WHERE id = 1")
    assert decision.allowed is False
    assert "Forbidden" in decision.reason


def test_blocks_unfiltered_select() -> None:
    validator = SQLPolicyValidator(
        allowed_tables={"tasks"},
        protected_tables=set(),
        allow_mutations=False,
        require_select_where=True,
    )
    decision = validator.validate("SELECT * FROM tasks")
    assert decision.allowed is False
    assert "Unfiltered SELECT" in decision.reason


def test_allows_filtered_select() -> None:
    validator = SQLPolicyValidator(
        allowed_tables={"tasks"},
        protected_tables=set(),
        allow_mutations=False,
        require_select_where=True,
    )
    decision = validator.validate("SELECT id, title FROM tasks WHERE status = 'pending'")
    assert decision.allowed is True
    assert "tasks" in decision.tables


def test_mutation_override_cannot_bypass_disabled_policy() -> None:
    validator = SQLPolicyValidator(
        allowed_tables={"tasks"},
        protected_tables=set(),
        allow_mutations=False,
        require_select_where=True,
    )
    decision = validator.validate(
        "INSERT INTO tasks (title, status) VALUES ('Pump check', 'pending')",
        allow_mutations_override=True,
    )
    assert decision.allowed is False
    assert "Mutations are disabled" in decision.reason


def test_mutation_requires_explicit_confirmation_flag() -> None:
    validator = SQLPolicyValidator(
        allowed_tables={"tasks"},
        protected_tables=set(),
        allow_mutations=True,
        require_select_where=True,
    )
    blocked = validator.validate(
        "UPDATE tasks SET status = 'done' WHERE id = 1",
        allow_mutations_override=False,
    )
    allowed = validator.validate(
        "UPDATE tasks SET status = 'done' WHERE id = 1",
        allow_mutations_override=True,
    )
    assert blocked.allowed is False
    assert allowed.allowed is True
