# -*- coding: utf-8 -*-
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
    
    # Progressive 포맷인 경우 직접 리다이렉트
    if selected_transcoding.get('format', {}).get('protocol') == 'progressive':
        print(f"🎵 Progressive 스트리밍으로 리다이렉트")
        return Response(
            requests.get(stream_url, headers=headers, stream=True).iter_content(chunk_size=4096),
            content_type="audio/mpeg"
        )
    
    # HLS 포맷인 경우 기존 로직 사용
    hls_url = stream_url

    # ✅ `.m3u8` 파일 다운로드
    hls_response = requests.get(hls_url, headers=headers)
    if hls_response.status_code != 200:
        print(f"❌ M3U8 다운로드 실패: status={hls_response.status_code}")
        return jsonify({"error": "Failed to fetch .m3u8 playlist", "status_code": hls_response.status_code}), 500

    # ✅ `.m3u8` 파일 분석
    try:
        playlist = m3u8.loads(hls_response.text)
    except Exception as e:
        print(f"❌ M3U8 파싱 실패: {e}")
        return jsonify({"error": "Failed to parse .m3u8 playlist", "details": str(e)}), 500

    # ✅ 모든 TS 세그먼트 가져오기
    ts_urls = [segment.uri for segment in playlist.segments]

    if not ts_urls:
        print(f"❌ TS 세그먼트 없음")
        return jsonify({"error": "No TS segments found in .m3u8 file"}), 500

    print(f"✅ {len(ts_urls)}개의 TS 세그먼트를 찾음")

    def generate():
        """ 모든 TS 세그먼트를 순차적으로 스트리밍 """
        failed_segments = 0
        for idx, ts_url in enumerate(ts_urls, 1):
            try:
                ts_response = requests.get(ts_url, headers=headers, stream=True, timeout=10)
                if ts_response.status_code != 200:
                    print(f"❌ TS 세그먼트 {idx}/{len(ts_urls)} 실패: status={ts_response.status_code}")
                    failed_segments += 1
                    if failed_segments > len(ts_urls) * 0.5:  # 50% 이상 실패시 중단
                        print(f"❌ 너무 많은 세그먼트 실패: {failed_segments}/{len(ts_urls)}")
                        break
                    continue

                for chunk in ts_response.iter_content(chunk_size=4096):
                    if chunk:
                        yield chunk
            except Exception as e:
                print(f"❌ TS 세그먼트 {idx}/{len(ts_urls)} 예외: {e}")
                failed_segments += 1

    return Response(stream_with_context(generate()), content_type="audio/mpeg")  # MP3 오디오 타입으로 변경



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
