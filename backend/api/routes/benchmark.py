"""
Vigil — RM Analytics API Route (backend/api/routes/benchmark.py)
Re-exports router and endpoints from backend.api.routes.rm for backward compatibility.
"""

from backend.api.routes.rm import (
    router,
    list_rms,
    get_rm_analytics,
    send_rm_report_email,
)

__all__ = [
    "router",
    "list_rms",
    "get_rm_analytics",
    "send_rm_report_email",
]
