"""Seed the demo SQLite databases with realistic sample data.

Usage (standalone):
    uv run python scripts/seed_demo.py

The same ``seed_all`` coroutine is also called by the HTTP lifespan hook
so the demo databases are ready on first boot.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Maintenance database
# ---------------------------------------------------------------------------

MAINTENANCE_DDL = """
CREATE TABLE IF NOT EXISTS facilities (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL,
    region TEXT NOT NULL DEFAULT 'Central'
);

CREATE TABLE IF NOT EXISTS locations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id INTEGER NOT NULL,
    section     TEXT NOT NULL,
    FOREIGN KEY (facility_id) REFERENCES facilities (id)
);

CREATE TABLE IF NOT EXISTS technicians (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL,
    specialty TEXT NOT NULL DEFAULT 'General'
);

CREATE TABLE IF NOT EXISTS parts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    stock_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id   INTEGER NOT NULL,
    location_id   INTEGER,
    technician_id INTEGER,
    title         TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    priority      TEXT NOT NULL DEFAULT 'medium',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (facility_id) REFERENCES facilities (id),
    FOREIGN KEY (location_id) REFERENCES locations (id),
    FOREIGN KEY (technician_id) REFERENCES technicians (id)
);

CREATE TABLE IF NOT EXISTS task_parts (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id  INTEGER NOT NULL,
    part_id  INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (task_id) REFERENCES tasks (id),
    FOREIGN KEY (part_id) REFERENCES parts (id)
);
"""

MAINTENANCE_DATA = """
-- Facilities
INSERT OR IGNORE INTO facilities (id, name, region) VALUES (1, 'Plant Alpha', 'North');
INSERT OR IGNORE INTO facilities (id, name, region) VALUES (2, 'Plant Beta', 'East');
INSERT OR IGNORE INTO facilities (id, name, region) VALUES (3, 'Plant Gamma', 'West');

-- Locations
INSERT OR IGNORE INTO locations (id, facility_id, section) VALUES (1, 1, 'Boiler Room');
INSERT OR IGNORE INTO locations (id, facility_id, section) VALUES (2, 1, 'Turbine Hall');
INSERT OR IGNORE INTO locations (id, facility_id, section) VALUES (3, 2, 'Pump Station');
INSERT OR IGNORE INTO locations (id, facility_id, section) VALUES (4, 2, 'Cooling Tower');
INSERT OR IGNORE INTO locations (id, facility_id, section) VALUES (5, 3, 'Generator Bay');
INSERT OR IGNORE INTO locations (id, facility_id, section) VALUES (6, 3, 'Substation');

-- Technicians
INSERT OR IGNORE INTO technicians (id, name, specialty) VALUES (1, 'Ravi Kumar', 'Electrical');
INSERT OR IGNORE INTO technicians (id, name, specialty) VALUES (2, 'Priya Sharma', 'Mechanical');
INSERT OR IGNORE INTO technicians (id, name, specialty) VALUES (3, 'Arun Patel', 'HVAC');
INSERT OR IGNORE INTO technicians (id, name, specialty) VALUES (4, 'Meena Iyer', 'Instrumentation');

-- Parts
INSERT OR IGNORE INTO parts (id, name, stock_count) VALUES (1, 'Hydraulic Pump Seal', 12);
INSERT OR IGNORE INTO parts (id, name, stock_count) VALUES (2, 'Bearing Assembly', 8);
INSERT OR IGNORE INTO parts (id, name, stock_count) VALUES (3, 'Pressure Gauge', 25);
INSERT OR IGNORE INTO parts (id, name, stock_count) VALUES (4, 'Control Valve', 3);
INSERT OR IGNORE INTO parts (id, name, stock_count) VALUES (5, 'Drive Belt', 0);
INSERT OR IGNORE INTO parts (id, name, stock_count) VALUES (6, 'Thermal Fuse', 15);

-- Tasks (mix of statuses)
INSERT OR IGNORE INTO tasks (id, facility_id, location_id, technician_id, title, status, priority) VALUES
  (1,  1, 1, 1, 'Replace boiler pressure relief valve',    'overdue',     'critical');
INSERT OR IGNORE INTO tasks (id, facility_id, location_id, technician_id, title, status, priority) VALUES
  (2,  1, 2, 2, 'Turbine bearing inspection',              'overdue',     'high');
INSERT OR IGNORE INTO tasks (id, facility_id, location_id, technician_id, title, status, priority) VALUES
  (3,  2, 3, 3, 'Pump station vibration analysis',         'in_progress', 'high');
INSERT OR IGNORE INTO tasks (id, facility_id, location_id, technician_id, title, status, priority) VALUES
  (4,  2, 4, NULL, 'Cooling tower fan motor replacement',  'overdue',     'critical');
INSERT OR IGNORE INTO tasks (id, facility_id, location_id, technician_id, title, status, priority) VALUES
  (5,  3, 5, 4, 'Generator winding test',                  'pending',     'medium');
INSERT OR IGNORE INTO tasks (id, facility_id, location_id, technician_id, title, status, priority) VALUES
  (6,  3, 6, 1, 'Substation transformer oil check',        'completed',   'low');
INSERT OR IGNORE INTO tasks (id, facility_id, location_id, technician_id, title, status, priority) VALUES
  (7,  1, 1, 2, 'Boiler tube leak repair',                 'overdue',     'critical');
INSERT OR IGNORE INTO tasks (id, facility_id, location_id, technician_id, title, status, priority) VALUES
  (8,  2, 3, 3, 'Pump impeller replacement',               'pending',     'high');
INSERT OR IGNORE INTO tasks (id, facility_id, location_id, technician_id, title, status, priority) VALUES
  (9,  3, 5, 4, 'Generator fuel filter service',           'in_progress', 'medium');
INSERT OR IGNORE INTO tasks (id, facility_id, location_id, technician_id, title, status, priority) VALUES
  (10, 1, 2, NULL, 'Turbine blade fatigue inspection',     'overdue',     'high');

-- Task parts
INSERT OR IGNORE INTO task_parts (id, task_id, part_id, quantity) VALUES (1, 1, 4, 2);
INSERT OR IGNORE INTO task_parts (id, task_id, part_id, quantity) VALUES (2, 2, 2, 1);
INSERT OR IGNORE INTO task_parts (id, task_id, part_id, quantity) VALUES (3, 4, 5, 3);
INSERT OR IGNORE INTO task_parts (id, task_id, part_id, quantity) VALUES (4, 7, 1, 4);
"""


# ---------------------------------------------------------------------------
# Dispatch database
# ---------------------------------------------------------------------------

DISPATCH_DDL = """
CREATE TABLE IF NOT EXISTS service_areas (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT NOT NULL,
    region TEXT NOT NULL DEFAULT 'Central'
);

CREATE TABLE IF NOT EXISTS technicians (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    specialty TEXT NOT NULL DEFAULT 'General'
);

CREATE TABLE IF NOT EXISTS dispatches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    technician_id   INTEGER NOT NULL,
    service_area_id INTEGER NOT NULL,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    priority        TEXT NOT NULL DEFAULT 'medium',
    scheduled_date  TEXT NOT NULL DEFAULT (date('now')),
    FOREIGN KEY (technician_id)   REFERENCES technicians (id),
    FOREIGN KEY (service_area_id) REFERENCES service_areas (id)
);
"""

DISPATCH_DATA = """
-- Service areas
INSERT OR IGNORE INTO service_areas (id, name, region) VALUES (1, 'Downtown Zone', 'North');
INSERT OR IGNORE INTO service_areas (id, name, region) VALUES (2, 'Industrial Park', 'East');
INSERT OR IGNORE INTO service_areas (id, name, region) VALUES (3, 'Suburban Ring', 'West');

-- Technicians
INSERT OR IGNORE INTO technicians (id, name, specialty) VALUES (1, 'Karthik R', 'Electrical');
INSERT OR IGNORE INTO technicians (id, name, specialty) VALUES (2, 'Sneha M', 'Plumbing');
INSERT OR IGNORE INTO technicians (id, name, specialty) VALUES (3, 'Vikram S', 'HVAC');

-- Dispatches
INSERT OR IGNORE INTO dispatches (id, technician_id, service_area_id, title, status, priority, scheduled_date) VALUES
  (1, 1, 1, 'Emergency lighting panel repair',   'pending',    'critical', '2026-03-18');
INSERT OR IGNORE INTO dispatches (id, technician_id, service_area_id, title, status, priority, scheduled_date) VALUES
  (2, 2, 2, 'Water main valve replacement',       'delayed',    'high',     '2026-03-15');
INSERT OR IGNORE INTO dispatches (id, technician_id, service_area_id, title, status, priority, scheduled_date) VALUES
  (3, 3, 3, 'HVAC duct cleaning – Building 7',    'pending',    'medium',   '2026-03-20');
INSERT OR IGNORE INTO dispatches (id, technician_id, service_area_id, title, status, priority, scheduled_date) VALUES
  (4, 1, 2, 'Transformer load balancing',          'delayed',    'high',     '2026-03-14');
INSERT OR IGNORE INTO dispatches (id, technician_id, service_area_id, title, status, priority, scheduled_date) VALUES
  (5, 2, 1, 'Fire suppression system test',        'completed',  'critical', '2026-03-17');
INSERT OR IGNORE INTO dispatches (id, technician_id, service_area_id, title, status, priority, scheduled_date) VALUES
  (6, 3, 3, 'Compressor unit service',             'in_progress','medium',   '2026-03-19');
INSERT OR IGNORE INTO dispatches (id, technician_id, service_area_id, title, status, priority, scheduled_date) VALUES
  (7, 1, 1, 'UPS battery bank replacement',        'pending',    'high',     '2026-03-21');
INSERT OR IGNORE INTO dispatches (id, technician_id, service_area_id, title, status, priority, scheduled_date) VALUES
  (8, 2, 2, 'Drainage pump overhaul',              'delayed',    'medium',   '2026-03-13');
"""


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def _seed_database(db_url: str, ddl: str, data: str) -> None:
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        for statement in ddl.strip().split(";"):
            statement = statement.strip()
            if statement:
                await conn.execute(text(statement))
        for statement in data.strip().split(";"):
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                # skip pure comment lines
                lines = [l for l in statement.splitlines() if not l.strip().startswith("--")]
                clean = "\n".join(lines).strip()
                if clean:
                    await conn.execute(text(clean))
    await engine.dispose()


async def seed_all() -> None:
    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(exist_ok=True)

    maintenance_url = f"sqlite+aiosqlite:///{data_dir / 'demo_maintenance.sqlite3'}"
    dispatch_url = f"sqlite+aiosqlite:///{data_dir / 'demo_dispatch.sqlite3'}"

    await _seed_database(maintenance_url, MAINTENANCE_DDL, MAINTENANCE_DATA)
    await _seed_database(dispatch_url, DISPATCH_DDL, DISPATCH_DATA)
    print("✓ Demo databases seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed_all())
