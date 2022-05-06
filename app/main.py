from statistics import multimode
from flask import Flask, render_template, request, redirect
from flask.templating import _render
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from urllib.parse import urlparse
import hashlib, time, logging, threading, sys

# Define version and author
__version__ = '0.1.1'
__author__ = 'Joni Turunen'

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../data/sqlite.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# logging conf
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('./blurby.log'),
        logging.StreamHandler(sys.stdout)]
    )
logger = logging.getLogger(' Blurby ')
# How long to keep data in the database
ttl = timedelta(hours=48)

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
        return redirect(f'/link/{sha_link}')
    elif request.method == 'GET':
        return render_template('find.html')


# Render About page
@app.route('/about')
def about():
    return render_template('about.html', ttl=ttl, version=__version__, author=__author__, db_conf=str(app.config['SQLALCHEMY_DATABASE_URI']))



if __name__ == "__main__":
    # start clean_up crew process in background
    cc = CleanUpCrew()
    app.run(debug=False)

