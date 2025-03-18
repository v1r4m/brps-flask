from flask import Flask, jsonify, request, render_template, Response, stream_with_context
import requests
import os
import random
import time
import m3u8  

from dotenv import load_dotenv

load_dotenv()

PLAYLIST_ID = os.getenv("PLAYLIST_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
AUTH = os.getenv("AUTH")

app = Flask(__name__, template_folder="templates")

def get_shuffled_tracks(playlist_id):
    """ SoundCloud V2 API를 사용해 플레이리스트 트랙 정보 가져오기 """
    url = f"https://api-v2.soundcloud.com/playlists/{playlist_id}?client_id={CLIENT_ID}"
    headers = {'Authorization': AUTH}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        for i in range(10):
            time.sleep(1)
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                break
        else:
            print(f"❌ 플레이리스트 가져오기 실패: {response.text}")
            return None

    data = response.json()
    tracks = data.get("tracks", [])

    if not tracks:
        return None

    random.shuffle(tracks)
    return tracks

@app.route('/')
def home():
    return render_template('index.html', playlist_id=PLAYLIST_ID)

@app.route('/playlist/<playlist_id>', methods=['GET'])
def get_playlist(playlist_id):
    tracks = get_shuffled_tracks(playlist_id)
    if tracks is None:
        return jsonify({"error": "Failed to fetch playlist"}), 500
    return jsonify(tracks)

@app.route('/stream/<track_id>', methods=['GET'])
def stream_track(track_id):
    """ SoundCloud V2 API를 사용해 MP3 스트리밍 URL 가져오기 """
    track_url = f"https://api-v2.soundcloud.com/tracks/{track_id}?client_id={CLIENT_ID}"
    headers = {'Authorization': AUTH}

    track_response = requests.get(track_url, headers=headers)
    if track_response.status_code != 200:
        for i in range(10):
            time.sleep(1)
            track_response = requests.get(track_url, headers=headers)
            if track_response.status_code == 200:
                break
        else:
            print(f"❌ 트랙 정보 가져오기 실패: {track_response.text}")
            return jsonify({"error": "Failed to fetch track metadata"}), 500

    track_data = track_response.json()
    transcodings = track_data.get("media", {}).get("transcodings", [])

    if not transcodings:
        return jsonify({"error": "No transcodings found"}), 500     

    # ✅ MP3 스트리밍 URL 가져오기
    transcoding_url = transcodings[0]['url']
    transcoding_response = requests.get(f"{transcoding_url}?client_id={CLIENT_ID}", headers=headers)

    if transcoding_response.status_code != 200:
        for i in range(10):
            time.sleep(1)
            transcoding_response = requests.get(f"{transcoding_url}?client_id={CLIENT_ID}", headers=headers)
            if transcoding_response.status_code == 200:
                break
        else:
            print(f"❌ 트랜스코딩 URL 가져오기 실패: {transcoding_response.text}")
            return jsonify({"error": "Failed to fetch transcoding URL"}), 500

    transcoding_data = transcoding_response.json()
    hls_url = transcoding_data['url']  # ✅ `.m3u8` 파일 URL

    print(f"✅ HLS 스트리밍 리스트 URL: {hls_url}")

    # ✅ `.m3u8` 파일 다운로드
    hls_response = requests.get(hls_url, headers=headers)
    if hls_response.status_code != 200:
        return jsonify({"error": "Failed to fetch .m3u8 playlist"}), 500

    # ✅ `.m3u8` 파일 분석
    playlist = m3u8.loads(hls_response.text)

    # ✅ 모든 TS 세그먼트 가져오기
    ts_urls = [segment.uri for segment in playlist.segments]

    if not ts_urls:
        return jsonify({"error": "No TS segments found in .m3u8 file"}), 500

    print(f"✅ {len(ts_urls)}개의 TS 세그먼트를 찾음")

    def generate():
        """ 모든 TS 세그먼트를 순차적으로 스트리밍 """
        for ts_url in ts_urls:
            ts_response = requests.get(ts_url, headers=headers, stream=True)
            if ts_response.status_code != 200:
                print(f"❌ TS 세그먼트 가져오기 실패: {ts_url}")
                continue

            for chunk in ts_response.iter_content(chunk_size=4096):
                yield chunk

    return Response(stream_with_context(generate()), content_type="video/MP2T")  # TS 파일의 MIME 타입


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
