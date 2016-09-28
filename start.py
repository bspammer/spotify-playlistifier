import requests
import json
import time
import sys

address = "https://accounts.spotify.com/authorize?client_id=214c5826a3024e999ffefd76cdac28c4&response_type=code&redirect_uri=http://localhost:8888/callback&scope=playlist-modify-private"

CLIENT_ID = "214c5826a3024e999ffefd76cdac28c4"
CLIENT_SECRET = open("clientsecret").read()

def get_initial_access_token():
    payload = {
        "grant_type": "authorization_code",
        "redirect_uri": "http://localhost:8888/callback",
        "code": open("accesscode").read(),
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    r = requests.post("https://accounts.spotify.com/api/token", data=payload)
    data = json.loads(r.text)
    if "error" in data.keys():
        raise Exception("Could not get access token: %s" % data["error"])
    print(data)
    access_token_file = open("accesstoken", "w")
    access_token_file.write(data["access_token"])
    access_token_file.close()
    refresh_token_file = open("refreshtoken", "w")
    refresh_token_file.write(data["refresh_token"])
    refresh_token_file.close()
    return data["access_token"]


def make_api_request(endpoint_url, params={}, data={}, use_prefix=True, method="GET"):
    prefix = "https://api.spotify.com/v1"
    with open("accesstoken") as f:
        headers = {
            "Authorization": "Bearer " + f.read(),
            "Content-Type": "application/json"
        }
    if method == "GET":
        r = requests.get(prefix*use_prefix + endpoint_url, headers=headers,
                params=params)
    elif method == "POST":
        r = requests.post(prefix*use_prefix + endpoint_url, headers=headers,
                params=params, data=data)
    else:
        raise Exception("Invalid method name")
    try:
        data = json.loads(r.text)
    except ValueError:
        return
    if "error" in data.keys():
        if data["error"]["status"] == 401:
            print("Getting new access token")
            get_new_token()
            make_api_request(endpoint_url, params, use_prefix=use_prefix)
        else:
            raise Exception("Error making '%s' request to endpoint %s, code %d: %s"
                    % (method, endpoint_url, data["error"]["status"],
                    data["error"]["message"]))
    return data


def get_new_token():
    with open("refreshtoken") as f:
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": f.read(),
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
    r = requests.post("https://accounts.spotify.com/api/token", data=payload)
    data = json.loads(r.text)
    if "error" in data.keys():
        raise Exception("Couldn't refresh access token: '%s'" 
                % data['error_description'])
    access_token_file = open("accesstoken", "w")
    access_token_file.write(data["access_token"])
    access_token_file.close()
    if "refresh_token" in data.keys():
        refresh_token_file = open("refreshtoken", "w")
        refresh_token_file.write(data["refresh_token"])
        refresh_token_file.close()
    print(data)


def get_artist_id(artist_search_string):
    payload = {
        "type": "artist",
        "q": artist_search_string
    }
    data = make_api_request("/search", params=payload)
    if len(data['artists']['items']) == 0:
        raise Exception("Error searching for artist")
    artist = data['artists']['items'][0]
    return artist['id']


def recurse_data(next_url):
    data = make_api_request(next_url, use_prefix=False)
    if len(data['items']) == 0:
        raise Exception("Error recursively getting items")
    if data['next'] is None:
        return data['items']
    else:
        # Wait a bit for politeness's sake
        time.sleep(0.5)
        return data['items'] + recurse_data(data['next'])


def get_all_album_ids(artist_id):
    albums = recurse_data("https://api.spotify.com/v1/artists/" + artist_id + "/albums")
    return [album['id'] for album in albums]


def get_track_ids_from_albums(album_ids, artist_id):
    track_ids = []
    for id in album_ids:
        tracks = recurse_data("https://api.spotify.com/v1/albums/" + id + "/tracks")
        track_ids += [track['uri'] for track in tracks if artist_id in
                [artist["id"] for artist in track["artists"]]]
    return track_ids


def get_current_user_id():
    data = make_api_request("/me")
    return data['id']


def create_new_playlist(playlist_name):
    payload = '{"name":"' + playlist_name + '","public":"false"}'
    data = make_api_request("/users/" + get_current_user_id() + "/playlists",
            data=payload, method="POST")
    return data['id']


def add_tracks_to_playlist(user_id, playlist_id, tracks):
    for i in range(1 + int(len(tracks)/20)):
        payload = {
            "uris": ",".join(tracks[i*20:(i+1)*20])
        }
        if len(payload['uris']) == 0:
            break
        make_api_request("/users/" + user_id + "/playlists/" + playlist_id
                + "/tracks", params=payload, method="POST")


def main(artist_name):
    playlist_id = create_new_playlist("Playlistifier: " + artist_name)
    artist_id = get_artist_id(artist_name)
    user_id = get_current_user_id()
    tracks = get_track_ids_from_albums(get_all_album_ids(artist_id), artist_id)
    add_tracks_to_playlist(user_id, playlist_id, tracks)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise Exception("Usage: start.py <artist_name>")
    
    artist_name = sys.argv[1]
    main(artist_name)
