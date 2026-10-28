from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

from playwright.async_api import Page


@dataclass
class TaskContext:
    task_id: str
    profile: Dict[str, Any]
    payload: Dict[str, Any]
    page: Page
    screenshot_dir: str
    log_dir: str
    navigation_timeout_ms: int
    diagnostic_url: str


class BaseAutomationTask(ABC):
    task_type: str = ""

    @abstractmethod
    async def run(self, ctx: TaskContext) -> Dict[str, Any]:
        raise NotImplementedError
