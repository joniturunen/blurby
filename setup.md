# Setup.md
Notes about running the dev env.

## Venv
```bash
sudo apt install pip
pip install virtualenv
PATH=$PATH:~/.local/bin
virtualenv env
source env/bin/activate
pip -V #to check that we are in the 'env'
pip install -r requirements.txt
```

## Setting up sqlite

Run `python setup_database.py` from app directory.

Note: Path to blurby's data folder must exists and be writable. By default (if not given as env) is `/blurby/data/sqlite.db`.
