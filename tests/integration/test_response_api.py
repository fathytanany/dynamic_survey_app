"""
Integration tests for the response submission endpoints.
"""
import uuid

import pytest
from rest_framework import status

from apps.responses.models import Response
from apps.surveys.models import Survey
from tests.conftest import make_auth_client
from tests.factories import (
    FieldFactory,
    RequiredFieldFactory,
    ResponseFactory,
    SectionFactory,
    SurveyFactory,
    UserFactory,
    PublishedSurveyFactory,
    AnonymousSurveyFactory,
    SensitiveFieldFactory,
)


BASE = "/api/v1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _answers(*fields, value="answer"):
    return [{"field_id": str(f.pk), "value": value} for f in fields]


# ---------------------------------------------------------------------------
# Submit response
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestSubmitResponse:
    def test_submit_to_published_survey_returns_201(self, db):
        user = UserFactory()
        survey = PublishedSurveyFactory(requires_auth=True)
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section)
        client = make_auth_client(user)
        payload = {
            "answers": _answers(field),
            "status": "complete",
        }
        resp = client.post(f"{BASE}/surveys/{survey.pk}/respond/", payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()["data"]
        assert data["status"] == "complete"
        assert data["session_token"] is not None

    def test_submit_anonymous_survey_without_auth(self, api_client, db):
        survey = AnonymousSurveyFactory()
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section)
        payload = {
            "answers": _answers(field),
            "status": "complete",
        }
        resp = api_client.post(
            f"{BASE}/surveys/{survey.pk}/respond/", payload, format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_submit_to_draft_survey_returns_400(self, db):
        user = UserFactory()
        survey = SurveyFactory(status=Survey.Status.DRAFT)
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section)
        client = make_auth_client(user)
        payload = {"answers": _answers(field), "status": "complete"}
        resp = client.post(f"{BASE}/surveys/{survey.pk}/respond/", payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_submit_to_nonexistent_survey_returns_404(self, db):
        user = UserFactory()
        client = make_auth_client(user)
        payload = {"answers": [], "status": "complete"}
        resp = client.post(
            f"{BASE}/surveys/{uuid.uuid4()}/respond/", payload, format="json"
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_auth_required_survey_unauthenticated_returns_401(self, api_client, db):
        survey = PublishedSurveyFactory(requires_auth=True)
        payload = {"answers": [], "status": "complete"}
        resp = api_client.post(
            f"{BASE}/surveys/{survey.pk}/respond/", payload, format="json"
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_submit_missing_required_field_returns_422(self, db):
        user = UserFactory()
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        RequiredFieldFactory(section=section, label="Name")
        client = make_auth_client(user)
        payload = {"answers": [], "status": "complete"}
        resp = client.post(f"{BASE}/surveys/{survey.pk}/respond/", payload, format="json")
        assert resp.status_code == 422

    def test_partial_save_returns_session_token(self, db):
        user = UserFactory()
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section)
        client = make_auth_client(user)
        payload = {"answers": _answers(field, value="partial"), "status": "partial"}
        resp = client.post(f"{BASE}/surveys/{survey.pk}/respond/", payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        token = resp.json()["data"]["session_token"]
        assert token is not None
        assert Response.objects.filter(session_token=token, status="partial").exists()

    def test_resume_updates_existing_partial(self, db):
        user = UserFactory()
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section)
        client = make_auth_client(user)

        # Create partial
        payload = {"answers": _answers(field, value="first"), "status": "partial"}
        resp1 = client.post(f"{BASE}/surveys/{survey.pk}/respond/", payload, format="json")
        token = resp1.json()["data"]["session_token"]

        # Resume and complete
        payload2 = {
            "answers": _answers(field, value="final"),
            "status": "complete",
            "session_token": token,
        }
        resp2 = client.post(f"{BASE}/surveys/{survey.pk}/respond/", payload2, format="json")
        assert resp2.status_code == status.HTTP_201_CREATED
        assert resp2.json()["data"]["status"] == "complete"
        # Same session token
        assert resp2.json()["data"]["session_token"] == token

    def test_answer_count_matches_submitted_fields(self, db):
        user = UserFactory()
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        fields = FieldFactory.create_batch(5, section=section)
        client = make_auth_client(user)
        payload = {"answers": _answers(*fields), "status": "complete"}
        resp = client.post(f"{BASE}/surveys/{survey.pk}/respond/", payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert len(resp.json()["data"]["answers"]) == 5

    def test_sensitive_field_value_decrypted_in_response(self, db):
        user = UserFactory()
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        field = SensitiveFieldFactory(section=section)
        client = make_auth_client(user)
        payload = {
            "answers": [{"field_id": str(field.pk), "value": "my-ssn"}],
            "status": "complete",
        }
        resp = client.post(f"{BASE}/surveys/{survey.pk}/respond/", payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        answer = resp.json()["data"]["answers"][0]
        assert answer["value"] == "my-ssn"


# ---------------------------------------------------------------------------
# Resume session
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestResumeResponse:
    def test_resume_partial_session_returns_200(self, api_client, db):
        survey = PublishedSurveyFactory()
        ResponseFactory(survey=survey, session_token="resume-me")
        resp = api_client.get(f"{BASE}/responses/resume-me/resume/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"]["session_token"] == "resume-me"

    def test_resume_nonexistent_session_returns_404(self, api_client):
        resp = api_client.get(f"{BASE}/responses/nonexistent-token/resume/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_resume_complete_session_returns_400(self, db, api_client):
        survey = PublishedSurveyFactory()
        from tests.factories import CompleteResponseFactory
        complete = CompleteResponseFactory(survey=survey, session_token="done-already")
        resp = api_client.get(f"{BASE}/responses/done-already/resume/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# My responses
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestMyResponses:
    def test_authenticated_user_sees_own_responses(self, db):
        user = UserFactory()
        survey = PublishedSurveyFactory()
        ResponseFactory.create_batch(3, respondent=user, survey=survey)
        ResponseFactory.create_batch(2, survey=survey)  # other users
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/responses/mine/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()["data"]) == 3

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(f"{BASE}/responses/mine/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_empty_for_user_with_no_responses(self, db):
        user = UserFactory()
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/responses/mine/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"] == []
