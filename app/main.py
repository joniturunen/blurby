from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime as dt

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../data/sqlite.db'
db = SQLAlchemy(app)

class Data(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blob = db.Column(db.String(256), nullable=False)
    time_stamp = db.Column(db.DateTime, default=dt.now)

    def __repr__(self):
        return '<Data %r>' % self.id


@app.route('/')
def index():
    return render_template('main.html')

@app.route('/post')
def post():
    return render_template('post.html')

@app.route('/list')
def list():
    return render_template('list.html')


if __name__ == "__main__":
    app.run(debug=True)
