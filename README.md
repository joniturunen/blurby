# Blurby

Simple little Flask app that takes pastebin-like of data from user and stores it in a sqlite file.


## How-To

Just run `python ./app/main.py` and head out to your browser with the url [http://127.0.0.1:5000](http://127.0.0.1:5000).

Check the Using Docker section for more info.

### Parameters

Configuration is done via environment variables. The following are the available parameters:

    - `BLURBY_DB_FILE`: Path to the sqlite database. (defaults to `/blurby/data/sqlite.db`)
    - `BLURBY_HOST_IP`: Host to bind the server to. (defaults to `0.0.0.0`)
    - `BLURBY_TTL_HOURS`: How long to keep a paste in the database. (defaults to `48`)
    - `BLURBY_THREADS`: Number of threads to use for processing. (defaults to `8`)

When run from the command line, the following *additional* parameters are available:

    - `--debug`: Run in debug mode.


### Initializing database

The application now checks if a `BLURBY_DB_FILE` environment variable is set. If it is, it uses that as a DB file. If the file is missing but the path is valid it creates the db file.

Manually: To create a blank Sqlite DB for the app use the `python ./app/setup_database.py` command.

## Using docker

To use docker simply run the container with prefered volume maps. 

ex. 
`docker container run -v /some/path/logs:/data/logs -v /your/path/data:/data joniturunen/blurby`

Note the data folder requires a SQLlite database to be created, check [documentation for setting up SQLite](#initializing-database).

## Todo

- Possibility to create logfile entries
- Better error handling
- Add view history to entries
- Better structure for the app (create_app())
- Context upgrade to g or app_ctx

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
