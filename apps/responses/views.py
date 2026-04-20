from django.core.exceptions import ValidationError
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

    def get(self, request):
        responses = response_service.get_user_responses(request.user)
        return success_response(data=ResponseOutputSerializer(responses, many=True).data)
