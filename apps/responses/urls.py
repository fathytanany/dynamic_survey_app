from django.urls import path

from apps.responses.views import MyResponsesView, ResumeResponseView, SubmitResponseView

urlpatterns = [
    path("surveys/<uuid:survey_id>/respond/", SubmitResponseView.as_view(), name="survey-respond"),
    path("responses/<str:session_token>/resume/", ResumeResponseView.as_view(), name="response-resume"),
    path("responses/mine/", MyResponsesView.as_view(), name="my-responses"),
]
