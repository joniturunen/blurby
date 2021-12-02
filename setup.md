```bash
sudo apt install pip
pip install virtualenv
PATH=$PATH:~/.local/bin
virtualenv env
source env/bin/activate
pip -V #to check that we are in the 'env'
pip install flask flask-sqlalchemy
```