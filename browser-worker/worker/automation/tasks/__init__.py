from typing import Dict, Type

from worker.automation.base import BaseAutomationTask
from worker.automation.tasks.environment_check import EnvironmentCheckTask
from worker.automation.tasks.public_page_snapshot import PublicPageSnapshotTask
from worker.automation.tasks.smoke_test import SmokeTestTask

TASK_REGISTRY: Dict[str, Type[BaseAutomationTask]] = {
    EnvironmentCheckTask.task_type: EnvironmentCheckTask,
    PublicPageSnapshotTask.task_type: PublicPageSnapshotTask,
    SmokeTestTask.task_type: SmokeTestTask,
}


def get_task_handler(task_type: str) -> BaseAutomationTask:
    try:
        return TASK_REGISTRY[task_type]()
    except KeyError as exc:
        raise ValueError(f"unsupported task type: {task_type}") from exc


__all__ = ["TASK_REGISTRY", "get_task_handler"]
