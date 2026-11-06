"""Ensure the retired OAuth controls are not reintroduced to the app."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class InterfaceContractTests(unittest.TestCase):
    def test_no_social_login_buttons_or_oauth_client(self):
        ui=(ROOT/'auth_ui.py').read_text()
        self.assertNotIn('Continue with Google',ui)
        self.assertNotIn('Continue with GitHub',ui)
        self.assertNotIn('auth_client().oauth_url',ui)
        self.assertNotIn('Finish secure sign-in',ui)
        self.assertNotIn('AUTH_FLOW_SECRET',ui)

    def test_dashboard_and_image_saving_available(self):
        ui=(ROOT/'auth_ui.py').read_text()
        dashboard=(ROOT/'dashboard_ui.py').read_text()
        self.assertIn('st.session_state["page"] = "dashboard"',ui)
        self.assertIn('Save input & result to my dashboard',dashboard)
        self.assertIn('Edit my profile',dashboard)

if __name__ == '__main__':unittest.main()
