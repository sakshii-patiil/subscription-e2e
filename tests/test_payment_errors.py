"""
Payment Error Handling Tests
Validates HTTP 4xx error responses, form validation rules,
and insufficient-funds edge cases.
"""

import pytest
import allure
import requests
from conftest import BASE_URL, TEST_CARDS


@allure.suite("Payment Error Handling")
class TestPaymentErrors:

    @allure.title("Insufficient funds — user shown retry prompt")
    def test_insufficient_funds_card(self, page, test_user):
        page.goto(f"{BASE_URL}/signup")
        page.fill('[data-testid="email"]',    "funds.test@disney-qa.com")
        page.fill('[data-testid="password"]', test_user["password"])
        page.fill('[data-testid="name"]',     test_user["name"])
        page.click('[data-testid="plan-basic"]')

        stripe_frame = page.frame_locator('iframe[name^="__privateStripeFrame"]').first
        stripe_frame.locator('[placeholder="Card number"]').fill(TEST_CARDS["insufficient_funds"])
        stripe_frame.locator('[placeholder="MM / YY"]').fill("12/26")
        stripe_frame.locator('[placeholder="CVC"]').fill("123")
        page.click('[data-testid="submit-signup"]')

        error = page.locator('[data-testid="payment-error"]')
        assert error.is_visible()
        assert "insufficient" in error.inner_text().lower() or "funds" in error.inner_text().lower()

    @allure.title("Empty card fields — inline validation fires before submit")
    def test_empty_card_validation(self, page, test_user):
        page.goto(f"{BASE_URL}/signup")
        page.fill('[data-testid="email"]',    test_user["email"])
        page.fill('[data-testid="password"]', test_user["password"])
        page.click('[data-testid="plan-basic"]')
        page.click('[data-testid="submit-signup"]')  # submit without card

        error = page.locator('[data-testid="payment-error"]')
        assert error.is_visible(), "Validation error must show for empty card fields"

    @allure.title("API — POST /api/checkout with invalid plan_id returns HTTP 422")
    def test_invalid_plan_id_returns_422(self):
        resp = requests.post(
            f"{BASE_URL}/api/checkout",
            json={"plan_id": "price_nonexistent_plan", "payment_method": "pm_test_001"},
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422, (
            f"Invalid plan_id must return 422 Unprocessable Entity, got {resp.status_code}"
        )
        body = resp.json()
        assert "error" in body, "422 response must include an error field"

    @allure.title("API — POST /api/checkout without auth returns HTTP 401")
    def test_unauthenticated_checkout_returns_401(self):
        resp = requests.post(
            f"{BASE_URL}/api/checkout",
            json={"plan_id": "price_basic_monthly", "payment_method": "pm_test_001"},
        )
        assert resp.status_code == 401, (
            f"Unauthenticated checkout must return 401, got {resp.status_code}"
        )

    @allure.title("Expired card — graceful error, no 500 thrown")
    def test_expired_card_no_500(self, page, test_user):
        page.goto(f"{BASE_URL}/signup")
        page.fill('[data-testid="email"]',    "expired@disney-qa.com")
        page.fill('[data-testid="password"]', test_user["password"])
        page.click('[data-testid="plan-basic"]')

        stripe_frame = page.frame_locator('iframe[name^="__privateStripeFrame"]').first
        stripe_frame.locator('[placeholder="Card number"]').fill("4000000000000069")
        stripe_frame.locator('[placeholder="MM / YY"]').fill("01/20")  # expired
        stripe_frame.locator('[placeholder="CVC"]').fill("123")
        page.click('[data-testid="submit-signup"]')

        # Must show error, not crash to 500 page
        assert "/error" not in page.url, "Expired card must not redirect to error page"
        error = page.locator('[data-testid="payment-error"]')
        assert error.is_visible(), "Inline error must appear for expired card"
