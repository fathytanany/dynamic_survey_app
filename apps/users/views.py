from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from apps.users.permissions import IsAdminUser
from apps.users.serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserManagementSerializer,
    UserProfileSerializer,
)
from apps.utils import error_response, success_response
from services import user_service


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True), name="dispatch")
class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Register a new user",
        request=RegisterSerializer,
        examples=[
            OpenApiExample(
                "Viewer registration",
                value={
                    "email": "jane.doe@example.com",
                    "password": "Str0ng!Pass",
                    "password_confirm": "Str0ng!Pass",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "role": "data_viewer",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Admin registration",
                value={
                    "email": "admin@example.com",
                    "password": "Adm!nPass99",
                    "password_confirm": "Adm!nPass99",
                    "first_name": "Admin",
                    "last_name": "User",
                    "role": "admin",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success (201)",
                value={
                    "success": True,
                    "message": "User registered successfully.",
                    "data": {
                        "user": {
                            "id": "a1b2c3d4-0000-0000-0000-000000000001",
                            "email": "jane.doe@example.com",
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "role": "data_viewer",
                            "created_at": "2026-04-21T10:00:00Z",
                            "updated_at": "2026-04-21T10:00:00Z",
                        },
                        "tokens": {
                            "access": "<jwt-access-token>",
                            "refresh": "<jwt-refresh-token>",
                        },
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                errors=serializer.errors,
                message="Registration failed.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = user_service.register_user(serializer.validated_data)
        return success_response(
            data={
                "user": UserProfileSerializer(result["user"]).data,
                "tokens": result["tokens"],
            },
            message="User registered successfully.",
            status=status.HTTP_201_CREATED,
        )


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True), name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Authenticate and obtain JWT tokens",
        request=LoginSerializer,
        examples=[
            OpenApiExample(
                "Login request",
                value={"email": "jane.doe@example.com", "password": "Str0ng!Pass"},
                request_only=True,
            ),
            OpenApiExample(
                "Success (200)",
                value={
                    "success": True,
                    "message": "Login successful.",
                    "data": {
                        "user": {
                            "id": "a1b2c3d4-0000-0000-0000-000000000001",
                            "email": "jane.doe@example.com",
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "role": "data_viewer",
                            "created_at": "2026-04-21T10:00:00Z",
                            "updated_at": "2026-04-21T10:00:00Z",
                        },
                        "tokens": {
                            "access": "<jwt-access-token>",
                            "refresh": "<jwt-refresh-token>",
                        },
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Invalid credentials (401)",
                value={
                    "success": False,
                    "message": "Authentication failed.",
                    "data": None,
                    "errors": {"detail": "Invalid email or password."},
                },
                response_only=True,
                status_codes=["401"],
            ),
        ],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                errors=serializer.errors,
                message="Invalid input.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = user_service.authenticate_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if result is None:
            return error_response(
                errors={"detail": "Invalid email or password."},
                message="Authentication failed.",
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return success_response(
            data={
                "user": UserProfileSerializer(result["user"]).data,
                "tokens": result["tokens"],
            },
            message="Login successful.",
        )


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Refresh JWT access token",
        request=TokenRefreshSerializer,
        examples=[
            OpenApiExample(
                "Refresh request",
                value={"refresh": "<jwt-refresh-token>"},
                request_only=True,
            ),
            OpenApiExample(
                "Success (200)",
                value={
                    "success": True,
                    "message": "Token refreshed.",
                    "data": {"access": "<new-jwt-access-token>"},
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken) as exc:
            return error_response(
                errors={"refresh": str(exc)},
                message="Invalid or expired refresh token.",
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return success_response(data=serializer.validated_data, message="Token refreshed.")


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get current user profile",
        examples=[
            OpenApiExample(
                "Success (200)",
                value={
                    "success": True,
                    "message": "",
                    "data": {
                        "id": "a1b2c3d4-0000-0000-0000-000000000001",
                        "email": "jane.doe@example.com",
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "role": "data_viewer",
                        "created_at": "2026-04-21T10:00:00Z",
                        "updated_at": "2026-04-21T10:00:00Z",
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return success_response(data=serializer.data)

    @extend_schema(
        summary="Partially update current user profile",
        request=UserProfileSerializer,
        examples=[
            OpenApiExample(
                "Update name",
                value={"first_name": "Janet", "last_name": "Smith"},
                request_only=True,
            ),
            OpenApiExample(
                "Success (200)",
                value={
                    "success": True,
                    "message": "Profile updated successfully.",
                    "data": {
                        "id": "a1b2c3d4-0000-0000-0000-000000000001",
                        "email": "jane.doe@example.com",
                        "first_name": "Janet",
                        "last_name": "Smith",
                        "role": "data_viewer",
                        "created_at": "2026-04-21T10:00:00Z",
                        "updated_at": "2026-04-21T11:00:00Z",
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(
                errors=serializer.errors,
                message="Profile update failed.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        updated_user = user_service.update_user_profile(
            request.user, serializer.validated_data
        )
        return success_response(
            data=UserProfileSerializer(updated_user).data,
            message="Profile updated successfully.",
        )


class UserListView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="List all users (admin only)",
        examples=[
            OpenApiExample(
                "Success (200)",
                value={
                    "success": True,
                    "message": "",
                    "data": [
                        {
                            "id": "a1b2c3d4-0000-0000-0000-000000000001",
                            "email": "jane.doe@example.com",
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "role": "data_viewer",
                            "is_active": True,
                            "created_at": "2026-04-21T10:00:00Z",
                            "updated_at": "2026-04-21T10:00:00Z",
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
        users = user_service.get_user_list()
        serializer = UserManagementSerializer(users, many=True)
        return success_response(data=serializer.data)


class UserDetailView(APIView):
    permission_classes = [IsAdminUser]

    def _get_user_or_404(self, user_id):
        user = user_service.get_user_by_id(user_id)
        if user is None:
            return None, error_response(
                errors={"detail": "User not found."},
                message="Not found.",
                status=status.HTTP_404_NOT_FOUND,
            )
        return user, None

    @extend_schema(
        summary="Get a specific user (admin only)",
        examples=[
            OpenApiExample(
                "Success (200)",
                value={
                    "success": True,
                    "message": "",
                    "data": {
                        "id": "a1b2c3d4-0000-0000-0000-000000000001",
                        "email": "jane.doe@example.com",
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "role": "data_viewer",
                        "is_active": True,
                        "created_at": "2026-04-21T10:00:00Z",
                        "updated_at": "2026-04-21T10:00:00Z",
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get(self, request, user_id):
        user, err = self._get_user_or_404(user_id)
        if err:
            return err
        return success_response(data=UserManagementSerializer(user).data)

    @extend_schema(
        summary="Update a user's role or status (admin only)",
        request=UserManagementSerializer,
        examples=[
            OpenApiExample(
                "Deactivate user",
                value={"is_active": False},
                request_only=True,
            ),
            OpenApiExample(
                "Change role",
                value={"role": "analyst"},
                request_only=True,
            ),
            OpenApiExample(
                "Success (200)",
                value={
                    "success": True,
                    "message": "User updated successfully.",
                    "data": {
                        "id": "a1b2c3d4-0000-0000-0000-000000000001",
                        "email": "jane.doe@example.com",
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "role": "analyst",
                        "is_active": True,
                        "created_at": "2026-04-21T10:00:00Z",
                        "updated_at": "2026-04-21T12:00:00Z",
                    },
                    "errors": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def patch(self, request, user_id):
        user, err = self._get_user_or_404(user_id)
        if err:
            return err
        serializer = UserManagementSerializer(user, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(
                errors=serializer.errors,
                message="Update failed.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        updated_user = user_service.update_user_profile(user, serializer.validated_data)
        return success_response(
            data=UserManagementSerializer(updated_user).data,
            message="User updated successfully.",
        )

    @extend_schema(
        summary="Delete a user (admin only)",
        examples=[
            OpenApiExample(
                "Success (204)",
                value={"success": True, "message": "User deleted successfully.", "data": None, "errors": None},
                response_only=True,
                status_codes=["204"],
            ),
        ],
    )
    def delete(self, request, user_id):
        user, err = self._get_user_or_404(user_id)
        if err:
            return err
        user_service.delete_user(user)
        return success_response(message="User deleted successfully.", status=status.HTTP_204_NO_CONTENT)
