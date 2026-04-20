from rest_framework import serializers

from apps.responses.models import Response, ResponseAnswer
from services import encryption_service


class AnswerInputSerializer(serializers.Serializer):
    field_id = serializers.UUIDField()
    value = serializers.CharField(allow_blank=True, allow_null=True, default="")


class ResponseSubmitSerializer(serializers.Serializer):
    answers = AnswerInputSerializer(many=True)
    status = serializers.ChoiceField(
        choices=[Response.Status.PARTIAL, Response.Status.COMPLETE],
        default=Response.Status.COMPLETE,
    )
    session_token = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class ResponseAnswerOutputSerializer(serializers.ModelSerializer):
    field_id = serializers.UUIDField(source="field_id", read_only=True)
    value = serializers.SerializerMethodField()

    class Meta:
        model = ResponseAnswer
        fields = ["id", "field_id", "value", "created_at"]

    def get_value(self, obj):
        if obj.value_encrypted:
            try:
                return encryption_service.decrypt(bytes(obj.value_encrypted))
            except Exception:
                return None
        return obj.value_text


class ResponseOutputSerializer(serializers.ModelSerializer):
    survey_id = serializers.UUIDField(source="survey_id", read_only=True)
    respondent_id = serializers.UUIDField(source="respondent_id", read_only=True)
    answers = ResponseAnswerOutputSerializer(many=True, read_only=True)

    class Meta:
        model = Response
        fields = [
            "id",
            "survey_id",
            "respondent_id",
            "session_token",
            "status",
            "started_at",
            "completed_at",
            "answers",
        ]
