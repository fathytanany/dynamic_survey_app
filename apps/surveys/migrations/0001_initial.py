import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Survey
        migrations.CreateModel(
            name="Survey",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="surveys",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("published", "Published"), ("archived", "Archived")],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_anonymous", models.BooleanField(default=False)),
                ("requires_auth", models.BooleanField(default=True)),
            ],
            options={"db_table": "surveys", "ordering": ["-created_at"]},
        ),
        # 2. Section — without condition FK (added later to break circular dep)
        migrations.CreateModel(
            name="Section",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "survey",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sections",
                        to="surveys.survey",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("order", models.PositiveIntegerField(default=0)),
            ],
            options={"db_table": "survey_sections", "ordering": ["order"]},
        ),
        # 3. Field
        migrations.CreateModel(
            name="Field",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "section",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fields",
                        to="surveys.section",
                    ),
                ),
                ("label", models.CharField(max_length=255)),
                (
                    "field_type",
                    models.CharField(
                        choices=[
                            ("text", "Text"),
                            ("number", "Number"),
                            ("date", "Date"),
                            ("dropdown", "Dropdown"),
                            ("checkbox", "Checkbox"),
                            ("radio", "Radio"),
                            ("textarea", "Textarea"),
                        ],
                        max_length=20,
                    ),
                ),
                ("is_required", models.BooleanField(default=False)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_sensitive", models.BooleanField(default=False)),
                ("placeholder", models.CharField(blank=True, max_length=255)),
                ("help_text", models.CharField(blank=True, max_length=500)),
                ("config", models.JSONField(blank=True, default=dict)),
            ],
            options={"db_table": "survey_fields", "ordering": ["order"]},
        ),
        # 4. FieldOption (self-referential FK is fine as a deferred constraint)
        migrations.CreateModel(
            name="FieldOption",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "field",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="options",
                        to="surveys.field",
                    ),
                ),
                ("label", models.CharField(max_length=255)),
                ("value", models.CharField(max_length=255)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "depends_on_option",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dependent_options",
                        to="surveys.fieldoption",
                    ),
                ),
            ],
            options={"db_table": "survey_field_options", "ordering": ["order"]},
        ),
        # 5. FieldCondition (references Field and Section — both exist now)
        migrations.CreateModel(
            name="FieldCondition",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "source_field",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conditions_as_source",
                        to="surveys.field",
                    ),
                ),
                (
                    "operator",
                    models.CharField(
                        choices=[
                            ("equals", "Equals"),
                            ("not_equals", "Not Equals"),
                            ("contains", "Contains"),
                            ("greater_than", "Greater Than"),
                            ("less_than", "Less Than"),
                        ],
                        max_length=20,
                    ),
                ),
                ("expected_value", models.CharField(max_length=255)),
                (
                    "target_field",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conditions_as_target",
                        to="surveys.field",
                    ),
                ),
                (
                    "target_section",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conditions_as_target",
                        to="surveys.section",
                    ),
                ),
            ],
            options={"db_table": "survey_field_conditions"},
        ),
        # 6. Add condition FK to Section (breaks the circular dependency)
        migrations.AddField(
            model_name="section",
            name="condition",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="conditioned_sections",
                to="surveys.fieldcondition",
            ),
        ),
    ]
