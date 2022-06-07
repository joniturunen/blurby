from flask import Flask, render_template, request, redirect
from flask.templating import _render
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from urllib.parse import urlparse
import hashlib, time, logging, threading, sys, bleach, os

# Define version and author
__version__ = '0.1.5'
__author__ = 'Joni Turunen'

# Read db_file from ENV variable
db_file = os.getenv('BLURBY_DB_FILE', '/blurby/data/sqlite.db')
ttl_hours = int(os.getenv('BLURBY_TTL_HOURS', '48'))
threads = int(os.getenv('BLURBY_THREADS', '8'))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_file}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# logging conf
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('./blurby.log'),
        logging.StreamHandler(sys.stdout)]
    )
logger = logging.getLogger(' Blurby ')

# Generate timedelta object from given hours
ttl = timedelta(hours=ttl_hours)

class Data(db.Model):
    sha_link = db.Column(db.String(64), primary_key=True)
    data = db.Column(db.Text, nullable=False)
    time_stamp = db.Column(db.DateTime, default=datetime.now())
    keep_until = db.Column(db.DateTime, default=datetime.now() + ttl)

    def __repr__(self):
        return '<Data %r>' % self.sha_link

class CleanUpCrew():
    # remove data older than 48 hours
    def __init__(self):
        # Define the interval in seconds for the clean_up function
        self.interval = 60
        thread = threading.Thread(target=self.clean_up, args=())
        thread.daemon = True
        thread.start()
    
    def clean_up(self):
        while True:
            logger.info('Checking for old data entries...')
            # if there are entries in the database that are older than 48 hours remove them
            if Data.query.filter(Data.keep_until < datetime.now()).all():
                logger.info(f'Found data entries that are older than {ttl}, deleting...')
                Data.query.filter(Data.keep_until < datetime.now()).delete()
                db.session.commit()
                # write log entry
                logger.info(f'Cleaned up old data entries!')
            time.sleep(self.interval)


@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        posted_data = request.form['data']
        o = urlparse(request.base_url)
        url= o.scheme + '://' + o.netloc + o.path
        salty_data = posted_data + str(time.time())
        sha = (hashlib.sha256(salty_data.encode()))
        sha_link=sha.hexdigest()
        new_data = Data(data=posted_data, sha_link=sha_link)
        try:
            db.session.add(new_data)
            db.session.commit()
            return render_template('link.html', sha_link=sha_link, url=url)
        except:
            return render_template('msg.html', msg_title='⚠ There was an error!', msg='There was a problem connecting the database')
    else:

        return render_template('main.html')


@app.route('/link/<string:sha_link>')
def read(sha_link):
    data = Data.query.get_or_404(sha_link)
    return render_template('read_link.html', retrieved_message=data.data, time=data.time_stamp, sha_link=data.sha_link, ttl=data.keep_until)


@app.route('/delete/<string:sha_link>')
def delete(sha_link):
    data_to_delete = Data.query.get_or_404(sha_link)
    try:
        db.session.delete(data_to_delete)
        db.session.commit()
        return render_template('msg.html', msg_title='👌 Message succesfully deleted!', msg='You can create a new secret!')
    except:
        return render_template('msg.html', msg_titl='⚠ There was an error!', msg='Message was not deleted, maybe some one deleted it before you?')

@app.route('/find', methods=['POST', 'GET'])
def find():
    if request.method == 'POST':        
        sha_link = request.form['sha_link']
        # Check if sha_link is valid and 'secure'
        if len(sha_link) == 64:
            if sha_link.isalnum():
                # Sanitize with bleach
                sha_link = bleach.clean(sha_link)
                # file deepcode ignore OR: sha_link gets cleaned by bleach, fixed 11th of May 2022
                return redirect(f'/link/{sha_link}')
            else:
                return render_template('msg.html', msg_title='⚠ Invalid link!', msg='The link you entered is not valid, please try again.')
        else:
            # Error message since the sha is not valid or not found
            return render_template('msg.html', msg_title='⚠ There was an error!', msg='Check your SHA link and try again!')
    elif request.method == 'GET':
        return render_template('find.html')

# Render About page
@app.route('/about')
def about():
    return render_template('about.html', ttl=ttl, version=__version__, author=__author__, db_conf=str(app.config['SQLALCHEMY_DATABASE_URI']))

# Function to check preconditions for database file creation
def check_preconditions():
    # Check if database file exists
    logger.info(f'Checking if database file {db_file} exists...')
    # Check if filepath is valid path
    if not os.path.isdir(os.path.dirname(db_file)):
        logger.error(f'{db_file} is not a valid path!')
        sys.exit(1)
    # Check if db_file variable includes a filename at the end
    if not db_file.endswith('.db'):
        logger.error(f'{db_file} is not a valid database file!')
        sys.exit(1)
    if not os.path.isfile(db_file):
        # Folder exists and path valid but file not found
        # Try to create the database if failed log error and exit
        logger.info(f'Database file {db_file} not found, trying to create it...')
        try:
            db.create_all()
            logger.info(f'Database file {db_file} created!')
        except:
            logger.error(f"Could not create database URI {app.config['SQLALCHEMY_DATABASE_URI']}")
            logger.warning(f'Please check if the database file {db_file} is writable!')
            sys.exit(1)
    else:
        # Write log entry
        logger.info(f"Database file: {db_file} found!")
    logger.info(f'\033[1mPreconditions check passed with following env values\033[0m:\033[1;32m \
                \n{" "*42}- BLURBY_TTL_HOURS = {ttl_hours} \
                \n{" "*42}- BLURBY_THREADS = {threads} \
                \n{" "*42}- BLURBY_DB_FILE = {db_file} \
                \033[0m')

# Render About page
@app.route('/about')
def about():
    return render_template('about.html', ttl=ttl, version=__version__, author=__author__, db_conf=str(app.config['SQLALCHEMY_DATABASE_URI']))

if __name__ == "__main__":
    # Echo the start of program to logger in color
    logger.info(f'\033[1;32m{"-"*30}\033[0m')
    logger.info(f'\033[1m\033[1;32mStarting Blurby v{__version__}...\033[0m')
    logger.info(f'\033[1;32m{"-"*30}\033[0m')
    # Call check_preconditions function to check if database file exists
    check_preconditions()
    # Start clean_up crew process in background
    cc = CleanUpCrew()
    # Run this Flask App in production mode
    from waitress import serve
    serve(app, host='0.0.0.0', port=8080, threads=threads)
