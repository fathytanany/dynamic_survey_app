"""
Locust load test — simulates 500 concurrent users.

Run from the project root (with Docker stack up) or point at a live server:

    locust -f tests/load/locustfile.py \
           --host http://localhost:8000 \
           --users 500 \
           --spawn-rate 20 \
           --run-time 120s \
           --headless

Targets:
  - p95 response time < 200 ms
  - Zero HTTP 5xx errors during steady-state
"""

import random
import uuid

from locust import HttpUser, SequentialTaskSet, between, task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PASSWORDS = "LoadTest123!"


def _email():
    return f"load_{uuid.uuid4().hex[:8]}@example.com"


# ---------------------------------------------------------------------------
# Auth helpers mixed in via a mixin-style base
# ---------------------------------------------------------------------------

class _AuthMixin:
    """Provides register+login utilities and stores access token."""

    access_token: str | None = None
    survey_id: str | None = None
    session_token: str | None = None

    def _headers(self):
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    def _register_and_login(self):
        email = _email()
        payload = {
            "email": email,
            "password": _PASSWORDS,
            "password_confirm": _PASSWORDS,
            "first_name": "Load",
            "last_name": "Tester",
        }
        with self.client.post(
            "/api/v1/auth/register/",
            json=payload,
            catch_response=True,
            name="/api/v1/auth/register/",
        ) as resp:
            if resp.status_code == 201:
                self.access_token = resp.json()["data"]["tokens"]["access"]
                resp.success()
            else:
                resp.failure(f"Registration failed: {resp.status_code} {resp.text}")


# ---------------------------------------------------------------------------
# Survey browsing (read-heavy, no auth required beyond initial)
# ---------------------------------------------------------------------------

class SurveyBrowseTaskSet(SequentialTaskSet, _AuthMixin):
    """Simulates an analyst browsing surveys and viewing analytics."""

    def on_start(self):
        self._register_and_login()

    @task
    def list_surveys(self):
        with self.client.get(
            "/api/v1/surveys/",
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/surveys/ (list)",
        ) as resp:
            if resp.status_code == 200:
                surveys = resp.json().get("data", [])
                if surveys:
                    self.survey_id = surveys[0]["id"]
                resp.success()
            else:
                resp.failure(f"List surveys: {resp.status_code}")

    @task
    def get_survey_detail(self):
        if not self.survey_id:
            return
        with self.client.get(
            f"/api/v1/surveys/{self.survey_id}/",
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/surveys/{id}/",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Survey detail: {resp.status_code}")

    @task
    def get_analytics(self):
        if not self.survey_id:
            return
        with self.client.get(
            f"/api/v1/surveys/{self.survey_id}/analytics/",
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/surveys/{id}/analytics/",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Analytics: {resp.status_code}")

    @task
    def get_field_analytics(self):
        if not self.survey_id:
            return
        with self.client.get(
            f"/api/v1/surveys/{self.survey_id}/analytics/fields/",
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/surveys/{id}/analytics/fields/",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Field analytics: {resp.status_code}")


# ---------------------------------------------------------------------------
# Survey creation (write-heavy, owner flow)
# ---------------------------------------------------------------------------

class SurveyCreationTaskSet(SequentialTaskSet, _AuthMixin):
    """Simulates a survey owner creating surveys with sections and fields."""

    def on_start(self):
        self._register_and_login()

    @task
    def create_survey(self):
        payload = {
            "title": f"Load Test Survey {uuid.uuid4().hex[:6]}",
            "description": "Created by load test.",
        }
        with self.client.post(
            "/api/v1/surveys/",
            json=payload,
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/surveys/ (create)",
        ) as resp:
            if resp.status_code == 201:
                self.survey_id = resp.json()["data"]["id"]
                resp.success()
            else:
                resp.failure(f"Create survey: {resp.status_code} {resp.text}")

    @task
    def add_section(self):
        if not self.survey_id:
            return
        payload = {"title": "Section A", "order": 1}
        with self.client.post(
            f"/api/v1/surveys/{self.survey_id}/sections/",
            json=payload,
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/surveys/{id}/sections/ (create)",
        ) as resp:
            if resp.status_code in (201, 400, 403):
                resp.success()
            else:
                resp.failure(f"Add section: {resp.status_code}")

    @task
    def publish_survey(self):
        if not self.survey_id:
            return
        with self.client.post(
            f"/api/v1/surveys/{self.survey_id}/publish/",
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/surveys/{id}/publish/",
        ) as resp:
            if resp.status_code in (200, 400):
                resp.success()
            else:
                resp.failure(f"Publish: {resp.status_code}")


# ---------------------------------------------------------------------------
# Survey response submission (anonymous, high volume)
# ---------------------------------------------------------------------------

class ResponseSubmissionTaskSet(SequentialTaskSet, _AuthMixin):
    """
    Simulates respondents submitting responses, including partial saves and resumes.
    Registers first to get a published survey to respond to.
    """

    section_id: str | None = None
    field_ids: list[str] = []

    def on_start(self):
        self._register_and_login()
        self._create_survey_with_fields()

    def _create_survey_with_fields(self):
        # Create survey
        resp = self.client.post(
            "/api/v1/surveys/",
            json={"title": f"Submission Survey {uuid.uuid4().hex[:6]}"},
            headers=self._headers(),
        )
        if resp.status_code != 201:
            return
        self.survey_id = resp.json()["data"]["id"]

        # Add section
        resp = self.client.post(
            f"/api/v1/surveys/{self.survey_id}/sections/",
            json={"title": "Questions", "order": 1},
            headers=self._headers(),
        )
        if resp.status_code != 201:
            return
        self.section_id = resp.json()["data"]["id"]

        # Add fields
        for i in range(3):
            resp = self.client.post(
                f"/api/v1/sections/{self.section_id}/fields/",
                json={"label": f"Q{i+1}", "field_type": "text", "order": i},
                headers=self._headers(),
            )
            if resp.status_code == 201:
                self.field_ids.append(resp.json()["data"]["id"])

        # Publish
        self.client.post(
            f"/api/v1/surveys/{self.survey_id}/publish/",
            headers=self._headers(),
        )

    @task(3)
    def submit_complete_response(self):
        if not self.survey_id or not self.field_ids:
            return
        answers = [
            {"field_id": fid, "value": f"answer_{random.randint(1, 100)}"}
            for fid in self.field_ids
        ]
        payload = {"answers": answers, "status": "complete"}
        with self.client.post(
            f"/api/v1/surveys/{self.survey_id}/respond/",
            json=payload,
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/surveys/{id}/respond/ (complete)",
        ) as resp:
            if resp.status_code in (201, 400, 401, 422):
                resp.success()
            else:
                resp.failure(f"Submit response: {resp.status_code}")

    @task(1)
    def partial_save_and_resume(self):
        if not self.survey_id or not self.field_ids:
            return

        # Partial save
        payload = {
            "answers": [{"field_id": self.field_ids[0], "value": "partial"}],
            "status": "partial",
        }
        with self.client.post(
            f"/api/v1/surveys/{self.survey_id}/respond/",
            json=payload,
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/surveys/{id}/respond/ (partial)",
        ) as resp:
            if resp.status_code == 201:
                token = resp.json()["data"]["session_token"]
                resp.success()
            else:
                resp.failure(f"Partial save: {resp.status_code}")
                return

        # Resume
        with self.client.get(
            f"/api/v1/responses/{token}/resume/",
            catch_response=True,
            name="/api/v1/responses/{token}/resume/",
        ) as resp:
            if resp.status_code in (200, 400, 404):
                resp.success()
            else:
                resp.failure(f"Resume: {resp.status_code}")

    @task(1)
    def view_my_responses(self):
        with self.client.get(
            "/api/v1/responses/mine/",
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/responses/mine/",
        ) as resp:
            if resp.status_code in (200, 401):
                resp.success()
            else:
                resp.failure(f"My responses: {resp.status_code}")


# ---------------------------------------------------------------------------
# User classes — distribute load across behaviours
# ---------------------------------------------------------------------------

class AnalystUser(HttpUser):
    """
    Heavy read user — views surveys and analytics.
    30% of the load.
    """
    weight = 30
    wait_time = between(0.5, 2)
    tasks = [SurveyBrowseTaskSet]


class SurveyOwnerUser(HttpUser):
    """
    Creates and manages surveys.
    20% of the load.
    """
    weight = 20
    wait_time = between(1, 3)
    tasks = [SurveyCreationTaskSet]


class RespondentUser(HttpUser):
    """
    Submits survey responses — the highest volume user type.
    50% of the load.
    """
    weight = 50
    wait_time = between(0.2, 1)
    tasks = [ResponseSubmissionTaskSet]
