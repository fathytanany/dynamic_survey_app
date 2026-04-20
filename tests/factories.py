"""
factory_boy factories for every model in the platform.
Import these in tests; never create model instances by hand.
"""
import uuid

import factory
from factory.django import DjangoModelFactory

from apps.audit.models import AuditLog
from apps.responses.models import Response, ResponseAnswer
from apps.surveys.models import Field, FieldCondition, FieldOption, Section, Survey
from apps.users.models import User


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    id = factory.LazyFunction(uuid.uuid4)
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    role = User.Role.DATA_VIEWER
    is_active = True
    is_staff = False
    password = factory.PostGenerationMethodCall("set_password", "StrongPass123!")


class AdminUserFactory(UserFactory):
    role = User.Role.ADMIN
    is_staff = True


class AnalystUserFactory(UserFactory):
    role = User.Role.ANALYST


# ---------------------------------------------------------------------------
# Surveys
# ---------------------------------------------------------------------------

class SurveyFactory(DjangoModelFactory):
    class Meta:
        model = Survey

    id = factory.LazyFunction(uuid.uuid4)
    title = factory.Sequence(lambda n: f"Survey {n}")
    description = factory.Faker("paragraph")
    owner = factory.SubFactory(UserFactory)
    status = Survey.Status.DRAFT
    version = 1
    is_anonymous = False
    requires_auth = True


class PublishedSurveyFactory(SurveyFactory):
    status = Survey.Status.PUBLISHED


class AnonymousSurveyFactory(SurveyFactory):
    status = Survey.Status.PUBLISHED
    is_anonymous = True
    requires_auth = False


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

class SectionFactory(DjangoModelFactory):
    class Meta:
        model = Section

    id = factory.LazyFunction(uuid.uuid4)
    survey = factory.SubFactory(SurveyFactory)
    title = factory.Sequence(lambda n: f"Section {n}")
    order = factory.Sequence(lambda n: n)
    condition = None


# ---------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------

class FieldFactory(DjangoModelFactory):
    class Meta:
        model = Field

    id = factory.LazyFunction(uuid.uuid4)
    section = factory.SubFactory(SectionFactory)
    label = factory.Sequence(lambda n: f"Field {n}")
    field_type = Field.FieldType.TEXT
    is_required = False
    order = factory.Sequence(lambda n: n)
    is_sensitive = False
    placeholder = ""
    help_text = ""
    config = {}


class RequiredFieldFactory(FieldFactory):
    is_required = True


class SensitiveFieldFactory(FieldFactory):
    is_sensitive = True


class DropdownFieldFactory(FieldFactory):
    field_type = Field.FieldType.DROPDOWN


class NumberFieldFactory(FieldFactory):
    field_type = Field.FieldType.NUMBER


# ---------------------------------------------------------------------------
# Field options
# ---------------------------------------------------------------------------

class FieldOptionFactory(DjangoModelFactory):
    class Meta:
        model = FieldOption

    id = factory.LazyFunction(uuid.uuid4)
    field = factory.SubFactory(DropdownFieldFactory)
    label = factory.Sequence(lambda n: f"Option {n}")
    value = factory.Sequence(lambda n: f"option_{n}")
    order = factory.Sequence(lambda n: n)
    depends_on_option = None


# ---------------------------------------------------------------------------
# Field conditions
# ---------------------------------------------------------------------------

class FieldConditionFactory(DjangoModelFactory):
    class Meta:
        model = FieldCondition

    id = factory.LazyFunction(uuid.uuid4)
    source_field = factory.SubFactory(FieldFactory)
    operator = FieldCondition.Operator.EQUALS
    expected_value = "yes"
    target_field = factory.SubFactory(FieldFactory)
    target_section = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class ResponseFactory(DjangoModelFactory):
    class Meta:
        model = Response

    id = factory.LazyFunction(uuid.uuid4)
    survey = factory.SubFactory(PublishedSurveyFactory)
    respondent = None
    session_token = factory.LazyFunction(lambda: uuid.uuid4().hex)
    status = Response.Status.PARTIAL
    ip_address = "127.0.0.1"
    user_agent = "pytest-test-agent"
    completed_at = None


class CompleteResponseFactory(ResponseFactory):
    status = Response.Status.COMPLETE

    @factory.lazy_attribute
    def completed_at(self):
        from django.utils import timezone
        return timezone.now()


# ---------------------------------------------------------------------------
# Response answers
# ---------------------------------------------------------------------------

class ResponseAnswerFactory(DjangoModelFactory):
    class Meta:
        model = ResponseAnswer

    id = factory.LazyFunction(uuid.uuid4)
    response = factory.SubFactory(ResponseFactory)
    field = factory.SubFactory(FieldFactory)
    value_text = factory.Faker("sentence")
    value_encrypted = None


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------

class AuditLogFactory(DjangoModelFactory):
    class Meta:
        model = AuditLog

    id = factory.LazyFunction(uuid.uuid4)
    user = factory.SubFactory(UserFactory)
    action = AuditLog.Action.CREATE
    model_name = "Survey"
    object_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    changes = {}
    ip_address = "127.0.0.1"
    user_agent = "pytest"
