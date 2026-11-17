import sys
from pathlib import Path
from streamlit.testing.v1 import AppTest

sys.stdout.reconfigure(encoding="utf-8")
APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")

print("--- Testing Caretaker 1 Navigation ---")
app = AppTest.from_file(APP_PATH).run(timeout=30)
app.text_input[0].set_value("mohini")
app.text_input[1].set_value("mohini123")
app.button[0].click()
app.run(timeout=30)
assert app.session_state["authenticated"]

radio = next(r for r in app.radio if "Care Console Options" in str(r.label))
print("Available options:", radio.options)

# Helper to get current radio widget
def get_radio():
    return next(r for r in app.radio if "Care Console Options" in str(r.label))

# 1. Test Resident Profile
print("Navigating to '👤 Resident Care Profile'...")
get_radio().set_value("👤 Resident Care Profile")
app.run(timeout=30)
assert not app.exception
assert any("Resident Profile" in m.value for m in app.markdown)
print("✅ Resident Profile rendered.")

# 2. Test Emergency History
print("Navigating to '📑 Emergency History & Reports'...")
get_radio().set_value("📑 Emergency History & Reports")
app.run(timeout=30)
assert not app.exception
assert any("Recent Emergency History" in m.value for m in app.markdown)
print("✅ Emergency History rendered.")

# 3. Test Caregiver Duty Roster
print("Navigating to '👥 Caregiver Duty Roster'...")
get_radio().set_value("👥 Caregiver Duty Roster")
app.run(timeout=30)
assert not app.exception
assert any("Caregiver Availability & Rosters" in m.value for m in app.markdown)
print("✅ Caregiver Duty Roster rendered.")

# 4. Test Quick Intercom
print("Navigating to '📞 Quick Intercom Directory'...")
get_radio().set_value("📞 Quick Intercom Directory")
app.run(timeout=30)
assert not app.exception
assert any("Quick Intercom Contacts" in m.value for m in app.markdown)
print("✅ Quick Intercom Contacts rendered.")

# 5. Test Live Room Monitoring
print("Navigating to 'Live Room Monitoring 📹'...")
get_radio().set_value("Live Room Monitoring 📹")
app.run(timeout=30)
assert not app.exception
assert any("Live Patient-Room Monitoring" in m.value or "Live Camera Stream" in m.value for m in app.markdown)
print("✅ Live Room Monitoring rendered.")

# 6. Test Complete Care Console
print("Navigating to '📊 Complete Care Console'...")
get_radio().set_value("📊 Complete Care Console")
app.run(timeout=30)
assert not app.exception
print("✅ Complete Care Console rendered.")

print("\n🎉 ALL CARETAKER CONSOLE OPTIONS TESTED AND WORKING PERFECTLY!")
