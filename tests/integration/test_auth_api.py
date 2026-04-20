"""
Integration tests for /api/v1/auth/* endpoints.
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tests.conftest import make_auth_client
from tests.factories import AdminUserFactory, UserFactory


BASE = "/api/v1/auth"


@pytest.mark.integration
@pytest.mark.django_db
class TestRegister:
    def test_success_returns_201_with_tokens(self, api_client):
        payload = {
            "email": "new@example.com",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "first_name": "Alice",
            "last_name": "Smith",
        }
        resp = api_client.post(f"{BASE}/register/", payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["success"] is True
        assert "access" in data["data"]["tokens"]
        assert "refresh" in data["data"]["tokens"]
        assert data["data"]["user"]["email"] == "new@example.com"

    def test_password_mismatch_returns_400(self, api_client):
        payload = {
            "email": "user@example.com",
            "password": "StrongPass123!",
            "password_confirm": "WrongPass123!",
        }
        resp = api_client.post(f"{BASE}/register/", payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["success"] is False

    def test_duplicate_email_returns_400(self, api_client, db):
        UserFactory(email="dup@example.com")
        payload = {
            "email": "dup@example.com",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        }
        resp = api_client.post(f"{BASE}/register/", payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_email_returns_400(self, api_client):
        payload = {"password": "StrongPass123!", "password_confirm": "StrongPass123!"}
        resp = api_client.post(f"{BASE}/register/", payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_weak_password_returns_400(self, api_client):
        payload = {
            "email": "weak@example.com",
            "password": "123",
            "password_confirm": "123",
        }
        resp = api_client.post(f"{BASE}/register/", payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_default_role_is_data_viewer(self, api_client):
        payload = {
            "email": "viewer@example.com",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        }
        resp = api_client.post(f"{BASE}/register/", payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["data"]["user"]["role"] == "data_viewer"


@pytest.mark.integration
@pytest.mark.django_db
class TestLogin:
    def test_success_returns_200_with_tokens(self, api_client, db):
        user = UserFactory(email="login@example.com")
        resp = api_client.post(
            f"{BASE}/login/",
            {"email": "login@example.com", "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()["data"]
        assert "access" in data["tokens"]
        assert data["user"]["email"] == "login@example.com"

    def test_wrong_password_returns_401(self, api_client, db):
        UserFactory(email="login@example.com")
        resp = api_client.post(
            f"{BASE}/login/",
            {"email": "login@example.com", "password": "WrongPassword!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_nonexistent_user_returns_401(self, api_client):
        resp = api_client.post(
            f"{BASE}/login/",
            {"email": "nobody@example.com", "password": "Irrelevant1!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_fields_returns_400(self, api_client):
        resp = api_client.post(f"{BASE}/login/", {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_inactive_user_returns_401(self, api_client, db):
        UserFactory(email="inactive@example.com", is_active=False)
        resp = api_client.post(
            f"{BASE}/login/",
            {"email": "inactive@example.com", "password": "StrongPass123!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.integration
@pytest.mark.django_db
class TestRefreshToken:
    def test_valid_refresh_returns_new_access(self, api_client, db):
        user = UserFactory()
        refresh = RefreshToken.for_user(user)
        resp = api_client.post(
            f"{BASE}/refresh/",
            {"refresh": str(refresh)},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.json()["data"]

    def test_invalid_refresh_returns_401(self, api_client):
        resp = api_client.post(
            f"{BASE}/refresh/",
            {"refresh": "not.a.valid.token"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.integration
@pytest.mark.django_db
class TestProfile:
    def test_get_profile_authenticated(self, db):
        user = UserFactory(first_name="Bob")
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/profile/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"]["first_name"] == "Bob"

    def test_get_profile_unauthenticated(self, api_client):
        resp = api_client.get(f"{BASE}/profile/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patch_profile_updates_name(self, db):
        user = UserFactory(first_name="Old")
        client = make_auth_client(user)
        resp = client.patch(
            f"{BASE}/profile/",
            {"first_name": "New"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"]["first_name"] == "New"

    def test_patch_profile_cannot_change_role(self, db):
        user = UserFactory(role="data_viewer")
        client = make_auth_client(user)
        # UserProfileSerializer marks role as read_only, so this is a no-op
        resp = client.patch(
            f"{BASE}/profile/",
            {"role": "admin"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"]["role"] == "data_viewer"


@pytest.mark.integration
@pytest.mark.django_db
class TestUserManagement:
    def test_user_list_accessible_by_admin(self, db):
        admin = AdminUserFactory()
        client = make_auth_client(admin)
        UserFactory.create_batch(3)
        resp = client.get(f"{BASE}/users/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()["data"]) >= 4  # 3 + admin

    def test_user_list_forbidden_for_non_admin(self, db):
        user = UserFactory(role="analyst")
        client = make_auth_client(user)
        resp = client.get(f"{BASE}/users/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_user_list_forbidden_unauthenticated(self, api_client):
        resp = api_client.get(f"{BASE}/users/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_user_detail_admin(self, db):
        admin = AdminUserFactory()
        target = UserFactory()
        client = make_auth_client(admin)
        resp = client.get(f"{BASE}/users/{target.pk}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"]["email"] == target.email

    def test_get_user_detail_not_found(self, db):
        import uuid
        admin = AdminUserFactory()
        client = make_auth_client(admin)
        resp = client.get(f"{BASE}/users/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_patch_user_role_admin(self, db):
        admin = AdminUserFactory()
        target = UserFactory(role="data_viewer")
        client = make_auth_client(admin)
        resp = client.patch(
            f"{BASE}/users/{target.pk}/",
            {"role": "analyst"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"]["role"] == "analyst"

    def test_delete_user_admin(self, db):
        admin = AdminUserFactory()
        target = UserFactory()
        client = make_auth_client(admin)
        resp = client.delete(f"{BASE}/users/{target.pk}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
