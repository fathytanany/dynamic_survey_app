import secrets

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.responses.models import Response, ResponseAnswer
from apps.surveys.models import Field, FieldCondition, Survey
from services import analytics_service, encryption_service


# ---------------------------------------------------------------------------
# Conditional logic
# ---------------------------------------------------------------------------

def _evaluate_condition(condition: FieldCondition, answers: dict) -> bool:
    """Return True when the condition is satisfied (target should be shown)."""
    source_value = answers.get(str(condition.source_field_id))
    if source_value is None:
        return False

    op = condition.operator
    expected = condition.expected_value

    if op == FieldCondition.Operator.EQUALS:
        return str(source_value) == expected
    if op == FieldCondition.Operator.NOT_EQUALS:
        return str(source_value) != expected
    if op == FieldCondition.Operator.CONTAINS:
        return expected in str(source_value)
    if op == FieldCondition.Operator.GREATER_THAN:
        try:
            return float(source_value) > float(expected)
        except (ValueError, TypeError):
            return False
    if op == FieldCondition.Operator.LESS_THAN:
        try:
            return float(source_value) < float(expected)
        except (ValueError, TypeError):
            return False
    return False


def get_active_field_ids(survey: Survey, answers: dict) -> set:
    """
    Return the set of field IDs that are currently visible given the provided answers.

    A field (or section) gated by a FieldCondition is hidden by default and becomes
    visible only when its condition evaluates to True.  Fields with no incoming
    conditions are always visible.
    """
    conditions = (
        FieldCondition.objects
        .filter(source_field__section__survey=survey)
        .select_related("target_field", "target_section")
    )

    gated_fields: set = set()
    gated_sections: set = set()
    unlocked_fields: set = set()
    unlocked_sections: set = set()

    for cond in conditions:
        if cond.target_field_id:
            gated_fields.add(str(cond.target_field_id))
        if cond.target_section_id:
            gated_sections.add(str(cond.target_section_id))

        if _evaluate_condition(cond, answers):
            if cond.target_field_id:
                unlocked_fields.add(str(cond.target_field_id))
            if cond.target_section_id:
                unlocked_sections.add(str(cond.target_section_id))

    all_fields = (
        Field.objects
        .filter(section__survey=survey)
        .values("id", "section_id")
    )

    active: set = set()
    for row in all_fields:
        fid = str(row["id"])
        sid = str(row["section_id"])

        section_hidden = sid in gated_sections and sid not in unlocked_sections
        field_hidden = fid in gated_fields and fid not in unlocked_fields

        if not section_hidden and not field_hidden:
            active.add(fid)

    return active


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_answers(survey: Survey, answers: list, is_complete: bool) -> dict:
    """
    Build answer dict and, for complete submissions, enforce required fields
    that are currently visible.  Returns {str(field_id): value}.
    Raises ValidationError on failure.
    """
    answers_dict = {str(a["field_id"]): a.get("value") or "" for a in answers}

    if not is_complete:
        return answers_dict

    active_ids = get_active_field_ids(survey, answers_dict)

    required_fields = Field.objects.filter(
        section__survey=survey, is_required=True
    ).only("id", "label")

    errors: dict = {}
    for field in required_fields:
        fid = str(field.pk)
        if fid not in active_ids:
            continue
        value = answers_dict.get(fid)
        if not value and value != 0:
            errors[fid] = f"'{field.label}' is required."

    if errors:
        raise ValidationError(errors)

    return answers_dict


# ---------------------------------------------------------------------------
# Save response (submit or partial)
# ---------------------------------------------------------------------------

@transaction.atomic
def save_response(survey: Survey, data: dict, request) -> Response:
    """
    Create or update a Response with its answers.

    - If data contains a valid session_token for an existing partial Response,
      that Response is updated in place (old answers replaced).
    - Answers for sensitive fields are Fernet-encrypted via encryption_service.
    - All ResponseAnswer rows are written with a single bulk_create call.
    """
    answers = data["answers"]
    status = data.get("status", Response.Status.COMPLETE)
    session_token = data.get("session_token") or None
    is_complete = status == Response.Status.COMPLETE

    answers_dict = _validate_answers(survey, answers, is_complete)

    # Resolve existing partial session
    response: Response | None = None
    if session_token:
        response = (
            Response.objects
            .filter(session_token=session_token, status=Response.Status.PARTIAL)
            .first()
        )

    ip_address = _get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    respondent = request.user if request.user.is_authenticated else None

    if response is None:
        response = Response.objects.create(
            survey=survey,
            respondent=respondent,
            session_token=secrets.token_urlsafe(32),
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            completed_at=timezone.now() if is_complete else None,
        )
    else:
        response.answers.all().delete()
        response.status = status
        response.completed_at = timezone.now() if is_complete else None
        response.save(update_fields=["status", "completed_at"])

    # Resolve fields in one query
    field_ids = list(answers_dict.keys())
    fields_map: dict = {
        str(f.pk): f
        for f in Field.objects.filter(pk__in=field_ids).only("id", "is_sensitive")
    }

    answer_objs: list[ResponseAnswer] = []
    for field_id, value in answers_dict.items():
        field = fields_map.get(field_id)
        if field is None:
            continue

        if field.is_sensitive:
            answer_objs.append(ResponseAnswer(
                response=response,
                field=field,
                value_text=None,
                value_encrypted=encryption_service.encrypt(value),
            ))
        else:
            answer_objs.append(ResponseAnswer(
                response=response,
                field=field,
                value_text=value,
                value_encrypted=None,
            ))

    ResponseAnswer.objects.bulk_create(answer_objs)

    # Invalidate analytics cache so next read reflects this submission
    analytics_service.invalidate_analytics_cache(str(survey.pk))

    return response


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_response_by_session(session_token: str) -> Response | None:
    try:
        return (
            Response.objects
            .select_related("survey", "respondent")
            .prefetch_related("answers__field")
            .get(session_token=session_token)
        )
    except Response.DoesNotExist:
        return None


def get_user_responses(user):
    return (
        Response.objects
        .filter(respondent=user)
        .select_related("survey")
        .prefetch_related("answers__field")
        .order_by("-started_at")
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "127.0.0.1")
