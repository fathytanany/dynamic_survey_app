import json
from datetime import date

from celery import shared_task
from django.core.cache import cache

from services import analytics_service

# TTL for task result metadata stored in Redis (24 hours)
TASK_RESULT_TTL = 60 * 60 * 24


def _task_meta_key(task_id: str) -> str:
    return f"task:{task_id}:meta"


@shared_task(bind=True)
def generate_survey_report(self, survey_id: str, format: str = "json", report_date: str = None):
    """
    Generate an analytics report for a survey.

    Args:
        survey_id: UUID string of the survey.
        format: "json" or "summary".
        report_date: ISO date string (YYYY-MM-DD). Defaults to today.

    Stores result metadata in Redis under task:{task_id}:meta for polling.
    """
    task_id = self.request.id

    # Mark as started
    cache.set(_task_meta_key(task_id), {"status": "started", "result": None}, TASK_RESULT_TTL)

    try:
        if report_date:
            parsed_date = date.fromisoformat(report_date)
        else:
            parsed_date = date.today()

        analytics = analytics_service.get_survey_analytics(survey_id)
        field_analytics = analytics_service.get_field_analytics(survey_id)
        historical = analytics_service.get_historical_report(survey_id, parsed_date)

        report = {
            "survey_id": survey_id,
            "report_date": str(parsed_date),
            "format": format,
            "summary": analytics,
            "field_breakdown": field_analytics,
            "historical": historical,
        }

        meta = {"status": "success", "result": report}
        cache.set(_task_meta_key(task_id), meta, TASK_RESULT_TTL)
        return report

    except Exception as exc:
        meta = {"status": "failure", "result": {"error": str(exc)}}
        cache.set(_task_meta_key(task_id), meta, TASK_RESULT_TTL)
        raise
