from django.urls import path

from apps.analytics.views import (
    ExportResponsesView,
    FieldAnalyticsView,
    GenerateReportView,
    SurveyAnalyticsView,
    TaskStatusView,
)

urlpatterns = [
    # Survey-level analytics
    path("surveys/<uuid:survey_id>/analytics/", SurveyAnalyticsView.as_view(), name="survey-analytics"),
    path("surveys/<uuid:survey_id>/analytics/fields/", FieldAnalyticsView.as_view(), name="field-analytics"),

    # Async task triggers
    path("surveys/<uuid:survey_id>/export/", ExportResponsesView.as_view(), name="export-responses"),
    path("surveys/<uuid:survey_id>/report/", GenerateReportView.as_view(), name="generate-report"),

    # Task status polling
    path("tasks/<str:task_id>/status/", TaskStatusView.as_view(), name="task-status"),
]
