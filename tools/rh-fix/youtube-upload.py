#!/usr/bin/env python3
"""Upload a video to YouTube with the official Data API (OAuth desktop flow).

Usage:
  youtube-upload.py --file VIDEO --meta META.json --secret CLIENT_SECRET.json
                    [--token TOKEN.json] [--thumbnail THUMB.png]
"""
import argparse
import json
import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--secret", required=True)
    ap.add_argument("--token", default=os.path.expanduser("~/.config/youtube/token.json"))
    ap.add_argument("--thumbnail", default=None)
    args = ap.parse_args()

    with open(args.meta, encoding="utf-8") as fh:
        meta = json.load(fh)

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
            creds = flow.run_local_server(port=0, open_browser=True,
                                          authorization_prompt_message="Opening browser for YouTube authorization...")
        os.makedirs(os.path.dirname(args.token) or ".", exist_ok=True)
        with open(args.token, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())

    yt = build("youtube", "v3", credentials=creds)

    snippet = {
        "title": meta["title"],
        "description": meta.get("description", ""),
        "tags": meta.get("tags", []),
        "categoryId": str(meta.get("categoryId", "28")),
        "defaultLanguage": meta.get("defaultLanguage", "en"),
        "defaultAudioLanguage": meta.get("defaultAudioLanguage", "en"),
    }
    status = {
        "privacyStatus": meta.get("privacyStatus", "private"),
        "selfDeclaredMadeForKids": bool(meta.get("madeForKids", False)),
        "license": "youtube",
        "embeddable": True,
    }

    media = MediaFileUpload(args.file, chunksize=8 * 1024 * 1024, resumable=True)
    request = yt.videos().insert(part="snippet,status", body={
        "snippet": snippet, "status": status}, media_body=media)

    print(f"uploading {args.file} ({os.path.getsize(args.file)/1e6:.1f} MB)", flush=True)
    response = None
    while response is None:
        status_progress, response = request.next_chunk()
        if status_progress:
            print(f"  {int(status_progress.progress() * 100)}%", flush=True)

    vid = response["id"]
    print(f"uploaded https://youtu.be/{vid}", flush=True)

    if args.thumbnail:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(args.thumbnail)).execute()
        print("thumbnail set", flush=True)

    print(json.dumps({"id": vid, "url": f"https://youtu.be/{vid}"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
