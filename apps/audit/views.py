from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.users.permissions import IsAdminUser
from apps.utils import error_response, success_response


class AuditLogListView(APIView):
    """
    GET /api/v1/audit/logs/

    Returns a paginated list of audit log entries.
    Admin only. Supports query param filters:
      - user      : user UUID
      - model     : model name (e.g. Survey, Response)
      - action    : action type (create, update, delete, …)
      - date_from : ISO 8601 datetime (inclusive)
      - date_to   : ISO 8601 datetime (inclusive)
      - page      : 1-based page number (default 1)
      - page_size : results per page (default 50, max 200)
    """

    permission_classes = [IsAdminUser]

    _MAX_PAGE_SIZE = 200
    _DEFAULT_PAGE_SIZE = 50

    @extend_schema(
        summary="List audit log entries (admin only)",
        parameters=[
            OpenApiParameter(name="user", description="Filter by user UUID", required=False, type=str),
            OpenApiParameter(name="model", description="Filter by model name (e.g. Survey, Response)", required=False, type=str),
            OpenApiParameter(name="action", description="Filter by action type (create, update, delete)", required=False, type=str),
            OpenApiParameter(name="date_from", description="Filter entries on or after this ISO 8601 datetime", required=False, type=str),
            OpenApiParameter(name="date_to", description="Filter entries on or before this ISO 8601 datetime", required=False, type=str),
            OpenApiParameter(name="page", description="1-based page number (default 1)", required=False, type=int),
            OpenApiParameter(name="page_size", description="Results per page (default 50, max 200)", required=False, type=int),
        ],
        examples=[
            OpenApiExample(
                "Success (200) — survey create events",
                value={
                    "success": True,
                    "message": "Audit logs retrieved.",
                    "data": {
                        "count": 2,
                        "page": 1,
                        "page_size": 50,
                        "results": [
                            {
                                "id": "log10000-0000-0000-0000-000000000001",
                                "user": "jane.doe@example.com",
                                "action": "create",
                                "model_name": "Survey",
                                "object_id": "s1000000-0000-0000-0000-000000000001",
                                "changes": {"title": [None, "Customer Satisfaction Q1"]},
                                "ip_address": "203.0.113.42",
                                "user_agent": "Mozilla/5.0",
                                "timestamp": "2026-04-21T10:05:00Z",
                            },
                            {
                                "id": "log10000-0000-0000-0000-000000000002",
                                "user": "admin@example.com",
                                "action": "create",
                                "model_name": "Survey",
                                "object_id": "s1000000-0000-0000-0000-000000000002",
                                "changes": {"title": [None, "Employee Engagement"]},
                                "ip_address": "198.51.100.5",
                                "user_agent": "curl/8.0.1",
                                "timestamp": "2026-04-21T11:00:00Z",
                            },
                        ],
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Success (200) — delete events with pagination",
                value={
                    "success": True,
                    "message": "Audit logs retrieved.",
                    "data": {
                        "count": 1,
                        "page": 1,
                        "page_size": 50,
                        "results": [
                            {
                                "id": "log10000-0000-0000-0000-000000000003",
                                "user": "jane.doe@example.com",
                                "action": "delete",
                                "model_name": "Response",
                                "object_id": "res10000-0000-0000-0000-000000000005",
                                "changes": {},
                                "ip_address": "203.0.113.42",
                                "user_agent": "Mozilla/5.0",
                                "timestamp": "2026-04-20T16:30:00Z",
                            }
                        ],
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Invalid pagination (400)",
                value={
                    "success": False,
                    "message": "Invalid pagination parameters.",
                    "data": None,
                    "errors": {"detail": "page and page_size must be integers."},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def get(self, request):
        qs = AuditLog.objects.select_related("user")

        user_id = request.query_params.get("user")
        model_name = request.query_params.get("model")
        action = request.query_params.get("action")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if user_id:
            qs = qs.filter(user_id=user_id)
        if model_name:
            qs = qs.filter(model_name__iexact=model_name)
        if action:
            qs = qs.filter(action=action)
        if date_from:
            qs = qs.filter(timestamp__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__lte=date_to)

        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(
                self._MAX_PAGE_SIZE,
                max(1, int(request.query_params.get("page_size", self._DEFAULT_PAGE_SIZE))),
            )
        except ValueError:
            return error_response(
                errors={"detail": "page and page_size must be integers."},
                message="Invalid pagination parameters.",
                status=400,
            )

        total = qs.count()
        offset = (page - 1) * page_size
        logs = qs[offset : offset + page_size]

        serializer = AuditLogSerializer(logs, many=True)
        return success_response(
            data={
                "count": total,
                "page": page,
                "page_size": page_size,
                "results": serializer.data,
            },
            message="Audit logs retrieved.",
        )
