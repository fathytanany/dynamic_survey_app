from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
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

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return success_response(data=serializer.data)

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

    def get(self, request, user_id):
        user, err = self._get_user_or_404(user_id)
        if err:
            return err
        return success_response(data=UserManagementSerializer(user).data)

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

    def delete(self, request, user_id):
        user, err = self._get_user_or_404(user_id)
        if err:
            return err
        user_service.delete_user(user)
        return success_response(message="User deleted successfully.", status=status.HTTP_204_NO_CONTENT)
