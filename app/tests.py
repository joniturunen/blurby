import unittest, random
from main import app, db, Data, __version__
from flask import current_app

class TestBase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        db.create_all()
        self.sample_data = "Lorem ipsum dolor sit amet, consectetur adipiscing elit.\nDonec euismod, nisi eu consectetur consectetur, nisi nisi\n        consectetur nisi, euismod nisi nisi euismod nisi."
        self.sample_sha = '5a96661c68776a977458f2462b24f3f3a6b5dcf4c75f0bdc19c2914812872e7b'
        self.sample_creator = 'Perus Käyttäjä'
        d = Data(data=self.sample_data, sha_link=self.sample_sha, creator=self.sample_creator)
        db.session.add(d)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
    
    def test_db_entry_is_created(self):
        self.assertEqual(Data.query.count(), 1)
        self.assertEqual(Data.query.first().data, self.sample_data)
        self.assertEqual(Data.query.first().sha_link, self.sample_sha)
        self.assertEqual(Data.query.first().creator, self.sample_creator)
        self.assertEqual(Data.query.first().blurby_version, __version__)
    
    def test_default_page_accessible(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
    
    def test_about_page_accessible(self):
        response = self.app.get('/about')
        self.assertEqual(response.status_code, 200)

    def test_find_page_accessible(self):
        response = self.app.get('/find')
        self.assertEqual(response.status_code, 200)

    def test_random_page_not_accessible(self):
        response = self.app.get('/'+str(random.randint(1, 100)))
        self.assertEqual(response.status_code, 404)
    
    def test_random_link_not_accessible(self):
        response = self.app.get('/'+str(random.randint(1, 100)))
        self.assertEqual(response.status_code, 404)

    def test_delete_page_contains_anonymous(self):
        response = self.app.get('/delete')
        self.assertEqual(response.status_code, 404)

    def test_get_about_page_contains_anonymous(self):
        response = self.app.get('/about')
        self.assertEqual(response.status_code, 200)

    def test_viewing_a_shalink(self):
        response = self.app.get('/link/5a96661c68776a977458f2462b24f3f3a6b5dcf4c75f0bdc19c2914812872e7b')
        self.assertEqual(response.status_code, 200)
    
    def test_deletion_of_shalink(self):
        response = self.app.get('/delete/5a96661c68776a977458f2462b24f3f3a6b5dcf4c75f0bdc19c2914812872e7b')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Data.query.count(), 0)


if __name__ == '__main__':
    unittest.main()