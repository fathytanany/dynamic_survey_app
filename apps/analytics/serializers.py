from rest_framework import serializers


class DailySubmissionSerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()


class SurveyAnalyticsSerializer(serializers.Serializer):
    total_responses = serializers.IntegerField()
    complete_responses = serializers.IntegerField()
    partial_responses = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    avg_completion_time_seconds = serializers.FloatField(allow_null=True)
    daily_submissions = DailySubmissionSerializer(many=True)


class AnswerDistributionSerializer(serializers.Serializer):
    value = serializers.CharField()
    count = serializers.IntegerField()


class FieldAnalyticsSerializer(serializers.Serializer):
    field_id = serializers.UUIDField()
    label = serializers.CharField()
    field_type = serializers.CharField()
    response_count = serializers.IntegerField()
    answer_distribution = AnswerDistributionSerializer(many=True, allow_null=True)
    note = serializers.CharField(required=False, allow_null=True)


class ExportRequestSerializer(serializers.Serializer):
    FORMAT_CHOICES = [("json", "JSON"), ("csv", "CSV")]
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default="json")


class TaskStatusSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    status = serializers.CharField()
    result = serializers.JSONField(allow_null=True)
