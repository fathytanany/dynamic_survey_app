from rest_framework.response import Response


def success_response(data=None, message="", status=200):
    return Response(
        {"success": True, "data": data, "message": message, "errors": None},
        status=status,
    )


def error_response(errors=None, message="", status=400):
    return Response(
        {"success": False, "data": None, "message": message, "errors": errors},
        status=status,
    )
