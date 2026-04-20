"""
Unit tests for services/response_service.py.
"""
import pytest
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError

from apps.responses.models import Response, ResponseAnswer
from apps.surveys.models import Field
from services import response_service
from tests.factories import (
    FieldFactory,
    RequiredFieldFactory,
    ResponseFactory,
    SectionFactory,
    SensitiveFieldFactory,
    SurveyFactory,
    UserFactory,
    PublishedSurveyFactory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(user=None, ip="127.0.0.1", user_agent="test-agent"):
    """Return a minimal mock Request object."""
    req = MagicMock()
    if user is None:
        anon = MagicMock()
        anon.is_authenticated = False
        req.user = anon
    else:
        req.user = user  # real User model — is_authenticated is a live property
    req.META = {
        "REMOTE_ADDR": ip,
        "HTTP_USER_AGENT": user_agent,
    }
    return req


def _answers_from_fields(*fields, value="answer"):
    return [{"field_id": str(f.pk), "value": value} for f in fields]


# ---------------------------------------------------------------------------
# save_response — complete submissions
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.django_db
class TestSaveResponseComplete:
    def test_creates_complete_response(self, db):
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section)
        data = {
            "answers": _answers_from_fields(field),
            "status": Response.Status.COMPLETE,
        }
        resp = response_service.save_response(survey, data, _make_request())
        assert resp.status == Response.Status.COMPLETE
        assert resp.completed_at is not None
        assert resp.survey == survey

    def test_creates_answer_records(self, db):
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        fields = FieldFactory.create_batch(3, section=section)
        data = {
            "answers": _answers_from_fields(*fields),
            "status": Response.Status.COMPLETE,
        }
        resp = response_service.save_response(survey, data, _make_request())
        assert resp.answers.count() == 3

    def test_sets_respondent_for_authenticated_user(self, db):
        user = UserFactory()
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        data = {
            "answers": [],
            "status": Response.Status.COMPLETE,
        }
        resp = response_service.save_response(survey, data, _make_request(user=user))
        assert resp.respondent == user

    def test_respondent_null_for_anonymous(self, db):
        survey = PublishedSurveyFactory()
        data = {"answers": [], "status": Response.Status.COMPLETE}
        resp = response_service.save_response(survey, data, _make_request())
        assert resp.respondent is None

    def test_assigns_session_token(self, db):
        survey = PublishedSurveyFactory()
        data = {"answers": [], "status": Response.Status.COMPLETE}
        resp = response_service.save_response(survey, data, _make_request())
        assert resp.session_token
        assert len(resp.session_token) > 10

    def test_ip_address_captured(self, db):
        survey = PublishedSurveyFactory()
        data = {"answers": [], "status": Response.Status.COMPLETE}
        resp = response_service.save_response(
            survey, data, _make_request(ip="192.168.1.100")
        )
        assert resp.ip_address == "192.168.1.100"

    def test_forwarded_ip_used_when_present(self, db):
        survey = PublishedSurveyFactory()
        req = _make_request()
        req.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1, 172.16.0.1"
        data = {"answers": [], "status": Response.Status.COMPLETE}
        resp = response_service.save_response(survey, data, req)
        assert resp.ip_address == "10.0.0.1"


# ---------------------------------------------------------------------------
# save_response — partial saves
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.django_db
class TestSaveResponsePartial:
    def test_creates_partial_response(self, db):
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section)
        data = {
            "answers": _answers_from_fields(field),
            "status": Response.Status.PARTIAL,
        }
        resp = response_service.save_response(survey, data, _make_request())
        assert resp.status == Response.Status.PARTIAL
        assert resp.completed_at is None

    def test_resumes_partial_session(self, db):
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section)

        # First save
        data = {
            "answers": _answers_from_fields(field, value="first"),
            "status": Response.Status.PARTIAL,
        }
        partial = response_service.save_response(survey, data, _make_request())
        token = partial.session_token

        # Resume with same token, different value
        data2 = {
            "answers": _answers_from_fields(field, value="updated"),
            "status": Response.Status.COMPLETE,
            "session_token": token,
        }
        completed = response_service.save_response(survey, data2, _make_request())
        assert completed.pk == partial.pk
        assert completed.status == Response.Status.COMPLETE
        assert completed.answers.first().value_text == "updated"

    def test_resume_with_unknown_token_creates_new_response(self, db):
        survey = PublishedSurveyFactory()
        data = {
            "answers": [],
            "status": Response.Status.COMPLETE,
            "session_token": "nonexistent-token",
        }
        resp = response_service.save_response(survey, data, _make_request())
        assert resp.session_token != "nonexistent-token"


# ---------------------------------------------------------------------------
# Sensitive field encryption
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.django_db
class TestSensitiveFieldEncryption:
    def test_sensitive_answer_is_encrypted(self, db):
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        field = SensitiveFieldFactory(section=section)
        data = {
            "answers": [{"field_id": str(field.pk), "value": "secret_value"}],
            "status": Response.Status.COMPLETE,
        }
        resp = response_service.save_response(survey, data, _make_request())
        answer = resp.answers.first()
        assert answer.value_text is None
        assert answer.value_encrypted is not None
        # Ciphertext must not be the plaintext
        assert b"secret_value" not in bytes(answer.value_encrypted)

    def test_non_sensitive_answer_is_plaintext(self, db):
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section, is_sensitive=False)
        data = {
            "answers": [{"field_id": str(field.pk), "value": "plain_value"}],
            "status": Response.Status.COMPLETE,
        }
        resp = response_service.save_response(survey, data, _make_request())
        answer = resp.answers.first()
        assert answer.value_text == "plain_value"
        assert answer.value_encrypted is None


# ---------------------------------------------------------------------------
# Validation — required fields
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.django_db
class TestRequiredFieldValidation:
    def test_missing_required_field_raises_on_complete(self, db):
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        RequiredFieldFactory(section=section, label="Email")
        data = {
            "answers": [],  # required field omitted
            "status": Response.Status.COMPLETE,
        }
        with pytest.raises(ValidationError):
            response_service.save_response(survey, data, _make_request())

    def test_missing_required_field_ok_on_partial(self, db):
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        RequiredFieldFactory(section=section, label="Email")
        data = {
            "answers": [],
            "status": Response.Status.PARTIAL,
        }
        resp = response_service.save_response(survey, data, _make_request())
        assert resp.status == Response.Status.PARTIAL

    def test_empty_string_fails_required(self, db):
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        field = RequiredFieldFactory(section=section)
        data = {
            "answers": [{"field_id": str(field.pk), "value": ""}],
            "status": Response.Status.COMPLETE,
        }
        with pytest.raises(ValidationError):
            response_service.save_response(survey, data, _make_request())

    def test_all_required_fields_provided_succeeds(self, db):
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        field = RequiredFieldFactory(section=section)
        data = {
            "answers": [{"field_id": str(field.pk), "value": "value"}],
            "status": Response.Status.COMPLETE,
        }
        resp = response_service.save_response(survey, data, _make_request())
        assert resp.status == Response.Status.COMPLETE


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.django_db
class TestResponseQueries:
    def test_get_response_by_session_found(self, db):
        response = ResponseFactory(session_token="abc123")
        result = response_service.get_response_by_session("abc123")
        assert result is not None
        assert result.pk == response.pk

    def test_get_response_by_session_not_found(self, db):
        result = response_service.get_response_by_session("no-such-token")
        assert result is None

    def test_get_user_responses(self, db):
        user = UserFactory()
        ResponseFactory.create_batch(3, respondent=user)
        ResponseFactory.create_batch(2)  # another user
        results = list(response_service.get_user_responses(user))
        assert len(results) == 3
        assert all(r.respondent_id == user.pk for r in results)

    def test_get_user_responses_empty(self, db):
        user = UserFactory()
        results = list(response_service.get_user_responses(user))
        assert results == []


# ---------------------------------------------------------------------------
# Analytics cache invalidation called on save
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.django_db
class TestAnalyticsCacheInvalidation:
    def test_cache_invalidated_after_save(self, db):
        survey = PublishedSurveyFactory()
        data = {"answers": [], "status": Response.Status.COMPLETE}
        with patch("services.response_service.analytics_service.invalidate_analytics_cache") as mock_inv:
            response_service.save_response(survey, data, _make_request())
        mock_inv.assert_called_once_with(str(survey.pk))
