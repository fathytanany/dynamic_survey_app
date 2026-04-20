import json
from datetime import date, timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, FloatField, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.responses.models import Response, ResponseAnswer
from apps.surveys.models import Field

# ---------------------------------------------------------------------------
# Cache key helpers & TTLs
# ---------------------------------------------------------------------------

ANALYTICS_TTL = 60 * 5        # 5 minutes — live stats
HISTORICAL_TTL = 60 * 60      # 1 hour — historical reports


def _analytics_key(survey_id) -> str:
    """Return the Redis cache key for a survey's top-level analytics."""
    return f"survey:{survey_id}:analytics"


def _field_analytics_key(survey_id) -> str:
    """Return the Redis cache key for a survey's field-level analytics."""
    return f"survey:{survey_id}:analytics:fields"


def _report_key(survey_id, report_date: str) -> str:
    """Return the Redis cache key for a survey's historical report on a given date."""
    return f"survey:{survey_id}:report:{report_date}"


def invalidate_analytics_cache(survey_id) -> None:
    """Delete all live analytics cache entries for a survey."""
    cache.delete_many([
        _analytics_key(survey_id),
        _field_analytics_key(survey_id),
    ])


# ---------------------------------------------------------------------------
# Survey-level analytics
# ---------------------------------------------------------------------------

def get_survey_analytics(survey_id: str) -> dict:
    """
    Return aggregated stats for a survey.
    Result is cached for ANALYTICS_TTL seconds.
    """
    cache_key = _analytics_key(survey_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = _compute_survey_analytics(survey_id)
    cache.set(cache_key, data, ANALYTICS_TTL)
    return data


def _compute_survey_analytics(survey_id: str) -> dict:
    """Query the DB to build the full analytics payload for a survey (no caching)."""
    base_qs = Response.objects.filter(survey_id=survey_id)

    totals = base_qs.aggregate(
        total=Count("id"),
        complete=Count("id", filter=Q(status=Response.Status.COMPLETE)),
        partial=Count("id", filter=Q(status=Response.Status.PARTIAL)),
    )

    total = totals["total"] or 0
    complete = totals["complete"] or 0
    partial = totals["partial"] or 0
    completion_rate = round((complete / total * 100), 2) if total else 0.0

    avg_seconds = (
        base_qs
        .filter(status=Response.Status.COMPLETE, completed_at__isnull=False)
        .annotate(
            duration=ExpressionWrapper(
                F("completed_at") - F("started_at"),
                output_field=DurationField(),
            )
        )
        .aggregate(avg=Avg("duration"))["avg"]
    )
    # Django returns timedelta in microseconds for Postgres; convert to seconds
    avg_completion_seconds = None
    if avg_seconds is not None:
        try:
            avg_completion_seconds = round(float(avg_seconds.total_seconds()), 2)
        except AttributeError:
            # Fallback: value may already be a float of microseconds
            avg_completion_seconds = round(float(avg_seconds) / 1_000_000, 2)

    # Submissions per day — last 30 days
    since = timezone.now() - timedelta(days=30)
    daily = (
        base_qs
        .filter(started_at__gte=since)
        .annotate(day=TruncDate("started_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    daily_submissions = [
        {"date": str(row["day"]), "count": row["count"]}
        for row in daily
    ]

    return {
        "total_responses": total,
        "complete_responses": complete,
        "partial_responses": partial,
        "completion_rate": completion_rate,
        "avg_completion_time_seconds": avg_completion_seconds,
        "daily_submissions": daily_submissions,
    }


# ---------------------------------------------------------------------------
# Field-level analytics
# ---------------------------------------------------------------------------

def get_field_analytics(survey_id: str) -> list:
    """
    Return per-field answer distribution for a survey.
    Result is cached for ANALYTICS_TTL seconds.
    """
    cache_key = _field_analytics_key(survey_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = _compute_field_analytics(survey_id)
    cache.set(cache_key, data, ANALYTICS_TTL)
    return data


def _compute_field_analytics(survey_id: str) -> list:
    """Query the DB to build per-field answer distributions for a survey (no caching)."""
    fields = (
        Field.objects
        .filter(section__survey_id=survey_id)
        .select_related("section")
        .order_by("section__order", "order")
    )

    result = []
    for field in fields:
        if field.is_sensitive:
            # Never expose encrypted values in analytics
            result.append({
                "field_id": str(field.pk),
                "label": field.label,
                "field_type": field.field_type,
                "response_count": 0,
                "answer_distribution": None,
                "note": "Sensitive field — distribution hidden.",
            })
            continue

        answers_qs = (
            ResponseAnswer.objects
            .filter(
                field=field,
                response__survey_id=survey_id,
                value_text__isnull=False,
            )
        )

        response_count = answers_qs.count()

        distribution = (
            answers_qs
            .exclude(value_text="")
            .values("value_text")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        answer_distribution = [
            {"value": row["value_text"], "count": row["count"]}
            for row in distribution
        ]

        result.append({
            "field_id": str(field.pk),
            "label": field.label,
            "field_type": field.field_type,
            "response_count": response_count,
            "answer_distribution": answer_distribution,
        })

    return result


# ---------------------------------------------------------------------------
# Historical report (cached 1 hour)
# ---------------------------------------------------------------------------

def get_historical_report(survey_id: str, report_date: date) -> dict:
    """Return analytics computed for a specific date (cached 1 hour)."""
    date_str = str(report_date)
    cache_key = _report_key(survey_id, date_str)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    next_day = report_date + timedelta(days=1)
    base_qs = Response.objects.filter(
        survey_id=survey_id,
        started_at__date=report_date,
    )

    totals = base_qs.aggregate(
        total=Count("id"),
        complete=Count("id", filter=Q(status=Response.Status.COMPLETE)),
    )
    total = totals["total"] or 0
    complete = totals["complete"] or 0

    data = {
        "date": date_str,
        "survey_id": str(survey_id),
        "total_responses": total,
        "complete_responses": complete,
        "completion_rate": round((complete / total * 100), 2) if total else 0.0,
    }

    cache.set(cache_key, data, HISTORICAL_TTL)
    return data
