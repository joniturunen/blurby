from flask import Flask, render_template, request, redirect
from flask.templating import _render
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime as dt
import time
from urllib.parse import urlparse
import hashlib

from werkzeug.utils import redirect

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../data/sqlite.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Data(db.Model):
    sha_link = db.Column(db.String(64), primary_key=True)
    data = db.Column(db.Text, nullable=False)
    time_stamp = db.Column(db.DateTime, default=dt.now)

    def __repr__(self):
        return '<Data %r>' % self.sha_link


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
    return render_template('read_link.html', retrieved_message=data.data, time=data.time_stamp, sha_link=data.sha_link)


@app.route('/delete/<string:sha_link>')
def delete(sha_link):
    data_to_delete = Data.query.get_or_404(sha_link)

    try:
        db.session.delete(data_to_delete)
        db.session.commit()
        return render_template('msg.html', msg_title='👌 Message succesfully deleted!', msg='You can create a new secret!')
    except:
        return render_template('msg.html', msg_titl='⚠ There was an error!', msg='Message was not deleted, maybe some one deleted it before you?')

if __name__ == "__main__":
    app.run(debug=True)
