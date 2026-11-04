# Blurby

Simple little Flask app that takes pastebin-like of data from user and stores it in a sqlite file.

- **Links that expire.** Each secret gets a random link and is deleted when its time is up. The creator chooses how long to keep it, up to a limit the admin sets.
- **Burn after reading.** The reader can burn a secret once they've read it. Its link then shows a read receipt: when it was burnt, and by whom.
- **Read-once secrets.** The creator can make a secret burn as it's revealed. Opening the link only shows a notice, so chat link previews and email scanners can't use up the one view; the secret is shown when the reader clicks Reveal.
- **Copy buttons** for the link and the secret.
- **Light and dark mode.** Pages follow your system's setting; the switch in the menu picks the other mode, and your browser remembers the choice.
- **Private by design.** Logs never contain secrets or links, pages aren't cached and load nothing from other sites, and a strict Content-Security-Policy is in place.

## How-To

Install the dependencies with [uv](https://docs.astral.sh/uv/) (`uv sync`), then run Blurby with a database file in the repo's `data/` folder (gitignored; the file is created on first start):

```bash
BLURBY_DB_FILE=./data/sqlite.db uv run blurby
```

and head out to your browser with the url [http://127.0.0.1:8080](http://127.0.0.1:8080). Without `BLURBY_DB_FILE`, Blurby uses the Docker path `/blurby/data/sqlite.db` and won't start when `/blurby/data` doesn't exist.

Add `--debug` for the Flask debug server on [http://127.0.0.1:5000](http://127.0.0.1:5000). On macOS, turn off the AirPlay Receiver first (System Settings → General → AirDrop & Handoff): it uses port 5000, and the debug server exits with "Address already in use".

Check the Using Docker section for more info.

### Parameters

Configuration is done via environment variables. The following are the available parameters:

    - `BLURBY_DB_FILE`: Path to the sqlite database. (defaults to `/blurby/data/sqlite.db`)
    - `BLURBY_HOST_IP`: Host to bind the server to. (defaults to `0.0.0.0`)
    - `BLURBY_TTL_HOURS`: How long to keep a secret, unless its creator chooses otherwise. (defaults to `48`)
    - `BLURBY_MAX_TTL_HOURS`: The longest TTL a creator can choose: 1 hour, 1 day, 2 days, 5 days, 1 week or 2 weeks, up to this limit. (defaults to `BLURBY_TTL_HOURS`, so creators can only choose shorter TTLs until you raise it; e.g. `336` allows up to 2 weeks)
    - `BLURBY_THREADS`: Number of threads to use for processing. (defaults to `8`)
    - `BLURBY_CLEANUP_INTERVAL`: Seconds between passes that delete expired pastes. (defaults to `60`)

`uv run blurby` serves the app with waitress on port `8080`. When run from the command line, the following *additional* parameters are available:

    - `--debug`: Run the Flask debug server on port `5000` instead. (On macOS, the AirPlay Receiver may already be using port 5000.)


### Initializing database

The application now checks if a `BLURBY_DB_FILE` environment variable is set. If it is, it uses that as a DB file. If the file is missing but the path is valid it creates the db file.

Manually: To create a blank Sqlite DB for the app use the `uv run python -m blurby.setup_database` command.

On every start, Blurby also adds any columns that a database from an earlier version lacks. The schema only grows, so an earlier version still runs on the upgraded database.

## Using docker

To use docker simply run the container with prefered volume maps. The container serves on port `8080` and keeps the SQLite database in `/blurby/data`.

ex. 
`docker container run -p 8080:8080 -v /your/path/data:/blurby/data joniturunen/blurby`

The database file is created on first start if it's missing (see [Initializing database](#initializing-database)). The mounted folder must be writable by the container's `appuser` (UID 5678). Logs go to the container's stdout (`docker logs`).

## Todo

- Add view history to entries

## Credits

Styled with [Pico CSS](https://picocss.com) (MIT license), vendored in `src/blurby/static/css/` with its license.

Photo by [krakenimages](https://unsplash.com/@krakenimages) on [Unsplash](https://unsplash.com/photos/8RXmc8pLX_I).

## Screenshot

![Screenshot of Blurby](/blurby.jpg?raw=true "Screenshot of retrieved message")
