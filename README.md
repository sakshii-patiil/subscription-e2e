# eCommerce Subscription Lifecycle E2E

Playwright + Python end-to-end test suite covering the full Disney+-style
subscription lifecycle: **sign-up → Stripe payment → plan upgrade → cancellation → refund**

## Coverage

| Test Class | Scenarios |
|---|---|
| `TestSignUp` | Valid card success, declined card error |
| `TestPlanUpgrade` | Basic → Premium upgrade, prorated charge, API schema |
| `TestCancellation` | Access revocation within SLA, session token invalidation, webhook schema |
| `TestPaymentErrors` | Insufficient funds, empty fields, invalid plan 422, unauth 401, expired card |

## Stack
- **Playwright 1.43** + **pytest-playwright** (Chromium headless)
- **Stripe test-mode** SDK for webhook payload validation
- **GitHub Actions** CI on every PR

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # set APP_BASE_URL + STRIPE_TEST_SECRET_KEY
```

## Run

```bash
pytest tests/ -v --alluredir=allure-results
allure serve allure-results
```
