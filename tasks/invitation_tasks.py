from celery import shared_task
from django.core.cache import cache
from django.core.mail import send_mass_mail
from django.conf import settings

from apps.surveys.models import Survey

# TTL for task result metadata stored in Redis (24 hours)
TASK_RESULT_TTL = 60 * 60 * 24


def _task_meta_key(task_id: str) -> str:
    return f"task:{task_id}:meta"


@shared_task(bind=True)
def send_survey_invitations(self, survey_id: str, email_list: list):
    """
    Send survey invitation emails to a list of recipients.

    Args:
        survey_id: UUID string of the survey to invite respondents to.
        email_list: List of email address strings to send invitations to.

    Stores result metadata in Redis under task:{task_id}:meta for polling.
    """
    task_id = self.request.id
    cache.set(_task_meta_key(task_id), {"status": "started", "result": None}, TASK_RESULT_TTL)

    try:
        survey = Survey.objects.get(id=survey_id)

        subject = f"You're invited to complete: {survey.title}"
        survey_url = f"{settings.FRONTEND_URL}/surveys/{survey_id}/" if hasattr(settings, "FRONTEND_URL") else f"/surveys/{survey_id}/"

        body = (
            f"Hello,\n\n"
            f"You have been invited to complete the survey: \"{survey.title}\".\n\n"
            f"{survey.description}\n\n"
            f"Click the link below to start:\n{survey_url}\n\n"
            f"This invitation was sent on behalf of the survey owner.\n"
        )

        from_email = settings.DEFAULT_FROM_EMAIL
        messages = tuple(
            (subject, body, from_email, [email])
            for email in email_list
            if email and "@" in email
        )

        sent_count = send_mass_mail(messages, fail_silently=False)

        result = {
            "survey_id": survey_id,
            "survey_title": survey.title,
            "requested": len(email_list),
            "sent": sent_count,
        }
        cache.set(_task_meta_key(task_id), {"status": "success", "result": result}, TASK_RESULT_TTL)
        return result

    except Survey.DoesNotExist:
        meta = {"status": "failure", "result": {"error": f"Survey {survey_id} not found"}}
        cache.set(_task_meta_key(task_id), meta, TASK_RESULT_TTL)
        raise

    except Exception as exc:
        meta = {"status": "failure", "result": {"error": str(exc)}}
        cache.set(_task_meta_key(task_id), meta, TASK_RESULT_TTL)
        raise
