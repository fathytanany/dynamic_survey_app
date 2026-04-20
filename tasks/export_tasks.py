import csv
import io
import json

from celery import shared_task
from django.core.cache import cache

from apps.responses.models import Response, ResponseAnswer
from services import encryption_service

# TTL for task result metadata stored in Redis (24 hours)
TASK_RESULT_TTL = 60 * 60 * 24


def _task_meta_key(task_id: str) -> str:
    return f"task:{task_id}:meta"


@shared_task(bind=True)
def export_responses(self, survey_id: str, user_id: str, format: str = "json"):
    """
    Export all complete responses for a survey.

    Args:
        survey_id: UUID string of the survey.
        user_id: UUID string of the requesting user (for audit purposes).
        format: "json" or "csv".

    Stores serialised export payload + metadata in Redis under task:{task_id}:meta.
    Sensitive fields are excluded from the export.
    """
    task_id = self.request.id
    cache.set(_task_meta_key(task_id), {"status": "started", "result": None}, TASK_RESULT_TTL)

    try:
        responses = (
            Response.objects
            .filter(survey_id=survey_id, status=Response.Status.COMPLETE)
            .prefetch_related("answers__field")
            .select_related("respondent")
            .order_by("started_at")
        )

        rows = []
        for resp in responses:
            row = {
                "response_id": str(resp.id),
                "respondent": str(resp.respondent_id) if resp.respondent_id else None,
                "started_at": resp.started_at.isoformat(),
                "completed_at": resp.completed_at.isoformat() if resp.completed_at else None,
                "ip_address": resp.ip_address,
                "answers": [],
            }
            for answer in resp.answers.all():
                if answer.field.is_sensitive:
                    continue  # never export encrypted data
                row["answers"].append({
                    "field_id": str(answer.field_id),
                    "field_label": answer.field.label,
                    "value": answer.value_text,
                })
            rows.append(row)

        if format == "csv":
            payload = _to_csv(rows)
            content_type = "text/csv"
        else:
            payload = json.dumps(rows, ensure_ascii=False)
            content_type = "application/json"

        result = {
            "survey_id": survey_id,
            "format": format,
            "content_type": content_type,
            "total_rows": len(rows),
            "data": payload,
        }

        meta = {"status": "success", "result": result}
        cache.set(_task_meta_key(task_id), meta, TASK_RESULT_TTL)
        return result

    except Exception as exc:
        meta = {"status": "failure", "result": {"error": str(exc)}}
        cache.set(_task_meta_key(task_id), meta, TASK_RESULT_TTL)
        raise


def _to_csv(rows: list) -> str:
    """Flatten nested response rows into a CSV string."""
    if not rows:
        return ""

    # Collect all unique field labels across all responses
    field_labels: list = []
    seen: set = set()
    for row in rows:
        for answer in row["answers"]:
            label = answer["field_label"]
            if label not in seen:
                field_labels.append(label)
                seen.add(label)

    base_cols = ["response_id", "respondent", "started_at", "completed_at", "ip_address"]
    fieldnames = base_cols + field_labels

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for row in rows:
        flat = {col: row.get(col) for col in base_cols}
        for answer in row["answers"]:
            flat[answer["field_label"]] = answer["value"]
        writer.writerow(flat)

    return buf.getvalue()
