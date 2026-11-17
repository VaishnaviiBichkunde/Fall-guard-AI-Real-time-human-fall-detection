import sys
from streamlit.testing.v1 import AppTest

sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")

def test_role(username, password, role_name):
    print(f"\n--- Testing {role_name} ({username}) ---")
    app = AppTest.from_file(APP_PATH).run(timeout=30)
    assert not app.exception
    # Enter credentials
    app.text_input[0].set_value(username)
    app.text_input[1].set_value(password)
    app.button[0].click()
    app.run(timeout=30)
    assert not app.exception
    assert app.session_state["authenticated"]
    print(f"✅ {role_name} logged in successfully.")

    # Check for Sign Out button
    logout_btns = [b for b in app.button if "Sign Out" in b.label]
    assert len(logout_btns) == 1, f"Expected exactly 1 Sign Out button, found {len(logout_btns)}"
    print(f"✅ Exactly 1 Sign Out button found: '{logout_btns[0].label}'")

    if "caretaker" in username:
        # Check Care Console Options radio
        radio_widgets = [r for r in app.radio if "Care Console Options" in str(r.label)]
        assert len(radio_widgets) >= 1
        options = radio_widgets[0].options
        print(f"✅ Caretaker radio options found: {options}")

        # Test selecting a specific option, e.g. "👤 Resident Care Profile"
        radio_widgets[0].set_value("👤 Resident Care Profile")
        app.run(timeout=30)
        assert not app.exception
        assert any("Resident Profile" in m.value for m in app.markdown)
        print("✅ Caretaker navigation to '👤 Resident Care Profile' succeeded.")

        # Test selecting "📑 Emergency History & Reports"
        radio_widgets[0].set_value("📑 Emergency History & Reports")
        app.run(timeout=30)
        assert not app.exception
        assert any("Recent Emergency History" in m.value for m in app.markdown)
        print("✅ Caretaker navigation to '📑 Emergency History & Reports' succeeded.")

        # Test selecting "📞 Quick Intercom Directory"
        radio_widgets[0].set_value("📞 Quick Intercom Directory")
        app.run(timeout=30)
        assert not app.exception
        assert any("Quick Intercom" in m.value for m in app.markdown)
        print("✅ Caretaker navigation to '📞 Quick Intercom Directory' succeeded.")

    # Test Logout
    logout_btns[0].click()
    app.run(timeout=30)
    assert not app.exception
    assert not app.session_state["authenticated"]
    print(f"✅ {role_name} logged out successfully. Returned to login screen.")

test_role("mohini", "mohini123", "Caretaker 1")
test_role("radha", "radha123", "Caretaker 2")
test_role("admin", "admin123", "Admin")
test_role("user", "user123", "Resident User")

print("\n🎉 ALL 4 ROLES TESTED AND VERIFIED SUCCESSFULLY!")
