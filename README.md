# Blurby

Simple little Flask app that takes pastebin-like of data from user and stores it in a sqlite file.

## How-To

Just run `python ./app/main.py` and head out to your browser with the url [http://127.0.0.1:5000](http://127.0.0.1:5000).

### Initializing database

The application now checks if a `BLURBY_DB_FILE` environment variable is set. If it is, it uses that as a DB file. If the file is missing but the path is valid it creates the db file.

Manually: To create a blank Sqlite DB for the app use the `python ./app/setup_database.py` command.

## Using docker

To use docker simply run the container with prefered volume maps. 

ex. 
`docker container run -v /some/path/logs:/data/logs -v /your/path/data:/data joniturunen/blurby`

Note the data folder requires a SQLlite database to be created, check [documentation for setting up SQLite](#initializing-database).

## Todo

- Make max string length parameterized
- TTL parameter howto
- Possibility to change TTL by user (selection list)
- Possibility to create logfile entries
- SSO (SAML2) support (read http headers, remote_user info) to log who CRUDs entries
- WSGI installation for containers
- Experiment with redis or some other db

## Credits

Photo by <a href="https://unsplash.com/@krakenimages?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">krakenimages</a> on <a href="https://unsplash.com/s/photos/secret?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Unsplash</a>

Icons: 
- [Font Awesome](http://fontawesome.io)

Other:
- [jQuery](http://jquery.com)
- [Scrollex](github.com/ajlkn/jquery.scrollex)
- [Responsive Tools](github.com/ajlkn/responsive-tools)

Theme:
Massively by HTML5 UP
html5up.net | @ajlkn
Free for personal and commercial use under the [CCA 3.0 license](https://html5up.net/license)

## Screenshot

![Screenshot of Blurby](/blurby.jpg?raw=true "Screenshot of retrieved message")
