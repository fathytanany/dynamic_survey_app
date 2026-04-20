from django.urls import path

from apps.surveys.views import (
    ConditionCreateView,
    ConditionDeleteView,
    FieldDetailView,
    FieldListView,
    SectionDetailView,
    SectionListView,
    SurveyCloneView,
    SurveyDetailView,
    SurveyListView,
    SurveyPublishView,
)

urlpatterns = [
    # Surveys
    path("surveys/", SurveyListView.as_view(), name="survey-list"),
    path("surveys/<uuid:survey_id>/", SurveyDetailView.as_view(), name="survey-detail"),
    path("surveys/<uuid:survey_id>/publish/", SurveyPublishView.as_view(), name="survey-publish"),
    path("surveys/<uuid:survey_id>/clone/", SurveyCloneView.as_view(), name="survey-clone"),

    # Sections
    path("surveys/<uuid:survey_id>/sections/", SectionListView.as_view(), name="section-list"),
    path(
        "surveys/<uuid:survey_id>/sections/<uuid:section_id>/",
        SectionDetailView.as_view(),
        name="section-detail",
    ),

    # Fields
    path("sections/<uuid:section_id>/fields/", FieldListView.as_view(), name="field-list"),
    path(
        "sections/<uuid:section_id>/fields/<uuid:field_id>/",
        FieldDetailView.as_view(),
        name="field-detail",
    ),

    # Conditions
    path("fields/<uuid:field_id>/conditions/", ConditionCreateView.as_view(), name="condition-create"),
    path("conditions/<uuid:condition_id>/", ConditionDeleteView.as_view(), name="condition-delete"),
]
