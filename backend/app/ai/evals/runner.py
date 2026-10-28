import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.evals.graders import (
    grounding_score,
    numeric_score,
    permission_score,
    schema_score,
    tool_score,
)
from app.core.project_paths import eval_path
from app.models.ai import AIEvalResult, AIEvalRun

DATASET_ROOT = eval_path("datasets")


def _load_cases(suite: str) -> List[Dict[str, Any]]:
    path = DATASET_ROOT / suite / "cases.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


async def run_eval_suite(db: AsyncSession, suite: str = "all") -> dict:
    suites = [suite] if suite != "all" else [p.name for p in DATASET_ROOT.iterdir() if p.is_dir()]
    run = AIEvalRun(eval_suite=suite, started_at=datetime.now(timezone.utc), status="RUNNING")
    db.add(run)
    await db.flush()
    total = passed = failed = 0
    aggregate = {"schema": [], "grounding": [], "numeric": [], "tool": [], "permission": []}
    for current_suite in suites:
        for case in _load_cases(current_suite):
            output = case.get("output", {})
            schema = schema_score(output)
            grounding = grounding_score(output)
            numeric = numeric_score(case.get("expected_facts", []), output)
            tool = tool_score(case.get("expected_tools", []), case.get("used_tools", []))
            permission = permission_score(case.get("forbidden_tools", []), case.get("used_tools", []))
            overall = round((schema + grounding + numeric + tool + permission) / 5, 3)
            critical = numeric < 1.0 and bool(case.get("expected_facts")) or (schema < 1.0)
            total += 1
            if overall >= 0.8 and not critical:
                passed += 1
            else:
                failed += 1
            for key, value in (("schema", schema), ("grounding", grounding), ("numeric", numeric), ("tool", tool), ("permission", permission)):
                aggregate[key].append(value)
            db.add(
                AIEvalResult(
                    eval_run_id=str(run.id),
                    case_id=case.get("case_id", f"{current_suite}-{total}"),
                    agent_type=case.get("agent_type", "unknown"),
                    schema_score=schema,
                    grounding_score=grounding,
                    numeric_score=numeric,
                    tool_score=tool,
                    permission_score=permission,
                    overall_score=overall,
                    critical_failure=critical,
                    details=case,
                )
            )
    run.total_cases = total
    run.passed = passed
    run.failed = failed
    run.aggregate_scores = {k: round(sum(v) / len(v), 3) if v else None for k, v in aggregate.items()}
    run.finished_at = datetime.now(timezone.utc)
    run.status = "SUCCESS"
    await db.commit()
    return {
        "eval_run_id": str(run.id),
        "suite": suite,
        "total": total,
        "passed": passed,
        "failed": failed,
        "aggregate_scores": run.aggregate_scores,
    }
