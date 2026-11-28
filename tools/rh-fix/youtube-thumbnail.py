#!/usr/bin/env python3
"""Set custom thumbnails for uploaded videos (needs youtube.force-ssl scope)."""
import argparse
import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secret", required=True)
    ap.add_argument("--token", default=os.path.expanduser("~/.config/youtube/token-force.json"))
    ap.add_argument("--pair", action="append", required=True,
                    help="videoId=thumbnail path (repeatable)")
    args = ap.parse_args()

    creds = None
    if os.path.exists(args.token):
        try:
            creds = Credentials.from_authorized_user_file(args.token, SCOPES)
        except ValueError:
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(args.secret, SCOPES)
            creds = flow.run_local_server(
                port=0, open_browser=True,
                authorization_prompt_message="Opening browser to grant YouTube thumbnail access...")
        with open(args.token, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())

    yt = build("youtube", "v3", credentials=creds)
    for pair in args.pair:
        vid, path = pair.split("=", 1)
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(path)).execute()
        print(json.dumps({"video": vid, "thumbnail": path, "status": "ok"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
