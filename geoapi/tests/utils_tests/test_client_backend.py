from geoapi.utils.client_backend import get_client_url


def test_valid_client_urls():
    valid_urls = [
        "http://localhost:4200/",
        "http://hazmapper.local:4200/",
        "https://hazmapper.tacc.utexas.edu/hazmapper/",
        "https://hazmapper.tacc.utexas.edu/hazmapper",
        "https://hazmapper.tacc.utexas.edu/staging/",
        "https://hazmapper.tacc.utexas.edu/staging",
        "https://hazmapper.tacc.utexas.edu/dev/",
        "https://hazmapper.tacc.utexas.edu/taggit/",
        "https://hazmapper.tacc.utexas.edu/taggit-staging/",
        "https://hazmapper.tacc.utexas.edu/taggit-dev/",
        "https://hazmapper-tmp.tacc.utexas.edu/hazmapper/",
        "https://hazmapper-tmp.tacc.utexas.edu/hazmapper",
        "https://hazmapper-tmp.tacc.utexas.edu/staging/",
        "https://hazmapper-tmp.tacc.utexas.edu/staging",
        "https://hazmapper-tmp.tacc.utexas.edu/dev/",
        "https://hazmapper-tmp.tacc.utexas.edu/taggit/",
        "https://hazmapper-tmp.tacc.utexas.edu/taggit-staging/",
        "https://hazmapper-tmp.tacc.utexas.edu/taggit-dev/",
    ]

    for url in valid_urls:
        fake_path = url.rstrip("/") + "/some-page"
        result = get_client_url(fake_path)
        assert result == url.rstrip("/"), f"Expected match for {url}, got {result}"


def test_invalid_urls():
    invalid_urls = [
        "http://localhost:3000/",
        "https://google.com/",
        "https://hazmapper.tacc.utexas.edu/",  # root not allowed
        "https://hazmapper-tmp.tacc.utexas.edu/",  # root not allowed
    ]

    for url in invalid_urls:
        result = get_client_url(url)
        assert result is None, f"Expected None for {url}, got {result}"
