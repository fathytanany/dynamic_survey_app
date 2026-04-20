from django.urls import path

from apps.users.views import (
    LoginView,
    ProfileView,
    RefreshTokenView,
    RegisterView,
    UserDetailView,
    UserListView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshTokenView.as_view(), name="auth-refresh"),
    path("profile/", ProfileView.as_view(), name="auth-profile"),
    # Admin-only user management
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/<uuid:user_id>/", UserDetailView.as_view(), name="user-detail"),
]
