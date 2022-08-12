from main import db

def setup_database():
    try:
        db.create_all()
        print('Database created!')
    except:
        print(f'Can\'t create database, maybe it already exists or path is not writable?')


if __name__ == "__main__":
    setup_database()