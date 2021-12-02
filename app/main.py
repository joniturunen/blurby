from flask import Flask, render_template

app = Flask(__name__)

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
