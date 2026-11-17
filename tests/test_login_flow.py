"""Tests for the existing Streamlit login and role-routing flow."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")
ACCOUNTS = [
    ("admin", "admin123", "admin", "System Administrator Master Console"),
    ("mohini", "mohini123", "caretaker_1", "Caretaker 1 Portal"),
    ("radha", "radha123", "caretaker_2", "Caretaker 2 Portal"),
    ("user", "user123", "user", "Resident Safety & Well-Being Hub"),
]


def _login(username, password):
    app = AppTest.from_file(APP_PATH).run(timeout=30)
    app.text_input[0].set_value(username)
    app.text_input[1].set_value(password)
    app.button[0].click()
    return app.run(timeout=30)


def test_login_form_does_not_prefill_or_expose_password():
    app = AppTest.from_file(APP_PATH).run(timeout=30)

    assert app.text_input[0].value == ""
    assert app.text_input[1].value == ""
    password_input = app.text_input[1].proto
    assert password_input.Type.Name(password_input.type) == "PASSWORD"
    assert not any(
        selectbox.label == "Quick Switch Active Portal:"
        for selectbox in app.selectbox
    )


def test_invalid_credentials_show_clear_error():
    app = _login("admin", "incorrect")

    assert len(app.error) == 1
    assert "username or password" in app.error[0].value.lower()
    assert not app.session_state["authenticated"]


@pytest.mark.parametrize(
    ("username", "password", "expected_message"),
    [
        ("", "admin123", "Enter your username"),
        ("admin", "", "Enter your password"),
    ],
)
def test_login_requires_both_credentials(username, password, expected_message):
    app = _login(username, password)

    assert any(expected_message in item.value for item in app.warning)
    assert not app.session_state["authenticated"]


@pytest.mark.parametrize(
    ("username", "password", "role", "dashboard_heading"),
    ACCOUNTS,
)
def test_login_routes_account_to_its_dashboard(username, password, role, dashboard_heading):
    app = _login(username, password)

    assert app.session_state["authenticated"]
    assert app.session_state["user_role"] == role
    assert any(dashboard_heading in item.value for item in app.markdown)
    assert any(button.label == "🚪 Sign Out" for button in app.button)
    assert not any(
        selectbox.label == "Quick Switch Active Portal:"
        for selectbox in app.selectbox
    )


def test_logout_returns_to_empty_login_form():
    app = _login("user", "user123")
    logout_button = next(button for button in app.button if button.label == "🚪 Sign Out")
    logout_button.click()
    app.run(timeout=30)

    assert not app.session_state["authenticated"]
    assert app.session_state["user_role"] == ""
    assert app.text_input[0].value == ""
    assert app.text_input[1].value == ""
    password_input = app.text_input[1].proto
    assert password_input.Type.Name(password_input.type) == "PASSWORD"


def test_tampered_role_session_is_returned_to_login():
    app = _login("user", "user123")
    app.session_state["username"] = "admin"
    app.run(timeout=30)

    assert not app.session_state["authenticated"]
    assert app.session_state["user_role"] == ""
    assert any("verified" in item.value.lower() for item in app.warning)
    assert not any(
        "System Administrator Master Console" in item.value
        for item in app.markdown
    )
