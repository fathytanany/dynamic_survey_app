import threading

_thread_locals = threading.local()


def get_current_user():
    return getattr(_thread_locals, "user", None)


def get_current_ip():
    return getattr(_thread_locals, "ip_address", None)


def get_current_user_agent():
    return getattr(_thread_locals, "user_agent", "")


class AuditMiddleware:
    """Captures the current request's user, IP, and user-agent into thread-local
    storage so Django signals can access them without the request object."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = request.user if request.user.is_authenticated else None
        _thread_locals.ip_address = self._get_client_ip(request)
        _thread_locals.user_agent = request.META.get("HTTP_USER_AGENT", "")
        response = self.get_response(request)
        return response

    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
