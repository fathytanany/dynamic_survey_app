import uuid

from django.conf import settings
from django.db import models

from apps.surveys.models import Field, Survey


class Response(models.Model):
    class Status(models.TextChoices):
        PARTIAL = "partial", "Partial"
        COMPLETE = "complete", "Complete"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="responses")
    respondent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responses",
    )
    session_token = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PARTIAL)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        db_table = "survey_responses"
        ordering = ["-started_at"]

    def __str__(self):
        return f"Response {self.id} — {self.survey.title} [{self.status}]"


class ResponseAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name="answers")
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="answers")
    value_text = models.TextField(null=True, blank=True)
    value_encrypted = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "survey_response_answers"

    def __str__(self):
        return f"Answer {self.id} — field {self.field_id}"
