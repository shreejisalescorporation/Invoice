import os
import unittest
from unittest.mock import patch

os.environ.setdefault("FLASK_SECRET_KEY", "test-session-secret")
os.environ.setdefault("WTF_CSRF_SECRET_KEY", "test-csrf-secret")
os.environ.setdefault("FLASK_USERS_JSON", "{}")

from werkzeug.security import generate_password_hash

import app


class FlashMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            SECRET_KEY="test-session-secret",
        )
        app.app.secret_key = "test-session-secret"

    def setUp(self):
        self.client = app.app.test_client()

    def test_failed_logins_are_shown_once_without_queueing_stale_flashes(self):
        user_hash = generate_password_hash("correct-password")
        with patch.dict(app.USERS, {"operator": user_hash}, clear=True):
            with patch.object(app, "load_customers") as load_customers:
                for _ in range(3):
                    response = self.client.post(
                        "/login",
                        data={"username": "operator", "password": "wrong-password"},
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data.count(b"Invalid credentials"), 1)

                load_customers.assert_not_called()

            with self.client.session_transaction() as session:
                self.assertNotIn("_flashes", session)

            with patch.object(app, "load_customers", return_value=[]):
                response = self.client.post(
                    "/login",
                    data={"username": "operator", "password": "correct-password"},
                    follow_redirects=True,
                )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Invalid credentials", response.data)

    def test_successful_login_clears_legacy_queued_login_errors(self):
        user_hash = generate_password_hash("correct-password")
        with patch.dict(app.USERS, {"operator": user_hash}, clear=True):
            with self.client.session_transaction() as session:
                session["_flashes"] = [
                    ("danger", "Invalid credentials"),
                    ("danger", "Invalid credentials"),
                    ("danger", "Invalid credentials"),
                ]

            with patch.object(app, "load_customers", return_value=[]):
                response = self.client.post(
                    "/login",
                    data={"username": "operator", "password": "correct-password"},
                    follow_redirects=True,
                )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Invalid credentials", response.data)
        with self.client.session_transaction() as session:
            self.assertNotIn("_flashes", session)

    def test_invoice_and_analytics_pages_consume_their_current_flashes(self):
        with patch.dict(app.USERS, {"operator": "test-hash"}, clear=True):
            for path in ("/", "/analysis"):
                with self.subTest(path=path):
                    client = app.app.test_client()
                    with client.session_transaction() as session:
                        session["_user_id"] = "operator"
                        session["_fresh"] = True
                        session["_flashes"] = [("warning", "Message for this page")]

                    with patch.object(app, "load_customers", return_value=[]):
                        response = client.get(path)

                    self.assertEqual(response.status_code, 200)
                    self.assertIn(b"Message for this page", response.data)
                    with client.session_transaction() as session:
                        self.assertNotIn("_flashes", session)

    def test_health_check_is_public_and_returns_security_headers(self):
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_logout_requires_post(self):
        with patch.dict(app.USERS, {"operator": "test-hash"}, clear=True):
            with self.client.session_transaction() as session:
                session["_user_id"] = "operator"
                session["_fresh"] = True

            self.assertEqual(self.client.get("/logout").status_code, 405)
            response = self.client.post("/logout")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)


if __name__ == "__main__":
    unittest.main()
