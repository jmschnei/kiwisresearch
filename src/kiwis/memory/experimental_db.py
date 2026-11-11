"""Relational database for experiment state tracking."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4


@dataclass
class ExperimentRun:
    """A single experiment execution."""
    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    hypothesis: str = ""
    methodology: str = ""
    dataset: str = ""
    hyperparameters: dict = field(default_factory=dict)
    results: dict[str, float] = field(default_factory=dict)
    artifacts_path: str = ""
    status: str = "pending"  # pending | running | completed | failed
    error_message: Optional[str] = None
    logs: list[str] = field(default_factory=list)


@dataclass
class MetricComparison:
    """Stores comparison of models/methods on same metric."""
    run_a: str
    run_b: str
    metric: str
    value_a: float
    value_b: float
    improvement: float  # percentage

    @property
    def better_run(self) -> str:
        if self.metric.endswith("_best"):
            return self.run_a if self.value_a > self.value_b else self.run_b
        return self.run_a if self.value_a < self.value_b else self.run_b


class ExperimentalDatabase:
    """Lightweight SQLite-backed store for experiment metadata."""

    def __init__(self, db_path: str = "./data/experiments.db"):
        self._db_path = db_path
        self._conn = None

    async def initialize(self) -> None:
        import aiosqlite
        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                run_id TEXT PRIMARY KEY,
                hypothesis TEXT,
                methodology TEXT,
                dataset TEXT,
                hyperparameters TEXT,
                results TEXT,
                artifacts_path TEXT,
                status TEXT,
                error_message TEXT,
                logs TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._conn.commit()

    async def insert_experiment(self, exp: ExperimentRun) -> str:
        await self._conn.execute(
            """INSERT INTO experiments 
               (run_id, hypothesis, methodology, dataset, hyperparameters, results,
                artifacts_path, status, error_message, logs)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                exp.run_id, exp.hypothesis, exp.methodology, exp.dataset,
                json.dumps(exp.hyperparameters), json.dumps(exp.results),
                exp.artifacts_path, exp.status, exp.error_message,
                json.dumps(exp.logs),
            ),
        )
        await self._conn.commit()
        return exp.run_id

    async def get_experiment(self, run_id: str) -> ExperimentRun | None:
        cursor = await self._conn.execute(
            "SELECT * FROM experiments WHERE run_id = ?", (run_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row))
        return ExperimentRun(
            run_id=data["run_id"],
            hypothesis=data["hypothesis"],
            methodology=data["methodology"],
            dataset=data["dataset"],
            hyperparameters=json.loads(data["hyperparameters"]),
            results=json.loads(data["results"]),
            artifacts_path=data["artifacts_path"],
            status=data["status"],
            error_message=data["error_message"],
            logs=json.loads(data["logs"]),
        )

    async def list_experiments(self, status: Optional[str] = None) -> list[ExperimentRun]:
        query = "SELECT * FROM experiments"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        experiments = []
        for row in rows:
            data = dict(zip(columns, row))
            experiments.append(ExperimentRun(
                run_id=data["run_id"],
                hypothesis=data["hypothesis"],
                methodology=data["methodology"],
                dataset=data["dataset"],
                hyperparameters=json.loads(data["hyperparameters"]),
                results=json.loads(data["results"]),
                artifacts_path=data["artifacts_path"],
                status=data["status"],
                error_message=data["error_message"],
                logs=json.loads(data["logs"]),
            ))
        return experiments

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
