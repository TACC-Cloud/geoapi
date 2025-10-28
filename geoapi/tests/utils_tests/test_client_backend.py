from geoapi.utils.client_backend import get_client_url


def test_valid_client_urls():
    valid_urls = [
        "http://localhost:4200/",
        "http://hazmapper.local:4200/",
        "https://hazmapper.tacc.utexas.edu/",
        "https://hazmapper.tacc.utexas.edu",
        "https://hazmapper.tacc.utexas.edu/hazmapper/",
        "https://hazmapper.tacc.utexas.edu/hazmapper",
        "https://hazmapper.tacc.utexas.edu/staging/",
        "https://hazmapper.tacc.utexas.edu/staging",
        "https://hazmapper.tacc.utexas.edu/dev/",
        "https://hazmapper.tacc.utexas.edu/taggit/",
        "https://hazmapper.tacc.utexas.edu/taggit-staging/",
        "https://hazmapper.tacc.utexas.edu/taggit-dev/",
    ]

    for url in valid_urls:
        fake_path = url.rstrip("/") + "/some-page"
        result = get_client_url(fake_path)
        assert result == url.rstrip("/"), f"Expected match for {url}, got {result}"
