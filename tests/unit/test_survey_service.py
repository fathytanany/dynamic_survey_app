"""
Unit tests for services/survey_service.py.
"""
import pytest
from unittest.mock import patch

from apps.surveys.models import Field, FieldCondition, FieldOption, Section, Survey
from services import survey_service
from tests.factories import (
    FieldConditionFactory,
    FieldFactory,
    FieldOptionFactory,
    SectionFactory,
    SurveyFactory,
    UserFactory,
)


@pytest.mark.unit
@pytest.mark.django_db
class TestCreateSurvey:
    def test_creates_with_owner_and_defaults(self, db):
        user = UserFactory()
        survey = survey_service.create_survey(
            {"title": "My Survey", "description": "desc"}, user
        )
        assert survey.pk is not None
        assert survey.title == "My Survey"
        assert survey.owner == user
        assert survey.status == Survey.Status.DRAFT
        assert survey.version == 1

    def test_extra_fields_forwarded(self, db):
        user = UserFactory()
        survey = survey_service.create_survey(
            {"title": "Anon", "is_anonymous": True, "requires_auth": False}, user
        )
        assert survey.is_anonymous is True
        assert survey.requires_auth is False


@pytest.mark.unit
@pytest.mark.django_db
class TestGetSurveys:
    def test_get_survey_list_returns_all(self, db):
        SurveyFactory.create_batch(3)
        result = list(survey_service.get_survey_list())
        assert len(result) >= 3

    def test_get_survey_list_filters_by_owner(self, db):
        owner = UserFactory()
        SurveyFactory.create_batch(2, owner=owner)
        SurveyFactory.create_batch(2)  # different owner
        result = list(survey_service.get_survey_list(user=owner))
        assert len(result) == 2
        assert all(s.owner_id == owner.pk for s in result)

    def test_get_survey_by_id_found(self, db):
        survey = SurveyFactory()
        result = survey_service.get_survey_by_id(str(survey.pk))
        assert result is not None
        assert result.pk == survey.pk

    def test_get_survey_by_id_not_found(self, db):
        import uuid
        result = survey_service.get_survey_by_id(str(uuid.uuid4()))
        assert result is None


@pytest.mark.unit
@pytest.mark.django_db
class TestSurveyDetailCached:
    def test_returns_survey_and_caches_pk(self, db):
        survey = SurveyFactory()
        with patch("services.survey_service.cache") as mock_cache:
            mock_cache.get.return_value = None
            result = survey_service.get_survey_detail_cached(str(survey.pk))
        assert result is not None
        assert result.pk == survey.pk

    def test_returns_from_cache_on_second_call(self, db):
        survey = SurveyFactory()
        with patch("services.survey_service.cache") as mock_cache:
            mock_cache.get.return_value = str(survey.pk)
            result = survey_service.get_survey_detail_cached(str(survey.pk))
        assert result is not None
        assert result.pk == survey.pk

    def test_returns_none_for_missing_survey(self, db):
        import uuid
        result = survey_service.get_survey_detail_cached(str(uuid.uuid4()))
        assert result is None


@pytest.mark.unit
@pytest.mark.django_db
class TestUpdateSurvey:
    def test_updates_fields(self, db):
        survey = SurveyFactory(title="Old Title")
        updated = survey_service.update_survey(survey, {"title": "New Title"})
        assert updated.title == "New Title"
        survey.refresh_from_db()
        assert survey.title == "New Title"

    def test_invalidates_cache(self, db):
        survey = SurveyFactory()
        with patch("services.survey_service.invalidate_survey_cache") as mock_inv:
            survey_service.update_survey(survey, {"title": "X"})
        mock_inv.assert_called_once_with(survey.pk)


@pytest.mark.unit
@pytest.mark.django_db
class TestDeleteSurvey:
    def test_deletes_from_db(self, db):
        survey = SurveyFactory()
        pk = survey.pk
        survey_service.delete_survey(survey)
        assert not Survey.objects.filter(pk=pk).exists()

    def test_invalidates_cache(self, db):
        survey = SurveyFactory()
        pk = survey.pk
        with patch("services.survey_service.invalidate_survey_cache") as mock_inv:
            survey_service.delete_survey(survey)
        mock_inv.assert_called_once_with(pk)


@pytest.mark.unit
@pytest.mark.django_db
class TestPublishSurvey:
    def test_draft_becomes_published(self, db):
        survey = SurveyFactory(status=Survey.Status.DRAFT)
        result = survey_service.publish_survey(survey)
        assert result.status == Survey.Status.PUBLISHED

    def test_already_published_raises(self, db):
        survey = SurveyFactory(status=Survey.Status.PUBLISHED)
        with pytest.raises(ValueError, match="draft"):
            survey_service.publish_survey(survey)

    def test_archived_raises(self, db):
        survey = SurveyFactory(status=Survey.Status.ARCHIVED)
        with pytest.raises(ValueError):
            survey_service.publish_survey(survey)


@pytest.mark.unit
@pytest.mark.django_db
class TestCloneSurvey:
    def test_clone_creates_new_draft(self, db):
        owner = UserFactory()
        original = SurveyFactory(owner=owner, status=Survey.Status.PUBLISHED)
        clone = survey_service.clone_survey(original, owner)
        assert clone.pk != original.pk
        assert clone.status == Survey.Status.DRAFT
        assert clone.title.startswith("Copy of")
        assert clone.owner == owner

    def test_clone_copies_sections_and_fields(self, db):
        owner = UserFactory()
        original = SurveyFactory(owner=owner)
        section = SectionFactory(survey=original)
        FieldFactory.create_batch(3, section=section)

        clone = survey_service.clone_survey(original, owner)
        assert clone.sections.count() == 1
        assert clone.sections.first().fields.count() == 3

    def test_clone_copies_field_options(self, db):
        owner = UserFactory()
        original = SurveyFactory(owner=owner)
        section = SectionFactory(survey=original)
        field = FieldFactory(section=section, field_type=Field.FieldType.DROPDOWN)
        FieldOptionFactory.create_batch(2, field=field)

        clone = survey_service.clone_survey(original, owner)
        cloned_field = clone.sections.first().fields.first()
        assert cloned_field.options.count() == 2


@pytest.mark.unit
@pytest.mark.django_db
class TestSectionCRUD:
    def test_create_section(self, db):
        survey = SurveyFactory()
        section = survey_service.create_section(survey, {"title": "Section A", "order": 1})
        assert section.survey == survey
        assert section.title == "Section A"

    def test_get_sections(self, db):
        survey = SurveyFactory()
        SectionFactory.create_batch(3, survey=survey)
        sections = list(survey_service.get_sections(survey))
        assert len(sections) == 3

    def test_get_section_by_id(self, db):
        survey = SurveyFactory()
        section = SectionFactory(survey=survey)
        result = survey_service.get_section_by_id(survey, str(section.pk))
        assert result == section

    def test_get_section_by_id_wrong_survey(self, db):
        survey = SurveyFactory()
        other_section = SectionFactory()  # belongs to different survey
        result = survey_service.get_section_by_id(survey, str(other_section.pk))
        assert result is None

    def test_update_section(self, db):
        section = SectionFactory(title="Old")
        updated = survey_service.update_section(section, {"title": "New"})
        assert updated.title == "New"

    def test_delete_section(self, db):
        section = SectionFactory()
        pk = section.pk
        survey_service.delete_section(section)
        assert not Section.objects.filter(pk=pk).exists()


@pytest.mark.unit
@pytest.mark.django_db
class TestFieldCRUD:
    def test_create_field(self, db):
        section = SectionFactory()
        field = survey_service.create_field(
            section, {"label": "Age", "field_type": "number", "order": 0}
        )
        assert field.section == section
        assert field.label == "Age"

    def test_get_fields(self, db):
        section = SectionFactory()
        FieldFactory.create_batch(4, section=section)
        fields = list(survey_service.get_fields(section))
        assert len(fields) == 4

    def test_update_field(self, db):
        field = FieldFactory(label="Old")
        updated = survey_service.update_field(field, {"label": "New", "is_required": True})
        assert updated.label == "New"
        assert updated.is_required is True

    def test_delete_field(self, db):
        field = FieldFactory()
        pk = field.pk
        survey_service.delete_field(field)
        assert not Field.objects.filter(pk=pk).exists()


@pytest.mark.unit
@pytest.mark.django_db
class TestConditionCRUD:
    def test_create_condition(self, db):
        source = FieldFactory()
        target = FieldFactory(section=source.section)
        condition = survey_service.create_condition(
            source,
            {
                "operator": FieldCondition.Operator.EQUALS,
                "expected_value": "yes",
                "target_field": target,
                "target_section": None,
            },
        )
        assert condition.source_field == source
        assert condition.operator == FieldCondition.Operator.EQUALS

    def test_get_condition_by_id(self, db):
        cond = FieldConditionFactory()
        result = survey_service.get_condition_by_id(str(cond.pk))
        assert result == cond

    def test_get_condition_by_id_missing(self, db):
        import uuid
        result = survey_service.get_condition_by_id(str(uuid.uuid4()))
        assert result is None

    def test_delete_condition(self, db):
        cond = FieldConditionFactory()
        pk = cond.pk
        survey_service.delete_condition(cond)
        assert not FieldCondition.objects.filter(pk=pk).exists()


@pytest.mark.unit
@pytest.mark.django_db
class TestInvalidateSurveyCache:
    def test_deletes_cache_key(self, db):
        survey = SurveyFactory()
        with patch("services.survey_service.cache") as mock_cache:
            survey_service.invalidate_survey_cache(survey.pk)
        mock_cache.delete.assert_called_once_with(f"survey:{survey.pk}:detail")
