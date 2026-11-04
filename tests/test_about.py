from blurby import __version__


def test_about_shows_neither_request_headers_nor_the_database(app):
    response = app.test_client().get(
        "/about",
        headers={"Authorization": "Bearer test-token-123", "Cookie": "session=abc"},
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "test-token-123" not in body
    assert "session=abc" not in body
    assert "sqlite:" not in body
    # What visitors need is still there.
    assert __version__ in body
    assert "Default TTL" in body


def test_about_credits_the_photo(app):
    body = app.test_client().get("/about").get_data(as_text=True)

    assert "krakenimages" in body
    assert "Unsplash" in body
