"""
Integration tests for the analytics endpoints.
"""
import uuid
from unittest.mock import patch

import pytest
from rest_framework import status

from tests.conftest import make_auth_client
from tests.factories import (
    AnalystUserFactory,
    CompleteResponseFactory,
    FieldFactory,
    ResponseAnswerFactory,
    ResponseFactory,
    SectionFactory,
    SurveyFactory,
    UserFactory,
    PublishedSurveyFactory,
)


BASE = "/api/v1"


# ---------------------------------------------------------------------------
# Survey analytics
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestSurveyAnalytics:
    def test_data_viewer_can_access(self, db):
        user = UserFactory(role="data_viewer")
        survey = PublishedSurveyFactory()
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/surveys/{survey.pk}/analytics/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()["data"]
        assert "total_responses" in data
        assert "completion_rate" in data
        assert "daily_submissions" in data

    def test_analyst_can_access(self, db):
        analyst = AnalystUserFactory()
        survey = PublishedSurveyFactory()
        client = make_auth_client(analyst)
        resp = client.get(f"{BASE}/surveys/{survey.pk}/analytics/")
        assert resp.status_code == status.HTTP_200_OK

    def test_unauthenticated_returns_401(self, api_client, db):
        survey = PublishedSurveyFactory()
        resp = api_client.get(f"{BASE}/surveys/{survey.pk}/analytics/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_nonexistent_survey_returns_404(self, db):
        user = UserFactory(role="data_viewer")
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/surveys/{uuid.uuid4()}/analytics/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_totals_computed_correctly(self, db):
        user = UserFactory(role="data_viewer")
        survey = PublishedSurveyFactory()
        CompleteResponseFactory.create_batch(3, survey=survey)
        ResponseFactory.create_batch(2, survey=survey, status="partial")
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/surveys/{survey.pk}/analytics/")
        data = resp.json()["data"]
        assert data["total_responses"] == 5
        assert data["complete_responses"] == 3
        assert data["partial_responses"] == 2

    def test_completion_rate_calculated(self, db):
        user = UserFactory(role="data_viewer")
        survey = PublishedSurveyFactory()
        CompleteResponseFactory.create_batch(2, survey=survey)
        ResponseFactory.create_batch(2, survey=survey, status="partial")
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/surveys/{survey.pk}/analytics/")
        assert resp.json()["data"]["completion_rate"] == 50.0

    def test_empty_survey_returns_zero_stats(self, db):
        user = UserFactory(role="data_viewer")
        survey = PublishedSurveyFactory()
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/surveys/{survey.pk}/analytics/")
        data = resp.json()["data"]
        assert data["total_responses"] == 0
        assert data["completion_rate"] == 0.0

    def test_response_cached_on_second_call(self, db):
        user = UserFactory(role="data_viewer")
        survey = PublishedSurveyFactory()
        client = make_auth_client(user)
        with patch("services.analytics_service.cache") as mock_cache:
            # Simulate cache hit on second call
            mock_cache.get.return_value = None
            client.get(f"{BASE}/surveys/{survey.pk}/analytics/")
            mock_cache.set.assert_called()


# ---------------------------------------------------------------------------
# Field analytics
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestFieldAnalytics:
    def test_returns_per_field_breakdown(self, db):
        user = UserFactory(role="data_viewer")
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        FieldFactory.create_batch(3, section=section)
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/surveys/{survey.pk}/analytics/fields/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()["data"]) == 3

    def test_sensitive_field_distribution_hidden(self, db):
        from tests.factories import SensitiveFieldFactory
        user = UserFactory(role="data_viewer")
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        SensitiveFieldFactory(section=section)
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/surveys/{survey.pk}/analytics/fields/")
        assert resp.status_code == status.HTTP_200_OK
        field_data = resp.json()["data"][0]
        assert field_data["answer_distribution"] is None

    def test_unauthenticated_returns_401(self, api_client, db):
        survey = PublishedSurveyFactory()
        resp = api_client.get(f"{BASE}/surveys/{survey.pk}/analytics/fields/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_field_answer_distribution_populated(self, db):
        user = UserFactory(role="data_viewer")
        survey = PublishedSurveyFactory()
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section, field_type="radio")
        # Two "yes" answers, one "no"
        resp_a = ResponseFactory(survey=survey)
        resp_b = ResponseFactory(survey=survey)
        resp_c = ResponseFactory(survey=survey)
        ResponseAnswerFactory(response=resp_a, field=field, value_text="yes")
        ResponseAnswerFactory(response=resp_b, field=field, value_text="yes")
        ResponseAnswerFactory(response=resp_c, field=field, value_text="no")
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/surveys/{survey.pk}/analytics/fields/")
        assert resp.status_code == status.HTTP_200_OK
        dist = resp.json()["data"][0]["answer_distribution"]
        counts = {d["value"]: d["count"] for d in dist}
        assert counts["yes"] == 2
        assert counts["no"] == 1


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestExportResponses:
    def test_analyst_can_trigger_export(self, db):
        analyst = AnalystUserFactory()
        survey = PublishedSurveyFactory()
        client = make_auth_client(analyst)
        with patch("apps.analytics.views.export_responses") as mock_task:
            mock_task.delay.return_value.id = "fake-task-id"
            resp = client.post(
                f"{BASE}/surveys/{survey.pk}/export/",
                {"format": "csv"},
                format="json",
            )
        assert resp.status_code == 202
        assert resp.json()["data"]["task_id"] == "fake-task-id"

    def test_data_viewer_cannot_export(self, db):
        user = UserFactory(role="data_viewer")
        survey = PublishedSurveyFactory()
        client = make_auth_client(user)
        resp = client.post(
            f"{BASE}/surveys/{survey.pk}/export/",
            {"format": "csv"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_export(self, api_client, db):
        survey = PublishedSurveyFactory()
        resp = api_client.post(
            f"{BASE}/surveys/{survey.pk}/export/",
            {"format": "csv"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_export_nonexistent_survey_returns_404(self, db):
        analyst = AnalystUserFactory()
        client = make_auth_client(analyst)
        resp = client.post(
            f"{BASE}/surveys/{uuid.uuid4()}/export/",
            {"format": "csv"},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_invalid_format_returns_400(self, db):
        analyst = AnalystUserFactory()
        survey = PublishedSurveyFactory()
        client = make_auth_client(analyst)
        resp = client.post(
            f"{BASE}/surveys/{survey.pk}/export/",
            {"format": "pdf"},  # not in choices
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Task status
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestTaskStatus:
    def test_returns_task_status(self, db):
        user = UserFactory(role="data_viewer")
        client = make_auth_client(user)
        task_id = "some-celery-task-id"
        # AsyncResult is imported inside the view method, patch at source module
        with patch("celery.result.AsyncResult") as mock_result_cls:
            mock_instance = mock_result_cls.return_value
            mock_instance.state = "SUCCESS"
            mock_instance.result = {"url": "s3://bucket/file.csv"}
            resp = client.get(f"{BASE}/tasks/{task_id}/status/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()["data"]
        assert "task_id" in data
        assert "status" in data

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(f"{BASE}/tasks/some-task/status/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
