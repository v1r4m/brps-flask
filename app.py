from flask import Flask, jsonify, request, render_template
import requests
import os
import random
import time
from dotenv import load_dotenv

load_dotenv()

PLAYLIST_ID = os.getenv("PLAYLIST_ID")

app = Flask(__name__, template_folder="templates")

# SoundCloud API 설정
CLIENT_ID = os.getenv("CLIENT_ID")
AUTH = os.getenv("AUTH")

def get_shuffled_tracks(playlist_id):
    url = f"https://api-v2.soundcloud.com/playlists/{playlist_id}?client_id={CLIENT_ID}"
    headers = {
        'Authorization': AUTH,
    }
    response = requests.get(url, headers=headers)
    print(response.text)
    if response.status_code != 200:
        #retry 10 times
        for i in range(10):
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                break
            time.sleep(1)
        else:
            return None

    data = response.json()
    tracks = data.get("tracks", [])
    
    if not tracks:
        return None

    random.shuffle(tracks)
    return tracks

@app.route('/')
def home():
    return render_template('index.html', playlist_id=PLAYLIST_ID)  # templates 폴더에서 index.html을 찾음

@app.route('/playlist/<playlist_id>', methods=['GET'])
def get_playlist(playlist_id):
    tracks = get_shuffled_tracks(playlist_id)
    if tracks is None:
        return jsonify({"error": "Failed to fetch playlist"}), 500
    return jsonify(tracks)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

