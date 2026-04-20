"""
Shared pytest fixtures for the entire test suite.
"""
import pytest
from cryptography.fernet import Fernet
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

# One stable Fernet key reused across all tests in the session.
TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# Global settings overrides applied before every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _test_settings(settings):
    """Force test-safe settings: Fernet key, no rate-limiting, eager Celery."""
    settings.ENCRYPTION_KEY = TEST_ENCRYPTION_KEY
    settings.RATELIMIT_ENABLE = False
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


# ---------------------------------------------------------------------------
# Reusable API client helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


def make_auth_client(user):
    """Return an APIClient pre-loaded with a Bearer token for *user*."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_user(db):
    from tests.factories import UserFactory
    return UserFactory(role="admin")


@pytest.fixture
def analyst_user(db):
    from tests.factories import UserFactory
    return UserFactory(role="analyst")


@pytest.fixture
def data_viewer_user(db):
    from tests.factories import UserFactory
    return UserFactory(role="data_viewer")


@pytest.fixture
def admin_client(admin_user):
    return make_auth_client(admin_user), admin_user


@pytest.fixture
def analyst_client(analyst_user):
    return make_auth_client(analyst_user), analyst_user


@pytest.fixture
def data_viewer_client(data_viewer_user):
    return make_auth_client(data_viewer_user), data_viewer_user
