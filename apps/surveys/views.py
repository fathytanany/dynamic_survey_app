from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.surveys.serializers import (
    FieldConditionSerializer,
    FieldSerializer,
    FieldWriteSerializer,
    SectionSerializer,
    SectionWriteSerializer,
    SurveyDetailSerializer,
    SurveyListSerializer,
    SurveyWriteSerializer,
)
from apps.utils import error_response, success_response
from services import survey_service


def _is_owner_or_admin(user, survey):
    return survey.owner_id == user.pk or user.role == "admin"


# ---------------------------------------------------------------------------
# Survey views
# ---------------------------------------------------------------------------

class SurveyListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        surveys = survey_service.get_survey_list()
        serializer = SurveyListSerializer(surveys, many=True)
        return success_response(data=serializer.data)

    def post(self, request):
        serializer = SurveyWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                errors=serializer.errors,
                message="Survey creation failed.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        survey = survey_service.create_survey(serializer.validated_data, request.user)
        return success_response(
            data=SurveyDetailSerializer(survey).data,
            message="Survey created successfully.",
            status=status.HTTP_201_CREATED,
        )


class SurveyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_survey_or_404(self, survey_id):
        survey = survey_service.get_survey_by_id(survey_id)
        if survey is None:
            return None, error_response(
                errors={"detail": "Survey not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )
        return survey, None

    def get(self, request, survey_id):
        survey = survey_service.get_survey_detail_cached(survey_id)
        if survey is None:
            return error_response(
                errors={"detail": "Survey not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )
        return success_response(data=SurveyDetailSerializer(survey).data)

    def put(self, request, survey_id):
        survey, err = self._get_survey_or_404(survey_id)
        if err:
            return err
        if not _is_owner_or_admin(request.user, survey):
            return error_response(
                errors={"detail": "You do not have permission to edit this survey."},
                message="Forbidden.",
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = SurveyWriteSerializer(survey, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(
                errors=serializer.errors,
                message="Survey update failed.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        updated = survey_service.update_survey(survey, serializer.validated_data)
        return success_response(
            data=SurveyDetailSerializer(updated).data,
            message="Survey updated successfully.",
        )

    def delete(self, request, survey_id):
        survey, err = self._get_survey_or_404(survey_id)
        if err:
            return err
        if not _is_owner_or_admin(request.user, survey):
            return error_response(
                errors={"detail": "You do not have permission to delete this survey."},
                message="Forbidden.",
                status=status.HTTP_403_FORBIDDEN,
            )
        survey_service.delete_survey(survey)
        return success_response(
            message="Survey deleted successfully.",
            status=status.HTTP_204_NO_CONTENT,
        )


class SurveyPublishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, survey_id):
        survey = survey_service.get_survey_by_id(survey_id)
        if survey is None:
            return error_response(
                errors={"detail": "Survey not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _is_owner_or_admin(request.user, survey):
            return error_response(
                errors={"detail": "You do not have permission to publish this survey."},
                message="Forbidden.",
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            published = survey_service.publish_survey(survey)
        except ValueError as exc:
            return error_response(
                errors={"detail": str(exc)},
                message="Publish failed.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        return success_response(
            data=SurveyDetailSerializer(published).data,
            message="Survey published successfully.",
        )


class SurveyCloneView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, survey_id):
        survey = survey_service.get_survey_by_id(survey_id)
        if survey is None:
            return error_response(
                errors={"detail": "Survey not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )
        cloned = survey_service.clone_survey(survey, request.user)
        return success_response(
            data=SurveyDetailSerializer(cloned).data,
            message="Survey cloned successfully.",
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Section views
# ---------------------------------------------------------------------------

class SectionListView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_survey_or_404(self, survey_id):
        survey = survey_service.get_survey_by_id(survey_id)
        if survey is None:
            return None, error_response(
                errors={"detail": "Survey not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )
        return survey, None

    def get(self, request, survey_id):
        survey, err = self._get_survey_or_404(survey_id)
        if err:
            return err
        sections = survey_service.get_sections(survey)
        serializer = SectionSerializer(sections, many=True)
        return success_response(data=serializer.data)

    def post(self, request, survey_id):
        survey, err = self._get_survey_or_404(survey_id)
        if err:
            return err
        if not _is_owner_or_admin(request.user, survey):
            return error_response(
                errors={"detail": "You do not have permission to add sections."},
                message="Forbidden.",
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = SectionWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                errors=serializer.errors,
                message="Section creation failed.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        section = survey_service.create_section(survey, serializer.validated_data)
        return success_response(
            data=SectionSerializer(section).data,
            message="Section created successfully.",
            status=status.HTTP_201_CREATED,
        )


class SectionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_survey_and_section_or_404(self, survey_id, section_id):
        survey = survey_service.get_survey_by_id(survey_id)
        if survey is None:
            return None, None, error_response(
                errors={"detail": "Survey not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )
        section = survey_service.get_section_by_id(survey, section_id)
        if section is None:
            return None, None, error_response(
                errors={"detail": "Section not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )
        return survey, section, None

    def put(self, request, survey_id, section_id):
        survey, section, err = self._get_survey_and_section_or_404(survey_id, section_id)
        if err:
            return err
        if not _is_owner_or_admin(request.user, survey):
            return error_response(
                errors={"detail": "You do not have permission to edit this section."},
                message="Forbidden.",
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = SectionWriteSerializer(section, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(
                errors=serializer.errors,
                message="Section update failed.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        updated = survey_service.update_section(section, serializer.validated_data)
        return success_response(
            data=SectionSerializer(updated).data,
            message="Section updated successfully.",
        )

    def delete(self, request, survey_id, section_id):
        survey, section, err = self._get_survey_and_section_or_404(survey_id, section_id)
        if err:
            return err
        if not _is_owner_or_admin(request.user, survey):
            return error_response(
                errors={"detail": "You do not have permission to delete this section."},
                message="Forbidden.",
                status=status.HTTP_403_FORBIDDEN,
            )
        survey_service.delete_section(section)
        return success_response(
            message="Section deleted successfully.",
            status=status.HTTP_204_NO_CONTENT,
        )


# ---------------------------------------------------------------------------
# Field views
# ---------------------------------------------------------------------------

class FieldListView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_section_or_404(self, section_id):
        from apps.surveys.models import Section
        try:
            return Section.objects.select_related("survey").get(pk=section_id), None
        except Section.DoesNotExist:
            return None, error_response(
                errors={"detail": "Section not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

    def get(self, request, section_id):
        section, err = self._get_section_or_404(section_id)
        if err:
            return err
        fields = survey_service.get_fields(section)
        serializer = FieldSerializer(fields, many=True)
        return success_response(data=serializer.data)

    def post(self, request, section_id):
        section, err = self._get_section_or_404(section_id)
        if err:
            return err
        if not _is_owner_or_admin(request.user, section.survey):
            return error_response(
                errors={"detail": "You do not have permission to add fields."},
                message="Forbidden.",
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = FieldWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                errors=serializer.errors,
                message="Field creation failed.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        field = survey_service.create_field(section, serializer.validated_data)
        return success_response(
            data=FieldSerializer(field).data,
            message="Field created successfully.",
            status=status.HTTP_201_CREATED,
        )


class FieldDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_section_and_field_or_404(self, section_id, field_id):
        from apps.surveys.models import Section
        try:
            section = Section.objects.select_related("survey").get(pk=section_id)
        except Section.DoesNotExist:
            return None, None, error_response(
                errors={"detail": "Section not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )
        field = survey_service.get_field_by_id(section, field_id)
        if field is None:
            return None, None, error_response(
                errors={"detail": "Field not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )
        return section, field, None

    def put(self, request, section_id, field_id):
        section, field, err = self._get_section_and_field_or_404(section_id, field_id)
        if err:
            return err
        if not _is_owner_or_admin(request.user, section.survey):
            return error_response(
                errors={"detail": "You do not have permission to edit this field."},
                message="Forbidden.",
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = FieldWriteSerializer(field, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(
                errors=serializer.errors,
                message="Field update failed.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        updated = survey_service.update_field(field, serializer.validated_data)
        return success_response(
            data=FieldSerializer(updated).data,
            message="Field updated successfully.",
        )

    def delete(self, request, section_id, field_id):
        section, field, err = self._get_section_and_field_or_404(section_id, field_id)
        if err:
            return err
        if not _is_owner_or_admin(request.user, section.survey):
            return error_response(
                errors={"detail": "You do not have permission to delete this field."},
                message="Forbidden.",
                status=status.HTTP_403_FORBIDDEN,
            )
        survey_service.delete_field(field)
        return success_response(
            message="Field deleted successfully.",
            status=status.HTTP_204_NO_CONTENT,
        )


# ---------------------------------------------------------------------------
# Condition views
# ---------------------------------------------------------------------------

class ConditionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, field_id):
        from apps.surveys.models import Field
        try:
            field = Field.objects.select_related("section__survey").get(pk=field_id)
        except Field.DoesNotExist:
            return error_response(
                errors={"detail": "Field not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _is_owner_or_admin(request.user, field.section.survey):
            return error_response(
                errors={"detail": "You do not have permission to add conditions."},
                message="Forbidden.",
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = FieldConditionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                errors=serializer.errors,
                message="Condition creation failed.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        # source_field comes from the URL, not the request body
        data = {k: v for k, v in serializer.validated_data.items() if k != "source_field"}
        condition = survey_service.create_condition(field, data)
        return success_response(
            data=FieldConditionSerializer(condition).data,
            message="Condition created successfully.",
            status=status.HTTP_201_CREATED,
        )


class ConditionDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, condition_id):
        condition = survey_service.get_condition_by_id(condition_id)
        if condition is None:
            return error_response(
                errors={"detail": "Condition not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _is_owner_or_admin(request.user, condition.source_field.section.survey):
            return error_response(
                errors={"detail": "You do not have permission to delete this condition."},
                message="Forbidden.",
                status=status.HTTP_403_FORBIDDEN,
            )
        survey_service.delete_condition(condition)
        return success_response(
            message="Condition deleted successfully.",
            status=status.HTTP_204_NO_CONTENT,
        )
