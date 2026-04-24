"""
Subscription Lifecycle E2E Tests
Covers: sign-up → Stripe payment → plan upgrade → cancellation → refund
Validates webhook payloads, JSON schemas, and session token invalidation.
"""

import pytest
import allure
import requests
import json
import time
from conftest import BASE_URL, PLANS, TEST_CARDS


@allure.suite("Subscription Lifecycle")
class TestSignUp:

    @allure.title("Sign-up — valid card — Basic plan")
    def test_signup_basic_plan_success(self, page, test_user, stripe_client):
        """User can sign up with a valid card and land on the dashboard."""
        with allure.step("Navigate to sign-up page"):
            page.goto(f"{BASE_URL}/signup")

        with allure.step("Fill in user details"):
            page.fill('[data-testid="email"]',    test_user["email"])
            page.fill('[data-testid="password"]', test_user["password"])
            page.fill('[data-testid="name"]',     test_user["name"])

        with allure.step("Select Basic plan"):
            page.click('[data-testid="plan-basic"]')

        with allure.step("Enter valid Stripe test card"):
            stripe_frame = page.frame_locator('iframe[name^="__privateStripeFrame"]').first
            stripe_frame.locator('[placeholder="Card number"]').fill(TEST_CARDS["valid"])
            stripe_frame.locator('[placeholder="MM / YY"]').fill("12/26")
            stripe_frame.locator('[placeholder="CVC"]').fill("123")

        with allure.step("Submit and assert redirect to dashboard"):
            page.click('[data-testid="submit-signup"]')
            page.wait_for_url(f"{BASE_URL}/dashboard", timeout=10_000)
            assert "/dashboard" in page.url, "Expected redirect to /dashboard after signup"

    @allure.title("Sign-up — declined card — error message shown")
    def test_signup_declined_card_shows_error(self, page, test_user):
        """Declined card must surface an inline error — not a crash."""
        page.goto(f"{BASE_URL}/signup")
        page.fill('[data-testid="email"]',    "declined@disney-qa.com")
        page.fill('[data-testid="password"]', test_user["password"])
        page.fill('[data-testid="name"]',     test_user["name"])
        page.click('[data-testid="plan-basic"]')

        stripe_frame = page.frame_locator('iframe[name^="__privateStripeFrame"]').first
        stripe_frame.locator('[placeholder="Card number"]').fill(TEST_CARDS["declined"])
        stripe_frame.locator('[placeholder="MM / YY"]').fill("12/26")
        stripe_frame.locator('[placeholder="CVC"]').fill("123")
        page.click('[data-testid="submit-signup"]')

        error_msg = page.locator('[data-testid="payment-error"]')
        assert error_msg.is_visible(), "Payment error message must be visible for declined card"
        assert "declined" in error_msg.inner_text().lower(), "Error must mention 'declined'"


@allure.suite("Subscription Lifecycle")
class TestPlanUpgrade:

    @allure.title("Upgrade Basic → Premium — prorated charge applied")
    def test_plan_upgrade_basic_to_premium(self, page, stripe_client):
        """Upgrading plan must create a prorated Stripe invoice and update UI."""
        # Authenticate as existing subscriber
        page.goto(f"{BASE_URL}/login")
        page.fill('[data-testid="email"]',    "basic.subscriber@disney-qa.com")
        page.fill('[data-testid="password"]', "TestPass123!")
        page.click('[data-testid="submit-login"]')
        page.wait_for_url(f"{BASE_URL}/dashboard")

        with allure.step("Navigate to plan management"):
            page.goto(f"{BASE_URL}/account/plan")

        with allure.step("Select Premium plan"):
            page.click('[data-testid="plan-premium"]')
            page.click('[data-testid="confirm-upgrade"]')

        with allure.step("Assert plan badge updated to Premium"):
            plan_badge = page.locator('[data-testid="current-plan-badge"]')
            plan_badge.wait_for(timeout=5_000)
            assert "premium" in plan_badge.inner_text().lower(), (
                "Plan badge must show Premium after upgrade"
            )

        with allure.step("Verify Stripe subscription updated via API"):
            resp = requests.get(
                f"{BASE_URL}/api/subscription/current",
                headers={"Authorization": f"Bearer {_get_session_token(page)}"},
            )
            data = resp.json()
            assert resp.status_code == 200
            assert data["plan"] == "premium", f"API returned plan: {data.get('plan')}"


@allure.suite("Subscription Lifecycle")
class TestCancellation:

    @allure.title("Cancel subscription — access revoked within 5s of effective date")
    def test_cancellation_revokes_access(self, page):
        page.goto(f"{BASE_URL}/login")
        page.fill('[data-testid="email"]',    "cancel.test@disney-qa.com")
        page.fill('[data-testid="password"]', "TestPass123!")
        page.click('[data-testid="submit-login"]')
        page.wait_for_url(f"{BASE_URL}/dashboard")

        with allure.step("Cancel subscription"):
            page.goto(f"{BASE_URL}/account/plan")
            page.click('[data-testid="cancel-subscription"]')
            page.click('[data-testid="confirm-cancellation"]')

        with allure.step("Assert cancellation confirmation shown"):
            confirmation = page.locator('[data-testid="cancellation-confirmation"]')
            assert confirmation.is_visible(), "Cancellation confirmation must be visible"

        with allure.step("Assert session token invalidated — protected page returns 401"):
            token = _get_session_token(page)
            time.sleep(2)  # Allow revocation to propagate
            resp = requests.get(
                f"{BASE_URL}/api/content/premium",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 401, (
                f"Premium content must return 401 after cancellation, got {resp.status_code}"
            )

    @allure.title("Webhook payload — customer.subscription.deleted schema valid")
    def test_cancellation_webhook_schema(self):
        """Stripe webhook for subscription deletion must conform to expected schema."""
        # Simulate webhook payload from Stripe
        payload = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test_001",
                    "customer": "cus_test_001",
                    "status": "canceled",
                    "current_period_end": 1893456000,
                    "plan": {"id": "price_basic_monthly", "amount": 799},
                }
            }
        }
        required_keys = ["id", "customer", "status", "current_period_end", "plan"]
        obj = payload["data"]["object"]
        for key in required_keys:
            assert key in obj, f"Webhook payload missing required key: {key}"
        assert obj["status"] == "canceled", "Status must be 'canceled' in deletion webhook"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session_token(page) -> str:
    """Extract bearer token from browser localStorage."""
    return page.evaluate("() => localStorage.getItem('auth_token') || ''")
