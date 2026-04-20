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
