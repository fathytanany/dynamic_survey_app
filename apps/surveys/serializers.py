from rest_framework import serializers

from apps.surveys.models import Field, FieldCondition, FieldOption, Section, Survey


# ---------------------------------------------------------------------------
# Read serializers (nested, used for detail views)
# ---------------------------------------------------------------------------

class FieldOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldOption
        fields = ["id", "label", "value", "order", "depends_on_option"]


class FieldSerializer(serializers.ModelSerializer):
    options = FieldOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Field
        fields = [
            "id", "label", "field_type", "is_required", "order",
            "is_sensitive", "placeholder", "help_text", "config", "options",
        ]


class SectionSerializer(serializers.ModelSerializer):
    fields = FieldSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = ["id", "title", "order", "condition", "fields"]


class SurveyDetailSerializer(serializers.ModelSerializer):
    sections = SectionSerializer(many=True, read_only=True)
    owner = serializers.SerializerMethodField()

    class Meta:
        model = Survey
        fields = [
            "id", "title", "description", "owner", "status", "version",
            "created_at", "updated_at", "is_anonymous", "requires_auth", "sections",
        ]

    def get_owner(self, obj):
        return {"id": str(obj.owner_id), "email": obj.owner.email}


# ---------------------------------------------------------------------------
# Write serializers (flat, used for create/update)
# ---------------------------------------------------------------------------

class SurveyWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Survey
        fields = ["title", "description", "is_anonymous", "requires_auth"]


class SurveyListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view — no nested sections."""
    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta:
        model = Survey
        fields = [
            "id", "title", "description", "owner_email", "status",
            "version", "created_at", "updated_at", "is_anonymous", "requires_auth",
        ]


class SectionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ["title", "order", "condition"]


class FieldWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Field
        fields = [
            "label", "field_type", "is_required", "order",
            "is_sensitive", "placeholder", "help_text", "config",
        ]


class FieldOptionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldOption
        fields = ["label", "value", "order", "depends_on_option"]


class FieldConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldCondition
        fields = [
            "id", "source_field", "operator", "expected_value",
            "target_field", "target_section",
        ]
        # source_field is injected from the URL in ConditionCreateView
        extra_kwargs = {"source_field": {"required": False}}

    def validate(self, attrs):
        if not attrs.get("target_field") and not attrs.get("target_section"):
            raise serializers.ValidationError(
                "A condition must target either a field or a section."
            )
        return attrs
