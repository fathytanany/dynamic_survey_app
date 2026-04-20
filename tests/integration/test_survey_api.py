"""
Integration tests for the surveys, sections, fields, and conditions endpoints.
"""
import uuid

import pytest
from rest_framework import status

from apps.surveys.models import Field, FieldCondition, Section, Survey
from tests.conftest import make_auth_client
from tests.factories import (
    AdminUserFactory,
    FieldConditionFactory,
    FieldFactory,
    SectionFactory,
    SurveyFactory,
    UserFactory,
)


BASE = "/api/v1"


# ---------------------------------------------------------------------------
# Survey list / create
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestSurveyList:
    def test_authenticated_user_can_list(self, db):
        user = UserFactory()
        SurveyFactory.create_batch(3)
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/surveys/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()["data"]) >= 3

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(f"{BASE}/surveys/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_survey_returns_201(self, db):
        user = UserFactory()
        client = make_auth_client(user)
        payload = {"title": "Customer Feedback", "description": "Tell us how we did."}
        resp = client.post(f"{BASE}/surveys/", payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()["data"]
        assert data["title"] == "Customer Feedback"
        assert data["status"] == Survey.Status.DRAFT

    def test_create_survey_sets_owner_to_requester(self, db):
        user = UserFactory()
        client = make_auth_client(user)
        resp = client.post(f"{BASE}/surveys/", {"title": "Mine"}, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["data"]["owner"]["email"] == user.email

    def test_create_survey_missing_title_returns_400(self, db):
        user = UserFactory()
        client = make_auth_client(user)
        resp = client.post(f"{BASE}/surveys/", {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Survey detail / update / delete
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestSurveyDetail:
    def test_get_returns_nested_structure(self, db):
        user = UserFactory()
        survey = SurveyFactory(owner=user)
        SectionFactory.create_batch(2, survey=survey)
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/surveys/{survey.pk}/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()["data"]["sections"]) == 2

    def test_get_nonexistent_returns_404(self, db):
        user = UserFactory()
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/surveys/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_owner_can_update(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner, title="Old Title")
        client = make_auth_client(owner)
        resp = client.put(
            f"{BASE}/surveys/{survey.pk}/",
            {"title": "New Title"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"]["title"] == "New Title"

    def test_non_owner_cannot_update(self, db):
        owner = UserFactory()
        other = UserFactory()
        survey = SurveyFactory(owner=owner)
        client = make_auth_client(other)
        resp = client.put(
            f"{BASE}/surveys/{survey.pk}/",
            {"title": "Hijack"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_update_any_survey(self, db):
        owner = UserFactory()
        admin = AdminUserFactory()
        survey = SurveyFactory(owner=owner)
        client = make_auth_client(admin)
        resp = client.put(
            f"{BASE}/surveys/{survey.pk}/",
            {"title": "Admin Edit"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_owner_can_delete(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner)
        client = make_auth_client(owner)
        resp = client.delete(f"{BASE}/surveys/{survey.pk}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not Survey.objects.filter(pk=survey.pk).exists()

    def test_non_owner_cannot_delete(self, db):
        owner = UserFactory()
        other = UserFactory()
        survey = SurveyFactory(owner=owner)
        client = make_auth_client(other)
        resp = client.delete(f"{BASE}/surveys/{survey.pk}/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestPublishSurvey:
    def test_publish_draft_returns_200(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner, status=Survey.Status.DRAFT)
        client = make_auth_client(owner)
        resp = client.post(f"{BASE}/surveys/{survey.pk}/publish/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"]["status"] == Survey.Status.PUBLISHED

    def test_publish_already_published_returns_400(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner, status=Survey.Status.PUBLISHED)
        client = make_auth_client(owner)
        resp = client.post(f"{BASE}/surveys/{survey.pk}/publish/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_owner_publish_returns_403(self, db):
        owner = UserFactory()
        other = UserFactory()
        survey = SurveyFactory(owner=owner, status=Survey.Status.DRAFT)
        client = make_auth_client(other)
        resp = client.post(f"{BASE}/surveys/{survey.pk}/publish/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_publish_nonexistent_returns_404(self, db):
        user = UserFactory()
        client = make_auth_client(user)
        resp = client.post(f"{BASE}/surveys/{uuid.uuid4()}/publish/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Clone
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestCloneSurvey:
    def test_clone_returns_201(self, db):
        user = UserFactory()
        survey = SurveyFactory(owner=user)
        client = make_auth_client(user)
        resp = client.post(f"{BASE}/surveys/{survey.pk}/clone/")
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()["data"]
        assert data["id"] != str(survey.pk)
        assert "Copy of" in data["title"]
        assert data["status"] == Survey.Status.DRAFT


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestSectionAPI:
    def test_list_sections(self, db):
        user = UserFactory()
        survey = SurveyFactory(owner=user)
        SectionFactory.create_batch(3, survey=survey)
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/surveys/{survey.pk}/sections/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()["data"]) == 3

    def test_create_section(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner)
        client = make_auth_client(owner)
        resp = client.post(
            f"{BASE}/surveys/{survey.pk}/sections/",
            {"title": "Demographics", "order": 1},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["data"]["title"] == "Demographics"

    def test_non_owner_cannot_create_section(self, db):
        owner = UserFactory()
        other = UserFactory()
        survey = SurveyFactory(owner=owner)
        client = make_auth_client(other)
        resp = client.post(
            f"{BASE}/surveys/{survey.pk}/sections/",
            {"title": "Stolen Section", "order": 1},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_update_section(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner)
        section = SectionFactory(survey=survey, title="Old")
        client = make_auth_client(owner)
        resp = client.put(
            f"{BASE}/surveys/{survey.pk}/sections/{section.pk}/",
            {"title": "Updated", "order": 2},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"]["title"] == "Updated"

    def test_delete_section(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner)
        section = SectionFactory(survey=survey)
        client = make_auth_client(owner)
        resp = client.delete(f"{BASE}/surveys/{survey.pk}/sections/{section.pk}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not Section.objects.filter(pk=section.pk).exists()


# ---------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestFieldAPI:
    def test_list_fields(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner)
        section = SectionFactory(survey=survey)
        FieldFactory.create_batch(4, section=section)
        client = make_auth_client(owner)
        resp = client.get(f"{BASE}/sections/{section.pk}/fields/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()["data"]) == 4

    def test_create_field(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner)
        section = SectionFactory(survey=survey)
        client = make_auth_client(owner)
        payload = {
            "label": "Full Name",
            "field_type": "text",
            "is_required": True,
            "order": 0,
        }
        resp = client.post(f"{BASE}/sections/{section.pk}/fields/", payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()["data"]
        assert data["label"] == "Full Name"
        assert data["is_required"] is True

    def test_create_field_invalid_type_returns_400(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner)
        section = SectionFactory(survey=survey)
        client = make_auth_client(owner)
        resp = client.post(
            f"{BASE}/sections/{section.pk}/fields/",
            {"label": "Bad", "field_type": "fax_machine"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_field(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner)
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section, label="Old")
        client = make_auth_client(owner)
        resp = client.put(
            f"{BASE}/sections/{section.pk}/fields/{field.pk}/",
            {"label": "New", "field_type": "text"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"]["label"] == "New"

    def test_delete_field(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner)
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section)
        client = make_auth_client(owner)
        resp = client.delete(f"{BASE}/sections/{section.pk}/fields/{field.pk}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not Field.objects.filter(pk=field.pk).exists()

    def test_non_owner_cannot_create_field(self, db):
        owner = UserFactory()
        other = UserFactory()
        survey = SurveyFactory(owner=owner)
        section = SectionFactory(survey=survey)
        client = make_auth_client(other)
        resp = client.post(
            f"{BASE}/sections/{section.pk}/fields/",
            {"label": "Hack", "field_type": "text"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.django_db
class TestConditionAPI:
    def test_create_condition(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner)
        section = SectionFactory(survey=survey)
        source = FieldFactory(section=section)
        target = FieldFactory(section=section)
        client = make_auth_client(owner)
        payload = {
            "operator": "equals",
            "expected_value": "yes",
            "target_field": str(target.pk),
        }
        resp = client.post(
            f"{BASE}/fields/{source.pk}/conditions/", payload, format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()["data"]
        assert data["operator"] == "equals"
        assert data["expected_value"] == "yes"

    def test_create_condition_without_target_returns_400(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner)
        section = SectionFactory(survey=survey)
        source = FieldFactory(section=section)
        client = make_auth_client(owner)
        payload = {"operator": "equals", "expected_value": "yes"}
        resp = client.post(
            f"{BASE}/fields/{source.pk}/conditions/", payload, format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_condition(self, db):
        owner = UserFactory()
        survey = SurveyFactory(owner=owner)
        section = SectionFactory(survey=survey)
        source = FieldFactory(section=section)
        target = FieldFactory(section=section)
        condition = FieldConditionFactory(source_field=source, target_field=target)
        client = make_auth_client(owner)
        resp = client.delete(f"{BASE}/conditions/{condition.pk}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not FieldCondition.objects.filter(pk=condition.pk).exists()

    def test_delete_nonexistent_condition_returns_404(self, db):
        user = UserFactory()
        client = make_auth_client(user)
        resp = client.delete(f"{BASE}/conditions/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_non_owner_cannot_create_condition(self, db):
        owner = UserFactory()
        other = UserFactory()
        survey = SurveyFactory(owner=owner)
        section = SectionFactory(survey=survey)
        source = FieldFactory(section=section)
        target = FieldFactory(section=section)
        client = make_auth_client(other)
        payload = {
            "operator": "equals",
            "expected_value": "yes",
            "target_field": str(target.pk),
        }
        resp = client.post(
            f"{BASE}/fields/{source.pk}/conditions/", payload, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
