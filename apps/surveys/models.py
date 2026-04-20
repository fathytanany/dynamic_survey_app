import uuid

from django.conf import settings
from django.db import models


class Survey(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="surveys",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_anonymous = models.BooleanField(default=False)
    requires_auth = models.BooleanField(default=True)

    class Meta:
        db_table = "surveys"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Section(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    # FK to FieldCondition defined after that model is created; nullable so sections
    # can exist without a condition.
    condition = models.ForeignKey(
        "FieldCondition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conditioned_sections",
    )

    class Meta:
        db_table = "survey_sections"
        ordering = ["order"]

    def __str__(self):
        return f"{self.survey.title} — {self.title}"


class Field(models.Model):
    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        NUMBER = "number", "Number"
        DATE = "date", "Date"
        DROPDOWN = "dropdown", "Dropdown"
        CHECKBOX = "checkbox", "Checkbox"
        RADIO = "radio", "Radio"
        TEXTAREA = "textarea", "Textarea"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="fields")
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FieldType.choices)
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    is_sensitive = models.BooleanField(default=False)
    placeholder = models.CharField(max_length=255, blank=True)
    help_text = models.CharField(max_length=500, blank=True)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "survey_fields"
        ordering = ["order"]

    def __str__(self):
        return f"{self.section.title} — {self.label}"


class FieldOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    depends_on_option = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dependent_options",
    )

    class Meta:
        db_table = "survey_field_options"
        ordering = ["order"]

    def __str__(self):
        return f"{self.field.label} — {self.label}"


class FieldCondition(models.Model):
    class Operator(models.TextChoices):
        EQUALS = "equals", "Equals"
        NOT_EQUALS = "not_equals", "Not Equals"
        CONTAINS = "contains", "Contains"
        GREATER_THAN = "greater_than", "Greater Than"
        LESS_THAN = "less_than", "Less Than"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        related_name="conditions_as_source",
    )
    operator = models.CharField(max_length=20, choices=Operator.choices)
    expected_value = models.CharField(max_length=255)
    target_field = models.ForeignKey(
        Field,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="conditions_as_target",
    )
    target_section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="conditions_as_target",
    )

    class Meta:
        db_table = "survey_field_conditions"

    def __str__(self):
        return f"{self.source_field.label} {self.operator} {self.expected_value}"
