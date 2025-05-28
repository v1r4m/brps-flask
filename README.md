# brps-flask
![Static Badge](https://img.shields.io/badge/python-v3.9-blue)
![Static Badge](https://img.shields.io/badge/flask-v3.1-blue)
![Static Badge](https://img.shields.io/badge/dotenv-v0.9-blue)
![Static Badge](https://img.shields.io/badge/requests-v2.32-blue)
* LIVE : https://music.viram.dev
* SoundCloud's shuffle function on desktop stopped working properly, only shuffling a limited number of tracks. This repository is a playlist shuffler to fix that issue. Check out [this issue on reddit](https://www.reddit.com/r/trap/comments/6u6ort/any_way_to_actually_shuffle_your_soundcloud/).
* This is a refactored version of [v1r4m/big-random-playlist-for-soundcloud](https://github.com/v1r4m/big-random-playlist-for-soundcloud) from `next.js` to `flask`.
## quick start
### on Windows (CMD / PowerShell)
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
### on Mac / Linux (bash/zsh)
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### on docker
```
docker build -t brps-flask .
docker run -p 8080:8080 brps-flask
```

## .env
```
PLAYLIST_ID=YOUR_PLAYLIST_ID
CLEINT_ID=YOUR_CLIENT_ID
AUTH=YOUR_AUTH
```
* I will soon add a page that can edit env value on site.
* First, go to the playlist page on soundcloud. (in my case, it's https://soundcloud.com/v1r4m/sets/beat)
* open F12(dev tool)
* filter `likers?client_id`
* you'll see something like
```
curl 'https://api-v2.soundcloud.com/playlists/{{it's your playlist id}}/likers?client_id={{it's your client id}}&limit=9&offset=0&linked_partitioning=1&app_version=1748345262&app_locale=en' \
  -H 'Authorization: {{it's your auth, plz contain OAuth symbol}}' 
```