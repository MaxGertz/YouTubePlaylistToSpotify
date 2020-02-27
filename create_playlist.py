import json
import os

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import requests
import youtube_dl

from exceptions import ResponseException
from secrets import spotify_token, spotify_user_id


class CreatePlaylist:
    def __init__(self, playlist_id, playlist_title):
        self.playlist_id = playlist_id
        self.playlist_title = playlist_title
        self.youtube_client = self.get_youtube_client()
        self.all_song_info = {}

    def get_youtube_client(self):
        """ Log Into Youtube, Copied from Youtube Data API """
        # Disable OAuthlib's HTTPS verification when running locally.
        # *DO NOT* leave this option enabled in production.
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

        api_service_name = "youtube"
        api_version = "v3"
        client_secrets_file = "client_secret.json"

        # Get credentials and create an API client
        scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes)
        credentials = flow.run_console()

        # from the Youtube DATA API
        youtube_client = googleapiclient.discovery.build(api_service_name, api_version, credentials=credentials)

        return youtube_client

    def get_song_infos(self, playlist_items):
        for playlist_item in playlist_items:
            for item in playlist_item:
                video_title = item["snippet"]["title"]
                youtube_url = "https://www.youtube.com/watch?v={}".format(item["contentDetails"]["videoId"])
                # use youtube_dl to collect the song name & artist name
                video = youtube_dl.YoutubeDL({}).extract_info(youtube_url, download=False)
                song_name = video["track"]
                artist = video["artist"]

                if song_name is not None and artist is not None:
                    # save all important info and skip any missing song and artist
                    self.all_song_info[video_title] = {
                        "youtube_url": youtube_url,
                        "song_name": song_name,
                        "artist": artist,

                        # add the uri, easy to get song to put into playlist
                        "spotify_uri": self.get_spotify_uri(song_name, artist)
                    }

    def get_playlist_videos(self):
        playlist_items = []
        request = self.youtube_client.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=self.playlist_id
        )

        response = request.execute()
        playlist_items.append(response["items"])
        # youtube api has a limit of 50 items
        # check if there is a next page
        if "nextPageToken":
            page_token = response["nextPageToken"]

            while page_token is not None:
                request = self.youtube_client.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=self.playlist_id,
                    pageToken=page_token
                )
                response = request.execute()
                playlist_items.append(response["items"])
                if "nextPageToken" in response:
                    page_token = response["nextPageToken"]
                else:
                    page_token = None

        print(len(playlist_items))

        self.get_song_infos(playlist_items)

    def create_playlist(self):
        request_body = json.dumps({
            "name": self.playlist_title,
            "description": "Generated from YouTube playlist",
            "public": True
        })

        query = "https://api.spotify.com/v1/users/{}/playlists".format(spotify_user_id)
        response = requests.post(
            query,
            data=request_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(spotify_token)
            }
        )
        response_json = response.json()

        print(response_json)

        # playlist id
        return response_json["id"]

    def get_spotify_uri(self, song_name, artist):
        query = "https://api.spotify.com/v1/search?query=track%3A{}+artist%3A{}&type=track&offset=0&limit=20".format(
            song_name,
            artist
        )
        response = requests.get(
            query,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(spotify_token)
            }
        )
        response_json = response.json()
        print(response_json)
        songs = response_json["tracks"]["items"]

        # only use the first song
        if len(songs) == 0:
            uri = None
        else:
            uri = songs[0]["uri"]

        return uri

    @property
    def add_song_to_playlist(self):
        """Add all liked songs into a new Spotify playlist"""
        # populate dictionary with our liked songs
        self.get_playlist_videos()

        print("Got all videos from YouTube")
        # collect all of uri
        uris = []
        for song, info in self.all_song_info.items():
            if info["spotify_uri"] is not None:
                uris.append(info["spotify_uri"])

        # create a new playlist
        sp_playlist_id = self.create_playlist()
        print("Created playlist with ID " + sp_playlist_id)
        # add all songs into new playlist
        request_data = json.dumps(uris)

        print("Adding songs to playlist")
        query = "https://api.spotify.com/v1/playlists/{}/tracks".format(sp_playlist_id)

        response = requests.post(
            query,
            data=request_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(spotify_token)
            }
        )

        if response.status_code != 201:
            raise ResponseException(response.status_code)

        print("Done with adding songs to playlist")


if __name__ == '__main__':
    playlist_id = input("Enter YouTube playlist ID:")
    playlist_title = input("Enter Spotify playlist title:")
    cp = CreatePlaylist(playlist_id, playlist_title)
    cp.add_song_to_playlist
