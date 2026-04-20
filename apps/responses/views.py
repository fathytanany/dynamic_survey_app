from django.core.exceptions import ValidationError
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.responses.models import Response
from apps.responses.serializers import ResponseOutputSerializer, ResponseSubmitSerializer
from apps.surveys.models import Survey
from apps.utils import error_response, success_response
from services import response_service, survey_service


class SubmitResponseView(APIView):
    """
    POST /api/v1/surveys/{survey_id}/respond/

    Accepts answers for a published survey.  Set status=partial to save
    progress and receive a session_token for later resumption.  Pass that
    token back as session_token to continue an existing partial session.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Submit or save a partial response to a survey",
        request=ResponseSubmitSerializer,
        examples=[
            OpenApiExample(
                "Complete submission",
                value={
                    "answers": [
                        {"field_id": "fld10000-0000-0000-0000-000000000001", "value": "4"},
                        {"field_id": "fld10000-0000-0000-0000-000000000002", "value": "Great product!"},
                    ],
                    "status": "complete",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Partial save (resume later)",
                value={
                    "answers": [
                        {"field_id": "fld10000-0000-0000-0000-000000000001", "value": "5"},
                    ],
                    "status": "partial",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Resume existing partial session",
                value={
                    "session_token": "abc123-session-token",
                    "answers": [
                        {"field_id": "fld10000-0000-0000-0000-000000000001", "value": "5"},
                        {"field_id": "fld10000-0000-0000-0000-000000000002", "value": "Love it!"},
                    ],
                    "status": "complete",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success (201)",
                value={
                    "success": True,
                    "message": "Response saved.",
                    "data": {
                        "id": "res10000-0000-0000-0000-000000000001",
                        "survey": "s1000000-0000-0000-0000-000000000001",
                        "status": "complete",
                        "session_token": None,
                        "submitted_at": "2026-04-21T14:00:00Z",
                        "answers": [
                            {"field_id": "fld10000-0000-0000-0000-000000000001", "value": "4"},
                            {"field_id": "fld10000-0000-0000-0000-000000000002", "value": "Great product!"},
                        ],
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Partial saved (201)",
                value={
                    "success": True,
                    "message": "Response saved.",
                    "data": {
                        "id": "res10000-0000-0000-0000-000000000002",
                        "survey": "s1000000-0000-0000-0000-000000000001",
                        "status": "partial",
                        "session_token": "abc123-session-token",
                        "submitted_at": None,
                        "answers": [
                            {"field_id": "fld10000-0000-0000-0000-000000000001", "value": "5"},
                        ],
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    )
    def post(self, request, survey_id):
        survey = survey_service.get_survey_by_id(survey_id)
        if survey is None:
            return error_response(message="Survey not found.", status=404)

        if survey.status != Survey.Status.PUBLISHED:
            return error_response(message="Survey is not accepting responses.", status=400)

        if survey.requires_auth and not request.user.is_authenticated:
            return error_response(message="Authentication required for this survey.", status=401)

        serializer = ResponseSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(errors=serializer.errors, message="Invalid input.", status=400)

        try:
            response = response_service.save_response(
                survey=survey,
                data=serializer.validated_data,
                request=request,
            )
        except ValidationError as exc:
            errors = exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages}
            return error_response(errors=errors, message="Validation failed.", status=422)

        return success_response(
            data=ResponseOutputSerializer(response).data,
            message="Response saved.",
            status=201,
        )


class ResumeResponseView(APIView):
    """
    GET /api/v1/responses/{session_token}/resume/

    Returns a partial Response with its saved answers so the respondent can
    continue filling out the survey.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Resume a partial survey response by session token",
        examples=[
            OpenApiExample(
                "Success (200)",
                value={
                    "success": True,
                    "message": "",
                    "data": {
                        "id": "res10000-0000-0000-0000-000000000002",
                        "survey": "s1000000-0000-0000-0000-000000000001",
                        "status": "partial",
                        "session_token": "abc123-session-token",
                        "submitted_at": None,
                        "answers": [
                            {"field_id": "fld10000-0000-0000-0000-000000000001", "value": "5"},
                        ],
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Session already complete (400)",
                value={
                    "success": False,
                    "message": "This session is already complete.",
                    "data": None,
                    "errors": None,
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def get(self, request, session_token):
        response = response_service.get_response_by_session(session_token)
        if response is None:
            return error_response(message="Session not found.", status=404)

        if response.status != Response.Status.PARTIAL:
            return error_response(message="This session is already complete.", status=400)

        return success_response(data=ResponseOutputSerializer(response).data)


class MyResponsesView(APIView):
    """
    GET /api/v1/responses/mine/

    Returns all responses submitted by the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List all responses submitted by the current user",
        examples=[
            OpenApiExample(
                "Success (200)",
                value={
                    "success": True,
                    "message": "",
                    "data": [
                        {
                            "id": "res10000-0000-0000-0000-000000000001",
                            "survey": "s1000000-0000-0000-0000-000000000001",
                            "status": "complete",
                            "session_token": None,
                            "submitted_at": "2026-04-21T14:00:00Z",
                            "answers": [
                                {"field_id": "fld10000-0000-0000-0000-000000000001", "value": "4"},
                            ],
                        }
                    ],
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get(self, request):
        responses = response_service.get_user_responses(request.user)
        return success_response(data=ResponseOutputSerializer(responses, many=True).data)
