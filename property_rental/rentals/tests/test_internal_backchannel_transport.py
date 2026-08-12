import pytest
from django.test import Client, override_settings


PRODUCTION_MIDDLEWARE = [
    "property_rental.middleware.InternalBackchannelSecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]


@pytest.fixture
def http_client():
    return Client()


@override_settings(
    SECURE_SSL_REDIRECT=True,
    ALLOWED_HOSTS=["rent", "rent.linik.ru", "testserver"],
    MIDDLEWARE=PRODUCTION_MIDDLEWARE,
    ROOT_URLCONF="property_rental.production_urls",
    OIDC_CALLBACK_URL="https://rent.linik.ru/oidc/callback/",
)
def test_exact_internal_backchannel_transport_reaches_the_view(http_client):
    post_response = http_client.post(
        "/oidc/backchannel-logout/", {}, HTTP_HOST="rent:8000"
    )
    get_response = http_client.get(
        "/oidc/backchannel-logout/", HTTP_HOST="rent"
    )

    assert post_response.status_code == 400
    assert get_response.status_code == 405


@override_settings(
    SECURE_SSL_REDIRECT=True,
    ALLOWED_HOSTS=["rent", "rent.linik.ru", "testserver"],
    MIDDLEWARE=PRODUCTION_MIDDLEWARE,
    ROOT_URLCONF="property_rental.production_urls",
    OIDC_CALLBACK_URL="https://rent.linik.ru/oidc/callback/",
)
def test_public_http_backchannel_transport_still_redirects_to_https(http_client):
    response = http_client.post(
        "/oidc/backchannel-logout/", {}, HTTP_HOST="rent.linik.ru"
    )

    assert response.status_code == 301
    assert response.headers["Location"].startswith("https://rent.linik.ru/")


@override_settings(
    SECURE_SSL_REDIRECT=True,
    ALLOWED_HOSTS=["rent", "rent.linik.ru", "testserver"],
    MIDDLEWARE=PRODUCTION_MIDDLEWARE,
    ROOT_URLCONF="property_rental.production_urls",
    OIDC_CALLBACK_URL="https://rent.linik.ru/oidc/callback/",
)
def test_other_internal_http_paths_still_redirect_to_https(http_client):
    response = http_client.get("/health/live", HTTP_HOST="rent:8000")

    assert response.status_code == 301
    assert response.headers["Location"].startswith("https://rent:8000/")


@pytest.mark.parametrize(
    "host",
    [
        "rent.evil.example",
        "rent:8000.evil.example",
        "rent@evil.example",
        "*.rent",
    ],
)
@override_settings(
    SECURE_SSL_REDIRECT=True,
    ALLOWED_HOSTS=["*"],
    MIDDLEWARE=PRODUCTION_MIDDLEWARE,
    ROOT_URLCONF="property_rental.production_urls",
    OIDC_CALLBACK_URL="https://rent.linik.ru/oidc/callback/",
)
def test_confusable_hosts_never_receive_the_internal_http_bypass(http_client, host):
    response = http_client.post(
        "/oidc/backchannel-logout/", {}, HTTP_HOST=host
    )

    assert response.status_code in {301, 400}
