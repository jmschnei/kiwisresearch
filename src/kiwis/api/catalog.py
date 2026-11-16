"""Static mapping between pipeline phases, backend agent roles and dashboard agents."""

from __future__ import annotations

from ..orchestrator.pipeline import PipelinePhase

# Dashboard agents: id, display name, icon, color
UI_AGENTS = [
    ("ideador", "Ideador", "🧠", "#a855f7"),
    ("rag", "RAG Bibliotecario", "📚", "#06b6d4"),
    ("coder", "Coder", "💻", "#3b82f6"),
    ("sandbox", "Sandbox", "⚙️", "#10b981"),
    ("analista", "Analista", "📊", "#f97316"),
    ("latex", "Redactor LaTeX", "📝", "#ec4899"),
    ("revisor", "Revisor Adversarial", "🔍", "#ef4444"),
]
UI_AGENT_BY_ID = {a[0]: a for a in UI_AGENTS}

# Pipeline order: phase, backend role, step name, dashboard agent id, status while running
PHASE_TABLE = [
    (PipelinePhase.HYPOTHESIS, "ideation", "Formulación del Problema", "ideador", "thinking"),
    (PipelinePhase.LITERATURE, "librarian", "Revisión Bibliográfica", "rag", "executing"),
    (PipelinePhase.EXPERIMENT_DESIGN, "experiment_architect", "Diseño del Experimento", "coder", "executing"),
    (PipelinePhase.EXECUTION, "engineer", "Ejecución en Sandbox", "sandbox", "executing"),
    (PipelinePhase.ANALYSIS, "data_analyst", "Análisis de Resultados", "analista", "executing"),
    (PipelinePhase.PAPER_WRITING, "writer", "Escritura del Manuscrito", "latex", "executing"),
    (PipelinePhase.PEER_REVIEW, "reviewer", "Revisión Adversarial", "revisor", "reviewing"),
]
PHASE_INDEX = {row[0]: i for i, row in enumerate(PHASE_TABLE)}
ROLE_TO_UI_AGENT = {row[1]: row[3] for row in PHASE_TABLE}
