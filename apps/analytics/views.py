from django.core.cache import cache
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.views import APIView

from apps.analytics.serializers import (
    ExportRequestSerializer,
    FieldAnalyticsSerializer,
    SurveyAnalyticsSerializer,
    TaskStatusSerializer,
)
from apps.users.permissions import IsAnalyst, IsDataViewer
from apps.utils import error_response, success_response
from services import analytics_service, survey_service
from tasks.export_tasks import export_responses
from tasks.report_tasks import generate_survey_report


class SurveyAnalyticsView(APIView):
    """
    GET /api/v1/surveys/{survey_id}/analytics/

    Returns aggregated stats: completion rate, avg time, daily submissions.
    Requires analyst or data_viewer role.
    """

    permission_classes = [IsDataViewer]

    @extend_schema(
        summary="Get aggregated analytics for a survey",
        examples=[
            OpenApiExample(
                "Success (200)",
                value={
                    "success": True,
                    "message": "Survey analytics retrieved.",
                    "data": {
                        "survey_id": "s1000000-0000-0000-0000-000000000001",
                        "total_responses": 120,
                        "complete_responses": 98,
                        "partial_responses": 22,
                        "completion_rate": 81.67,
                        "avg_completion_time_seconds": 245,
                        "daily_submissions": [
                            {"date": "2026-04-19", "count": 15},
                            {"date": "2026-04-20", "count": 23},
                            {"date": "2026-04-21", "count": 18},
                        ],
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get(self, request, survey_id):
        survey = survey_service.get_survey_by_id(survey_id)
        if survey is None:
            return error_response(message="Survey not found.", status=404)

        data = analytics_service.get_survey_analytics(str(survey_id))
        serializer = SurveyAnalyticsSerializer(data)
        return success_response(data=serializer.data, message="Survey analytics retrieved.")


class FieldAnalyticsView(APIView):
    """
    GET /api/v1/surveys/{survey_id}/analytics/fields/

    Returns per-field answer distribution for all non-sensitive fields.
    Requires analyst or data_viewer role.
    """

    permission_classes = [IsDataViewer]

    @extend_schema(
        summary="Get per-field answer distribution for a survey",
        examples=[
            OpenApiExample(
                "Success (200)",
                value={
                    "success": True,
                    "message": "Field analytics retrieved.",
                    "data": [
                        {
                            "field_id": "fld10000-0000-0000-0000-000000000001",
                            "label": "Overall satisfaction",
                            "field_type": "rating",
                            "response_count": 98,
                            "answer_distribution": {
                                "1": 3,
                                "2": 8,
                                "3": 22,
                                "4": 41,
                                "5": 24,
                            },
                        },
                        {
                            "field_id": "fld10000-0000-0000-0000-000000000002",
                            "label": "How did you hear about us?",
                            "field_type": "single_choice",
                            "response_count": 95,
                            "answer_distribution": {
                                "Social media": 40,
                                "Friend referral": 35,
                                "Advertisement": 20,
                            },
                        },
                    ],
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get(self, request, survey_id):
        survey = survey_service.get_survey_by_id(survey_id)
        if survey is None:
            return error_response(message="Survey not found.", status=404)

        data = analytics_service.get_field_analytics(str(survey_id))
        serializer = FieldAnalyticsSerializer(data, many=True)
        return success_response(data=serializer.data, message="Field analytics retrieved.")


class ExportResponsesView(APIView):
    """
    POST /api/v1/surveys/{survey_id}/export/

    Enqueues an async Celery task to export all complete responses.
    Returns a task_id for status polling.
    Requires analyst role.
    """

    permission_classes = [IsAnalyst]

    @extend_schema(
        summary="Export survey responses as JSON or CSV (async)",
        request=ExportRequestSerializer,
        examples=[
            OpenApiExample(
                "Export as CSV",
                value={"format": "csv"},
                request_only=True,
            ),
            OpenApiExample(
                "Export as JSON",
                value={"format": "json"},
                request_only=True,
            ),
            OpenApiExample(
                "Accepted (202)",
                value={
                    "success": True,
                    "message": "Export task queued.",
                    "data": {"task_id": "celery-task-uuid-0000-0001"},
                    "errors": None,
                },
                response_only=True,
                status_codes=["202"],
            ),
        ],
    )
    def post(self, request, survey_id):
        survey = survey_service.get_survey_by_id(survey_id)
        if survey is None:
            return error_response(message="Survey not found.", status=404)

        serializer = ExportRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(errors=serializer.errors, message="Invalid input.", status=400)

        task = export_responses.delay(
            survey_id=str(survey_id),
            user_id=str(request.user.pk),
            format=serializer.validated_data["format"],
        )

        return success_response(
            data={"task_id": task.id},
            message="Export task queued.",
            status=202,
        )


class GenerateReportView(APIView):
    """
    POST /api/v1/surveys/{survey_id}/report/

    Enqueues an async Celery task to generate a full analytics report.
    Returns a task_id for status polling.
    Requires analyst role.
    """

    permission_classes = [IsAnalyst]

    @extend_schema(
        summary="Generate a full analytics report (async)",
        examples=[
            OpenApiExample(
                "JSON report for a specific date",
                value={"format": "json", "date": "2026-04-20"},
                request_only=True,
            ),
            OpenApiExample(
                "CSV report (no date filter)",
                value={"format": "csv"},
                request_only=True,
            ),
            OpenApiExample(
                "Accepted (202)",
                value={
                    "success": True,
                    "message": "Report generation task queued.",
                    "data": {"task_id": "celery-task-uuid-0000-0002"},
                    "errors": None,
                },
                response_only=True,
                status_codes=["202"],
            ),
        ],
    )
    def post(self, request, survey_id):
        survey = survey_service.get_survey_by_id(survey_id)
        if survey is None:
            return error_response(message="Survey not found.", status=404)

        format_ = request.data.get("format", "json")
        report_date = request.data.get("date")  # optional ISO date string

        task = generate_survey_report.delay(
            survey_id=str(survey_id),
            format=format_,
            report_date=report_date,
        )

        return success_response(
            data={"task_id": task.id},
            message="Report generation task queued.",
            status=202,
        )


class TaskStatusView(APIView):
    """
    GET /api/v1/tasks/{task_id}/status/

    Poll the status of any async Celery task (export or report).
    Status values: pending | started | success | failure
    """

    permission_classes = [IsDataViewer]

    @extend_schema(
        summary="Poll the status of an async task (export or report)",
        examples=[
            OpenApiExample(
                "Task pending",
                value={
                    "success": True,
                    "message": "Task status retrieved.",
                    "data": {
                        "task_id": "celery-task-uuid-0000-0001",
                        "status": "pending",
                        "result": None,
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Task succeeded with JSON result",
                value={
                    "success": True,
                    "message": "Task status retrieved.",
                    "data": {
                        "task_id": "celery-task-uuid-0000-0001",
                        "status": "success",
                        "result": {
                            "rows": 98,
                            "download_url": "/media/exports/survey-s1000000-export.csv",
                        },
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Task failed",
                value={
                    "success": True,
                    "message": "Task status retrieved.",
                    "data": {
                        "task_id": "celery-task-uuid-0000-0001",
                        "status": "failure",
                        "result": {"error": "Database connection timeout."},
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get(self, request, task_id):
        meta_key = f"task:{task_id}:meta"
        meta = cache.get(meta_key)

        if meta is None:
            # Not in our Redis meta store — fall back to Celery's result backend
            from celery.result import AsyncResult
            result = AsyncResult(task_id)
            state = result.state.lower()
            task_result = None
            if state == "success":
                task_result = result.result
            elif state == "failure":
                task_result = {"error": str(result.result)}

            meta = {"status": state, "result": task_result}

        serializer = TaskStatusSerializer({"task_id": task_id, **meta})
        return success_response(data=serializer.data, message="Task status retrieved.")
