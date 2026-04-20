"""
Unit tests for the conditional logic in services/response_service.py:
  - _evaluate_condition
  - get_active_field_ids
"""
import pytest

from apps.surveys.models import FieldCondition
from services.response_service import _evaluate_condition, get_active_field_ids
from tests.factories import (
    FieldConditionFactory,
    FieldFactory,
    SectionFactory,
    SurveyFactory,
)


# ---------------------------------------------------------------------------
# _evaluate_condition
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEvaluateCondition:
    """Tests _evaluate_condition in isolation using mock-like FieldCondition objects."""

    def _make_condition(self, source_field_id, operator, expected_value):
        cond = FieldCondition()
        cond.source_field_id = source_field_id
        cond.operator = operator
        cond.expected_value = expected_value
        return cond

    # --- EQUALS ---

    def test_equals_true(self):
        cond = self._make_condition("f1", FieldCondition.Operator.EQUALS, "yes")
        assert _evaluate_condition(cond, {"f1": "yes"}) is True

    def test_equals_false(self):
        cond = self._make_condition("f1", FieldCondition.Operator.EQUALS, "yes")
        assert _evaluate_condition(cond, {"f1": "no"}) is False

    def test_equals_case_sensitive(self):
        cond = self._make_condition("f1", FieldCondition.Operator.EQUALS, "Yes")
        assert _evaluate_condition(cond, {"f1": "yes"}) is False

    # --- NOT_EQUALS ---

    def test_not_equals_true(self):
        cond = self._make_condition("f1", FieldCondition.Operator.NOT_EQUALS, "yes")
        assert _evaluate_condition(cond, {"f1": "no"}) is True

    def test_not_equals_false(self):
        cond = self._make_condition("f1", FieldCondition.Operator.NOT_EQUALS, "yes")
        assert _evaluate_condition(cond, {"f1": "yes"}) is False

    # --- CONTAINS ---

    def test_contains_true(self):
        cond = self._make_condition("f1", FieldCondition.Operator.CONTAINS, "foo")
        assert _evaluate_condition(cond, {"f1": "foobar"}) is True

    def test_contains_false(self):
        cond = self._make_condition("f1", FieldCondition.Operator.CONTAINS, "baz")
        assert _evaluate_condition(cond, {"f1": "foobar"}) is False

    def test_contains_exact_match(self):
        cond = self._make_condition("f1", FieldCondition.Operator.CONTAINS, "foobar")
        assert _evaluate_condition(cond, {"f1": "foobar"}) is True

    # --- GREATER_THAN ---

    def test_greater_than_true(self):
        cond = self._make_condition("f1", FieldCondition.Operator.GREATER_THAN, "18")
        assert _evaluate_condition(cond, {"f1": "25"}) is True

    def test_greater_than_false(self):
        cond = self._make_condition("f1", FieldCondition.Operator.GREATER_THAN, "18")
        assert _evaluate_condition(cond, {"f1": "10"}) is False

    def test_greater_than_equal_is_false(self):
        cond = self._make_condition("f1", FieldCondition.Operator.GREATER_THAN, "18")
        assert _evaluate_condition(cond, {"f1": "18"}) is False

    def test_greater_than_non_numeric_returns_false(self):
        cond = self._make_condition("f1", FieldCondition.Operator.GREATER_THAN, "18")
        assert _evaluate_condition(cond, {"f1": "twenty"}) is False

    # --- LESS_THAN ---

    def test_less_than_true(self):
        cond = self._make_condition("f1", FieldCondition.Operator.LESS_THAN, "100")
        assert _evaluate_condition(cond, {"f1": "50"}) is True

    def test_less_than_false(self):
        cond = self._make_condition("f1", FieldCondition.Operator.LESS_THAN, "100")
        assert _evaluate_condition(cond, {"f1": "200"}) is False

    def test_less_than_non_numeric_returns_false(self):
        cond = self._make_condition("f1", FieldCondition.Operator.LESS_THAN, "100")
        assert _evaluate_condition(cond, {"f1": "big"}) is False

    # --- Missing source field ---

    def test_missing_source_value_returns_false(self):
        cond = self._make_condition("missing_id", FieldCondition.Operator.EQUALS, "yes")
        assert _evaluate_condition(cond, {}) is False

    def test_none_source_value_returns_false(self):
        cond = self._make_condition("f1", FieldCondition.Operator.EQUALS, "yes")
        assert _evaluate_condition(cond, {"f1": None}) is False


# ---------------------------------------------------------------------------
# get_active_field_ids
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.django_db
class TestGetActiveFieldIds:
    def test_field_without_conditions_always_active(self, db):
        survey = SurveyFactory()
        section = SectionFactory(survey=survey)
        field = FieldFactory(section=section)
        active = get_active_field_ids(survey, {})
        assert str(field.pk) in active

    def test_gated_field_hidden_by_default(self, db):
        survey = SurveyFactory()
        section = SectionFactory(survey=survey)
        source = FieldFactory(section=section)
        target = FieldFactory(section=section)
        FieldConditionFactory(
            source_field=source,
            operator=FieldCondition.Operator.EQUALS,
            expected_value="yes",
            target_field=target,
            target_section=None,
        )
        # No answer provided — target should be hidden
        active = get_active_field_ids(survey, {})
        assert str(target.pk) not in active

    def test_gated_field_visible_when_condition_met(self, db):
        survey = SurveyFactory()
        section = SectionFactory(survey=survey)
        source = FieldFactory(section=section)
        target = FieldFactory(section=section)
        FieldConditionFactory(
            source_field=source,
            operator=FieldCondition.Operator.EQUALS,
            expected_value="yes",
            target_field=target,
            target_section=None,
        )
        answers = {str(source.pk): "yes"}
        active = get_active_field_ids(survey, answers)
        assert str(target.pk) in active

    def test_gated_field_hidden_when_condition_not_met(self, db):
        survey = SurveyFactory()
        section = SectionFactory(survey=survey)
        source = FieldFactory(section=section)
        target = FieldFactory(section=section)
        FieldConditionFactory(
            source_field=source,
            operator=FieldCondition.Operator.EQUALS,
            expected_value="yes",
            target_field=target,
            target_section=None,
        )
        answers = {str(source.pk): "no"}
        active = get_active_field_ids(survey, answers)
        assert str(target.pk) not in active

    def test_source_field_always_active(self, db):
        survey = SurveyFactory()
        section = SectionFactory(survey=survey)
        source = FieldFactory(section=section)
        target = FieldFactory(section=section)
        FieldConditionFactory(
            source_field=source,
            operator=FieldCondition.Operator.EQUALS,
            expected_value="yes",
            target_field=target,
            target_section=None,
        )
        active = get_active_field_ids(survey, {})
        assert str(source.pk) in active

    def test_section_gating_hides_all_fields_in_section(self, db):
        survey = SurveyFactory()
        controlling_section = SectionFactory(survey=survey)
        gated_section = SectionFactory(survey=survey)
        source = FieldFactory(section=controlling_section)
        gated_field = FieldFactory(section=gated_section)
        FieldConditionFactory(
            source_field=source,
            operator=FieldCondition.Operator.EQUALS,
            expected_value="show",
            target_field=None,
            target_section=gated_section,
        )
        # No matching answer — gated section hidden
        active = get_active_field_ids(survey, {})
        assert str(gated_field.pk) not in active

    def test_section_gating_shows_when_condition_met(self, db):
        survey = SurveyFactory()
        controlling_section = SectionFactory(survey=survey)
        gated_section = SectionFactory(survey=survey)
        source = FieldFactory(section=controlling_section)
        gated_field = FieldFactory(section=gated_section)
        FieldConditionFactory(
            source_field=source,
            operator=FieldCondition.Operator.EQUALS,
            expected_value="show",
            target_field=None,
            target_section=gated_section,
        )
        answers = {str(source.pk): "show"}
        active = get_active_field_ids(survey, answers)
        assert str(gated_field.pk) in active

    def test_multiple_conditions_independent(self, db):
        survey = SurveyFactory()
        section = SectionFactory(survey=survey)
        source = FieldFactory(section=section)
        target1 = FieldFactory(section=section)
        target2 = FieldFactory(section=section)
        FieldConditionFactory(
            source_field=source,
            operator=FieldCondition.Operator.EQUALS,
            expected_value="a",
            target_field=target1,
            target_section=None,
        )
        FieldConditionFactory(
            source_field=source,
            operator=FieldCondition.Operator.EQUALS,
            expected_value="b",
            target_field=target2,
            target_section=None,
        )
        # Matches first condition only
        answers = {str(source.pk): "a"}
        active = get_active_field_ids(survey, answers)
        assert str(target1.pk) in active
        assert str(target2.pk) not in active

    def test_empty_survey_returns_empty_set(self, db):
        survey = SurveyFactory()
        active = get_active_field_ids(survey, {})
        assert active == set()

    def test_greater_than_condition(self, db):
        survey = SurveyFactory()
        section = SectionFactory(survey=survey)
        source = FieldFactory(section=section)
        target = FieldFactory(section=section)
        FieldConditionFactory(
            source_field=source,
            operator=FieldCondition.Operator.GREATER_THAN,
            expected_value="18",
            target_field=target,
            target_section=None,
        )
        assert str(target.pk) in get_active_field_ids(survey, {str(source.pk): "25"})
        assert str(target.pk) not in get_active_field_ids(survey, {str(source.pk): "10"})

    def test_contains_condition(self, db):
        survey = SurveyFactory()
        section = SectionFactory(survey=survey)
        source = FieldFactory(section=section)
        target = FieldFactory(section=section)
        FieldConditionFactory(
            source_field=source,
            operator=FieldCondition.Operator.CONTAINS,
            expected_value="urgent",
            target_field=target,
            target_section=None,
        )
        assert str(target.pk) in get_active_field_ids(
            survey, {str(source.pk): "this is urgent help"}
        )
        assert str(target.pk) not in get_active_field_ids(
            survey, {str(source.pk): "all is fine"}
        )
