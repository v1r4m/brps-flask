# brps-flask
![Static Badge](https://img.shields.io/badge/python-v3.9-blue)
![Static Badge](https://img.shields.io/badge/flask-v3.1-blue)
![Static Badge](https://img.shields.io/badge/dotenv-v0.9-blue)
![Static Badge](https://img.shields.io/badge/requests-v2.32-blue)
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
* It will be served on `localhost:5001`.