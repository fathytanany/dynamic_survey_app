from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """Full access — admin role only."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )


class IsAnalyst(BasePermission):
    """Read surveys + analytics, trigger exports — analyst or admin."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ("admin", "analyst")
        )


class IsDataViewer(BasePermission):
    """Read analytics only — any authenticated role."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ("admin", "analyst", "data_viewer")
        )
