from django.contrib.auth import authenticate

from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


def _tokens_for_user(user: User) -> dict:
    """Generate and return a fresh JWT access/refresh token pair for *user*."""
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def register_user(validated_data: dict) -> dict:
    """Create a new user and return JWT tokens."""
    user = User.objects.create_user(
        email=validated_data["email"],
        password=validated_data["password"],
        first_name=validated_data.get("first_name", ""),
        last_name=validated_data.get("last_name", ""),
        role=validated_data.get("role", User.Role.DATA_VIEWER),
    )
    tokens = _tokens_for_user(user)
    return {"user": user, "tokens": tokens}


def authenticate_user(email: str, password: str) -> dict | None:
    """Authenticate by email/password; return tokens or None on failure."""
    user = authenticate(username=email, password=password)
    if user is None or not user.is_active:
        return None
    tokens = _tokens_for_user(user)
    return {"user": user, "tokens": tokens}


def get_user_list():
    """Return a queryset of all users."""
    return User.objects.all()


def get_user_by_id(user_id: str) -> User | None:
    """Return a User by primary key; None if not found."""
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return None


def update_user_profile(user: User, data: dict) -> User:
    """Apply *data* fields to *user* and persist the changes."""
    for field, value in data.items():
        setattr(user, field, value)
    user.save()
    return user


def delete_user(user: User) -> None:
    """Permanently delete *user* from the database."""
    user.delete()
