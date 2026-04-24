"""
Fixtures for eCommerce Subscription Lifecycle E2E Suite.
Sets up Playwright browser + Stripe test-mode client.
"""

import pytest
import stripe
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

# Stripe test-mode key (safe to commit test keys)
stripe.api_key = os.getenv("STRIPE_TEST_SECRET_KEY", "sk_test_placeholder")

BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def browser_context():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir="videos/" if os.getenv("RECORD_VIDEO") else None,
        )
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(browser_context):
    page = browser_context.new_page()
    yield page
    page.close()


@pytest.fixture(scope="session")
def stripe_client():
    return stripe


@pytest.fixture
def test_user():
    return {
        "email":    "test.user@disney-qa.com",
        "password": "TestPass123!",
        "name":     "QA Test User",
    }


PLANS = {
    "basic":    {"price_id": "price_basic_monthly",    "amount": 799},
    "standard": {"price_id": "price_standard_monthly", "amount": 1399},
    "premium":  {"price_id": "price_premium_monthly",  "amount": 1999},
}

TEST_CARDS = {
    "valid":    "4242424242424242",
    "declined": "4000000000000002",
    "insufficient_funds": "4000000000009995",
}
