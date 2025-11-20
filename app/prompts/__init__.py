"""
Prompts Module - Consolidated Management
"""

# Import from v1 (current version)
from .v1 import (
    ROUTER_PROMPT,
    SYSTEM_PROMPT,
    NEWS_PROMPT,
    NEWS_TEMPLATE,
    GOLD_PROMPT,
    GOLD_TEMPLATE,
    STOCK_PROMPT,
    STOCK_TEMPLATE,
    DEFAULT_PROMPT,
    DEFAULT_TEMPLATE,
)

# For backwards compatibility - export old names if needed
ROUTER_TEMPLATE = ROUTER_PROMPT

__all__ = [
    # System
    "SYSTEM_PROMPT",
    
    # Router
    "ROUTER_PROMPT",
    "ROUTER_TEMPLATE",
    
    # Templates by category
    "NEWS_PROMPT",
    "NEWS_TEMPLATE",
    "GOLD_PROMPT",
    "GOLD_TEMPLATE",
    "STOCK_PROMPT",
    "STOCK_TEMPLATE",
    "DEFAULT_PROMPT",
    "DEFAULT_TEMPLATE",
]
