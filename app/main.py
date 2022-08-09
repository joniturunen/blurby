from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import hashlib, time, logging, threading, sys, bleach, os

# Define version and author
__version__ = '0.1.7.1'
__author__ = 'Joni Turunen'

# Read db_file from ENV variable
db_file = os.getenv('BLURBY_DB_FILE', '/blurby/data/sqlite.db')
ttl_hours = int(os.getenv('BLURBY_TTL_HOURS', '48'))
threads = int(os.getenv('BLURBY_THREADS', '8'))
host_ipaddr = os.getenv('BLURBY_HOST_IP', '0.0.0.0')

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
    time_stamp = db.Column(db.DateTime, default=datetime.now)
    # Static method that automatically returns time_stamp value plus ttl.
    @staticmethod
    def keep_until():
        return datetime.now() + ttl
    keep_until = db.Column(db.DateTime, default=keep_until)
    creator = db.Column(db.String(64), nullable=False)
    event_history = db.Column(db.Text)

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
        url = request.headers.get('Origin') + '/'
        salty_data = posted_data + str(time.time())
        sha = (hashlib.sha256(salty_data.encode()))
        sha_link=sha.hexdigest()
        creator = request.headers.get('username') if request.headers.get('username') else 'anonymous'
        new_data = Data(data=posted_data, sha_link=sha_link, creator=creator)
        try:
            db.session.add(new_data)
            db.session.commit()
            logger.info(f'{request.headers.get("username")} submitted a secret') if request.headers.get("username") else logger.info(f'Anonymous submitted a secret')
            return render_template('link.html', username=request.headers.get('username') if request.headers.get('username') else 'anonymous', sha_link=sha_link, url=url)
        except:
            return render_template('msg.html', username=request.headers.get('username') if request.headers.get('username') else 'anonymous', msg_title='⚠ There was an error!', msg='There was a problem connecting the database')
    else:
        logger.info(f'{request.headers.get("username")} requested the default page') if request.headers.get("username") else logger.info(f'Anonymous requested the default page')
        return render_template('main.html', username=request.headers.get('username') if request.headers.get('username') else 'anonymous')


@app.route('/link/<string:sha_link>')
def read(sha_link):
    data = Data.query.get_or_404(sha_link)
    logger.info(f'{request.headers.get("username")} requested a sha link') if request.headers.get("username") else logger.info(f'Anonymous requested a sha link')
    return render_template('read_link.html', username=request.headers.get('username') if request.headers.get('username') else 'anonymous', retrieved_message=data.data, time=data.time_stamp, sha_link=data.sha_link, ttl=data.keep_until, creator=data.creator, event_history=data.event_history)

@app.route('/delete/<string:sha_link>')
def delete(sha_link):
    data_to_delete = Data.query.get_or_404(sha_link)
    logger.info(f'{request.headers.get("username")} deleted a sha link') if request.headers.get("username") else logger.info(f'Anonymous deleted a sha link')
    try:
        db.session.delete(data_to_delete)
        db.session.commit()
        return render_template('msg.html', username=request.headers.get('username') if request.headers.get('username') else 'anonymous', msg_title='👌 Message succesfully deleted!', msg='You can create a new secret!')
    except:
        return render_template('msg.html', username=request.headers.get('username') if request.headers.get('username') else 'anonymous', msg_titl='⚠ There was an error!', msg='Message was not deleted, maybe some one deleted it before you?')

@app.route('/find', methods=['POST', 'GET'])
def find():
    logger.info(f'{request.headers.get("username")} requested to find a secret') if request.headers.get("username") else logger.info(f'Anonymous requested to find a secret')
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
                return render_template('msg.html', username=request.headers.get('username') if request.headers.get('username') else 'anonymous', msg_title='⚠ Invalid link!', msg='The link you entered is not valid, please try again.')
        else:
            # Error message since the sha is not valid or not found
            return render_template('msg.html', username=request.headers.get('username') if request.headers.get('username') else 'anonymous', msg_title='⚠ There was an error!', msg='Check your SHA link and try again!')
    elif request.method == 'GET':
        return render_template('find.html', username=request.headers.get('username') if request.headers.get('username') else 'anonymous')

# Render About page
@app.route('/about')
def about():
    logger.info(f'{request.headers.get("username")} requested the about page') if request.headers.get("username") else logger.info(f'Anonymous requested the about page')
    return render_template('about.html', username=request.headers.get('username') if request.headers.get('username') else 'anonymous', ttl=ttl, version=__version__, author=__author__, db_conf=str(app.config['SQLALCHEMY_DATABASE_URI']), request_headers=request.headers)

# Function to check preconditions for database file creation
def check_preconditions():
    # Check if database file exists
    logger.info(f'Checking if database file {db_file} exists...')
    # Check if filepath is valid path
    if not os.path.isdir(os.path.dirname(db_file)):
        logger.error(f'{db_file} is not a valid path!')
        sys.exit(1)
    # Check if db_file variable includes a file extension at the end
    if not db_file.endswith('.db'):
        logger.error(f'{db_file} is not a valid database file!')
        sys.exit(1)
    if not os.path.isfile(db_file):
        # Folder exists and path valid but file not found
        # Try to create the database if failed log error and exit
        logger.info(f'Database file {db_file} not found, trying to create it...')
        try:
            logger.info(f'Create the DB file {db_file}!')
            db.create_all()
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

if __name__ == "__main__":
    # Echo the start of program to logger in color
    logger.info(f'\033[1;32m{"-"*30}\033[0m')
    logger.info(f'\033[1m\033[1;32mStarting Blurby v{__version__}...\033[0m')
    logger.info(f'\033[1;32m{"-"*30}\033[0m')
    # Call check_preconditions function to check if database file exists
    check_preconditions()
    # Start clean_up crew process in background
    cc = CleanUpCrew()
    # If commandline argument --debug is used, run the app in debug mode
    if len(sys.argv) > 1 and sys.argv[1] == '--debug':
        # deepcode ignore RunWithDebugTrue: <please specify a reason of ignoring this>
        app.run(host=host_ipaddr, port=5000, debug=True, threaded=True)
    # Else run the app in production mode
    else:
        from waitress import serve
        serve(app, host=host_ipaddr, port=8080, threads=threads)

    