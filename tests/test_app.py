import unittest
from unittest import mock

from sqlalchemy.exc import SQLAlchemyError

from blurby import __version__, create_app
from blurby.models import Data, db


class TestBase(unittest.TestCase):
    def setUp(self):
        self.flask_app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            }
        )
        self.app = self.flask_app.test_client()
        self.app_context = self.flask_app.app_context()
        self.app_context.push()
        db.create_all()
        self.sample_data = "Lorem ipsum dolor sit amet, consectetur adipiscing elit.\nDonec euismod, nisi eu consectetur consectetur, nisi nisi\n        consectetur nisi, euismod nisi nisi euismod nisi."
        self.sample_sha = (
            "5a96661c68776a977458f2462b24f3f3a6b5dcf4c75f0bdc19c2914812872e7b"
        )
        self.sample_creator = "Perus Käyttäjä"
        d = Data(
            data=self.sample_data, sha_link=self.sample_sha, creator=self.sample_creator
        )
        db.session.add(d)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        # Each test builds its own engine; close its SQLite connection explicitly.
        db.engine.dispose()
        self.app_context.pop()

    def test_db_entry_is_created(self):
        self.assertEqual(Data.query.count(), 1)
        self.assertEqual(Data.query.first().data, self.sample_data)
        self.assertEqual(Data.query.first().sha_link, self.sample_sha)
        self.assertEqual(Data.query.first().creator, self.sample_creator)
        self.assertEqual(Data.query.first().blurby_version, __version__)

    def test_default_page_accessible(self):
        response = self.app.get("/")
        self.assertEqual(response.status_code, 200)

    def test_about_page_accessible(self):
        response = self.app.get("/about")
        self.assertEqual(response.status_code, 200)

    def test_find_page_accessible(self):
        response = self.app.get("/find")
        self.assertEqual(response.status_code, 200)

    def test_unknown_page_returns_404(self):
        response = self.app.get("/no-such-page")
        self.assertEqual(response.status_code, 404)

    def test_delete_without_a_sha_returns_404(self):
        response = self.app.get("/delete")
        self.assertEqual(response.status_code, 404)

    def test_viewing_a_shalink(self):
        response = self.app.get(
            "/link/5a96661c68776a977458f2462b24f3f3a6b5dcf4c75f0bdc19c2914812872e7b"
        )
        self.assertEqual(response.status_code, 200)

    def test_deletion_of_shalink(self):
        response = self.app.get(
            "/delete/5a96661c68776a977458f2462b24f3f3a6b5dcf4c75f0bdc19c2914812872e7b"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Data.query.count(), 0)

    ORIGIN = {"Origin": "http://blurby.test"}

    def test_posting_a_secret_stores_it_and_shows_its_link(self):
        response = self.app.post("/", data={"data": "top secret"}, headers=self.ORIGIN)
        self.assertEqual(response.status_code, 200)
        stored = Data.query.filter_by(data="top secret").one()
        self.assertRegex(stored.sha_link, r"^[0-9a-f]{64}$")
        self.assertEqual(stored.creator, "anonymous")
        self.assertIn(
            f"http://blurby.test/link/{stored.sha_link}",
            response.get_data(as_text=True),
        )

    def test_posting_a_secret_without_an_origin_header_links_to_this_host(self):
        # Browsers send Origin with form posts, but curl and scripts don't.
        response = self.app.post("/", data={"data": "no origin"})
        self.assertEqual(response.status_code, 200)
        sha = Data.query.filter_by(data="no origin").one().sha_link
        self.assertIn(f"http://localhost/link/{sha}", response.get_data(as_text=True))

    def test_posting_a_secret_records_the_username_header_as_creator(self):
        response = self.app.post(
            "/",
            data={"data": "from alice"},
            headers={**self.ORIGIN, "username": "alice"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Data.query.filter_by(data="from alice").one().creator, "alice")

    def test_a_database_error_while_saving_shows_an_error_page(self):
        failing_commit = mock.patch.object(
            db.session, "commit", side_effect=SQLAlchemyError("disk I/O error")
        )
        with failing_commit, self.assertLogs("blurby.views", "ERROR"):
            response = self.app.post("/", data={"data": "lost"}, headers=self.ORIGIN)
        body = response.get_data(as_text=True)
        self.assertIn("There was a problem connecting the database", body)
        self.assertNotIn("/link/", body)

    def test_deleting_an_unknown_secret_returns_404_with_an_error_title(self):
        response = self.app.get("/delete/" + "0" * 64)
        self.assertEqual(response.status_code, 404)
        body = response.get_data(as_text=True)
        self.assertIn("There was an error!", body)
        self.assertIn("Message was not found", body)

    def test_viewing_a_secret_shows_its_content_and_creator(self):
        body = self.app.get(f"/link/{self.sample_sha}").get_data(as_text=True)
        self.assertIn("Lorem ipsum dolor sit amet", body)
        self.assertIn(self.sample_creator, body)

    def test_secret_content_is_html_escaped(self):
        payload = "<script>alert(1)</script>"
        self.app.post("/", data={"data": payload}, headers=self.ORIGIN)
        sha = Data.query.filter_by(data=payload).one().sha_link
        body = self.app.get(f"/link/{sha}").get_data(as_text=True)
        self.assertNotIn(payload, body)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)

    def test_viewing_an_unknown_link_returns_404(self):
        response = self.app.get("/link/" + "0" * 64)
        self.assertEqual(response.status_code, 404)

    def test_find_redirects_a_valid_sha_to_its_link(self):
        response = self.app.post("/find", data={"sha_link": self.sample_sha})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.headers["Location"].endswith(f"/link/{self.sample_sha}")
        )

    def test_find_rejects_a_non_alphanumeric_sha(self):
        response = self.app.post("/find", data={"sha_link": "../" + "a" * 61})
        self.assertIn("Invalid link", response.get_data(as_text=True))

    def test_find_with_a_wrong_length_sha_returns_404(self):
        response = self.app.post("/find", data={"sha_link": "abc123"})
        self.assertEqual(response.status_code, 404)

    def test_about_page_shows_the_version(self):
        body = self.app.get("/about").get_data(as_text=True)
        self.assertIn(__version__, body)

    def test_pages_greet_the_username_header_or_anonymous(self):
        for path in ("/", "/find", "/about", f"/link/{self.sample_sha}"):
            with self.subTest(path=path):
                anonymous = self.app.get(path).get_data(as_text=True)
                named = self.app.get(path, headers={"username": "alice"})
                self.assertIn("🤫 anonymous", anonymous)
                self.assertIn("🤫 alice", named.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
