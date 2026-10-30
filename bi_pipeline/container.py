from .service import AnalyticsService
_service=None
def get_service():
    global _service
    if _service is None: _service=AnalyticsService()
    return _service
