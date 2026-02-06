# -*- coding: utf-8 -*-
from flask import Flask, jsonify, request, render_template, Response, stream_with_context, send_from_directory
import requests
import os
import random
import time
import m3u8
import subprocess
import tempfile
import shutil

from dotenv import load_dotenv

load_dotenv()

PLAYLIST_ID = os.getenv("PLAYLIST_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
AUTH = os.getenv("AUTH")

app = Flask(__name__, template_folder="templates", static_folder="static")

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

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/')
def home():
    return render_template('index.html', playlist_id=PLAYLIST_ID)

@app.route('/track/<track_id>', methods=['GET'])
def get_track_title(track_id):
    """ track id로 title만 반환하는 API """
    track_url = f"https://api-v2.soundcloud.com/tracks/{track_id}?client_id={CLIENT_ID}"
    headers = {'Authorization': AUTH}
    for i in range(10):
        time.sleep(1)
        track_response = requests.get(track_url, headers=headers)
        if track_response.status_code == 200:
            break
    else:
        print(f"❌ 트랙 정보 가져오기 실패: {track_response.text}")
        return jsonify({"error": "Failed to fetch track metadata"}), 500

    track_data = track_response.json()
    return jsonify({
        "title": track_data.get("title", "Unknown Title"),
        "artist": track_data.get("user", {}).get("username", "Unknown Artist"),
        "artwork_url": track_data.get("artwork_url", ""),
        "duration": track_data.get("duration", 0) / 1000,  # Duration in seconds
        "playback_count": track_data.get("playback_count", 0),
        "likes_count": track_data.get("likes_count", 0)
    })

@app.route('/playlist/<playlist_id>', methods=['GET'])
def get_playlist(playlist_id):
    tracks = get_shuffled_tracks(playlist_id)
    if tracks is None:
        return jsonify({"error": "Failed to fetch playlist"}), 500
    return jsonify(tracks)

@app.route('/stream/<track_id>', methods=['GET'])
def stream_track(track_id):
    """ SoundCloud V2 API를 사용해 MP3 스트리밍 URL 가져오기 """
    print(f"🎵 스트리밍 요청: track_id={track_id}")
    track_url = f"https://api-v2.soundcloud.com/tracks/{track_id}?client_id={CLIENT_ID}"
    headers = {'Authorization': AUTH}

    track_response = requests.get(track_url, headers=headers)
    if track_response.status_code != 200:
        print(f"⚠️ 첫 번째 시도 실패: {track_response.status_code}")
        for i in range(10):
            time.sleep(1)
            track_response = requests.get(track_url, headers=headers)
            if track_response.status_code == 200:
                print(f"✅ {i+1}번째 재시도 성공")
                break
        else:
            print(f"❌ 트랙 정보 가져오기 실패: status={track_response.status_code}, response={track_response.text}")
            return jsonify({"error": "Failed to fetch track metadata", "status_code": track_response.status_code}), 500

    track_data = track_response.json()
    print(f"📝 트랙 제목: {track_data.get('title', 'Unknown')}")
    transcodings = track_data.get("media", {}).get("transcodings", [])

    if not transcodings:
        print(f"❌ 트랜스코딩 없음: track_id={track_id}")
        return jsonify({"error": "No transcodings found"}), 500     

    # ✅ MP3 또는 progressive 포맷 우선 선택
    progressive_transcoding = None
    hls_transcoding = None
    
    for t in transcodings:
        format_protocol = t.get('format', {}).get('protocol', '')
        print(f"  - 포맷: {format_protocol}, URL: {t.get('url', 'N/A')[:50]}...")
        if format_protocol == 'progressive':
            progressive_transcoding = t
            break
        elif format_protocol == 'hls' and not hls_transcoding:
            hls_transcoding = t
    
    # progressive 우선, 없으면 hls 사용
    selected_transcoding = progressive_transcoding or hls_transcoding or transcodings[0]
    transcoding_url = selected_transcoding['url']
    print(f"✅ 선택된 포맷: {selected_transcoding.get('format', {}).get('protocol', 'unknown')}")
    transcoding_response = requests.get(f"{transcoding_url}?client_id={CLIENT_ID}", headers=headers)

    if transcoding_response.status_code != 200:
        print(f"⚠️ 트랜스코딩 URL 첫 번째 시도 실패: {transcoding_response.status_code}")
        for i in range(10):
            time.sleep(1)
            transcoding_response = requests.get(f"{transcoding_url}?client_id={CLIENT_ID}", headers=headers)
            if transcoding_response.status_code == 200:
                print(f"✅ 트랜스코딩 URL {i+1}번째 재시도 성공")
                break
        else:
            print(f"❌ 트랜스코딩 URL 가져오기 실패: status={transcoding_response.status_code}, response={transcoding_response.text}")
            return jsonify({"error": "Failed to fetch transcoding URL", "status_code": transcoding_response.status_code}), 500

    transcoding_data = transcoding_response.json()
    stream_url = transcoding_data.get('url')  # MP3 또는 HLS URL
    
    if not stream_url:
        print(f"❌ 스트림 URL 없음: {transcoding_data}")
        return jsonify({"error": "No stream URL found"}), 500

    print(f"✅ 스트리밍 URL: {stream_url[:100]}...")
    
    # Progressive 포맷인 경우 직접 스트리밍 (Content-Length 포함)
    if selected_transcoding.get('format', {}).get('protocol') == 'progressive':
        print(f"🎵 Progressive 스트리밍")
        upstream = requests.get(stream_url, headers=headers, stream=True)
        resp_headers = {'Content-Type': 'audio/mpeg'}
        if 'Content-Length' in upstream.headers:
            resp_headers['Content-Length'] = upstream.headers['Content-Length']
            resp_headers['Accept-Ranges'] = 'none'
        return Response(
            upstream.iter_content(chunk_size=4096),
            headers=resp_headers
        )
    
    # HLS 포맷인 경우 ffmpeg로 MP3 변환
    hls_url = stream_url
    print(f"🎵 HLS 스트리밍 - ffmpeg로 MP3 변환")

    def generate_mp3_from_hls():
        """ffmpeg를 사용해 HLS 스트림을 MP3로 변환하여 스트리밍"""
        try:
            # ffmpeg로 HLS URL에서 직접 MP3로 변환
            process = subprocess.Popen(
                [
                    'ffmpeg',
                    '-i', hls_url,           # HLS URL 직접 입력
                    '-vn',                    # 비디오 제외
                    '-acodec', 'libmp3lame',  # MP3 인코딩
                    '-ab', '128k',            # 비트레이트
                    '-f', 'mp3',              # 출력 포맷
                    '-'                       # stdout으로 출력
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=4096
            )

            # stdout에서 청크 단위로 읽어서 yield
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                yield chunk

            process.wait()
            if process.returncode != 0:
                stderr = process.stderr.read().decode('utf-8', errors='ignore')
                print(f"⚠️ ffmpeg 경고/에러: {stderr[:500]}")

        except FileNotFoundError:
            print(f"❌ ffmpeg가 설치되어 있지 않습니다. 폴백으로 TS 직접 스트리밍 시도")
            # ffmpeg 없으면 기존 방식으로 폴백 (문제 있을 수 있음)
            hls_response = requests.get(hls_url, headers=headers)
            if hls_response.status_code == 200:
                playlist = m3u8.loads(hls_response.text)
                ts_urls = [segment.uri for segment in playlist.segments]
                for ts_url in ts_urls:
                    try:
                        ts_response = requests.get(ts_url, headers=headers, stream=True, timeout=10)
                        if ts_response.status_code == 200:
                            for chunk in ts_response.iter_content(chunk_size=4096):
                                if chunk:
                                    yield chunk
                    except Exception as e:
                        print(f"❌ TS 세그먼트 예외: {e}")
        except Exception as e:
            print(f"❌ ffmpeg 실행 예외: {e}")

    return Response(stream_with_context(generate_mp3_from_hls()), content_type="audio/mpeg")



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
