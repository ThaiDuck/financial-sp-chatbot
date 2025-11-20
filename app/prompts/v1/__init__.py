"""V1 Prompts - Consolidated and Organized"""
from .router import ROUTER_PROMPT
from .system import SYSTEM_PROMPT
from .news import NEWS_PROMPT, NEWS_TEMPLATE
from .gold import GOLD_PROMPT, GOLD_TEMPLATE
from .stock import STOCK_PROMPT, STOCK_TEMPLATE
from .default import DEFAULT_PROMPT, DEFAULT_TEMPLATE

__all__ = [
    "ROUTER_PROMPT",
    "SYSTEM_PROMPT",
    "NEWS_PROMPT",
    "NEWS_TEMPLATE",
    "GOLD_PROMPT",
    "GOLD_TEMPLATE",
    "STOCK_PROMPT",
    "STOCK_TEMPLATE",
    "DEFAULT_PROMPT",
    "DEFAULT_TEMPLATE",
]
