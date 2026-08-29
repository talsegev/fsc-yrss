import os
import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime


# ============================================================
# Configuration
# ============================================================

CLIENT_ID = os.environ.get("SOUNDCLOUD_CLIENT_ID")
USER_ID = os.environ.get("SOUNDCLOUD_USER_ID", "19053868")
USERNAME = os.environ.get("SOUNDCLOUD_USERNAME", "yondertapes")

API_BASE = "https://api-v2.soundcloud.com"
TRACKS_URL = f"{API_BASE}/users/{USER_ID}/tracks"

OUTPUT_FILE = "yonder.xml"

PAGE_LIMIT = 50
REQUEST_TIMEOUT = 30

PROFILE_URL = f"https://soundcloud.com/{USERNAME}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": PROFILE_URL,
}


# ============================================================
# Validation
# ============================================================

if not CLIENT_ID:
    print("ERROR: SOUNDCLOUD_CLIENT_ID is not set.")
    sys.exit(1)


# ============================================================
# SoundCloud API
# ============================================================

def fetch_tracks():
    """
    Fetch every track from the SoundCloud user's track collection.

    SoundCloud uses cursor-style pagination here.

    The first request is:

        /users/{user_id}/tracks?client_id=...&limit=50

    The API then returns a `next_href`, for example:

        https://api-v2.soundcloud.com/users/19053868/tracks
        ?offset=2023-01-08T13%3A13%3A09.000Z,tracks,...
        &limit=50

    We follow `next_href` until it disappears or an empty collection
    is returned.
    """

    session = requests.Session()
    session.headers.update(HEADERS)

    tracks = []
    seen_ids = set()

    url = TRACKS_URL

    params = {
        "client_id": CLIENT_ID,
        "limit": PAGE_LIMIT,
    }

    page = 0

    while url:
        page += 1

        print(f"\nFETCH PAGE {page}")
        print(url)

        try:
            response = session.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            print(f"ERROR requesting SoundCloud: {exc}")
            sys.exit(1)

        print("STATUS:", response.status_code)

        try:
            response.raise_for_status()
        except requests.HTTPError:
            print(response.text[:1000])
            raise

        try:
            data = response.json()
        except ValueError:
            print("ERROR: SoundCloud returned invalid JSON.")
            print(response.text[:1000])
            sys.exit(1)

        collection = data.get("collection", [])

        print("THIS PAGE:", len(collection))

        if not collection:
            break

        for track in collection:
            track_id = track.get("id")

            if track_id is None:
                continue

            if track_id in seen_ids:
                continue

            seen_ids.add(track_id)
            tracks.append(track)

        # IMPORTANT:
        # The second and subsequent requests must use the complete
        # next_href supplied by SoundCloud.
        next_href = data.get("next_href")

        if not next_href:
            break

        url = next_href

        # next_href already contains its own query parameters.
        # Do not append client_id/limit again.
        params = None

    print("\nTOTAL:", len(tracks))

    return tracks


# ============================================================
# Helpers
# ============================================================

def track_url(track):
    """
    Return the public SoundCloud URL.
    """

    permalink_url = track.get("permalink_url")

    if permalink_url:
        return permalink_url

    permalink = track.get("permalink")

    if permalink:
        return f"https://soundcloud.com/{USERNAME}/{permalink}"

    return PROFILE_URL


def track_title(track):
    """
    Return a safe RSS title.
    """

    title = track.get("title")

    if title:
        return str(title)

    return "Untitled"


def track_description(track):
    """
    Build a useful RSS description.
    """

    description = track.get("description")

    if description:
        return str(description)

    title = track_title(track)

    return f"{title} by Yonder"


def track_pub_date(track):
    """
    Convert SoundCloud's created_at timestamp to RFC 2822,
    which is what RSS expects for pubDate.
    """

    created_at = track.get("created_at")

    if not created_at:
        return format_datetime(datetime.now(timezone.utc))

    try:
        # SoundCloud normally returns:
        # 2026-08-29T12:34:56.000Z
        dt = datetime.fromisoformat(
            created_at.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return format_datetime(dt)
    except Exception:
        return format_datetime(datetime.now(timezone.utc))


def track_image(track):
    """
    Get the SoundCloud artwork URL if available.
    """

    artwork = track.get("artwork_url")

    if artwork:
        return artwork

    user = track.get("user") or {}

    avatar = user.get("avatar_url")

    if avatar:
        return avatar

    return None


# ============================================================
# RSS generation
# ============================================================

def create_rss(tracks):
    """
    Create the RSS XML document.
    """

    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
            "xmlns:content": "http://purl.org/rss/1.0/modules/content/",
        },
    )

    channel = ET.SubElement(rss, "channel")

    ET.SubElement(
        channel,
        "title",
    ).text = "Yonder"

    ET.SubElement(
        channel,
        "link",
    ).text = PROFILE_URL

    ET.SubElement(
        channel,
        "description",
    ).text = "Yonder SoundCloud tracks and DJ sets."

    ET.SubElement(
        channel,
        "language",
    ).text = "en"

    ET.SubElement(
        channel,
        "generator",
    ).text = "Yonder RSS Bot"

    ET.SubElement(
        channel,
        "lastBuildDate",
    ).text = format_datetime(datetime.now(timezone.utc))

    ET.SubElement(
        channel,
        "itunes:author",
    ).text = "Yonder"

    ET.SubElement(
        channel,
        "itunes:explicit",
    ).text = "false"

    # Keep newest tracks first.
    tracks = sorted(
        tracks,
        key=lambda t: (
            t.get("created_at") or "",
            t.get("id") or 0,
        ),
        reverse=True,
    )

    for track in tracks:
        item = ET.SubElement(channel, "item")

        title = track_title(track)
        url = track_url(track)

        ET.SubElement(
            item,
            "title",
        ).text = title

        ET.SubElement(
            item,
            "link",
        ).text = url

        ET.SubElement(
            item,
            "guid",
            {
                "isPermaLink": "true",
            },
        ).text = url

        ET.SubElement(
            item,
            "description",
        ).text = track_description(track)

        ET.SubElement(
            item,
            "pubDate",
        ).text = track_pub_date(track)

        image = track_image(track)

        if image:
            ET.SubElement(
                item,
                "itunes:image",
                {
                    "href": image,
                },
            )

        # Store the SoundCloud track ID as a custom metadata element.
        track_id = track.get("id")

        if track_id is not None:
            ET.SubElement(
                item,
                "soundcloud:id",
            ).text = str(track_id)

    return rss


# ============================================================
# XML writing
# ============================================================

def write_xml(root):
    """
    Write formatted XML to disk.
    """

    tree = ET.ElementTree(root)

    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        # Python < 3.9 compatibility.
        pass

    tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True,
    )


# ============================================================
# Main
# ============================================================

def main():
    print("========================================")
    print("Yonder RSS Generator")
    print("========================================")
    print("User:", USERNAME)
    print("User ID:", USER_ID)
    print("Output:", OUTPUT_FILE)

    tracks = fetch_tracks()

    if not tracks:
        print("ERROR: No tracks were returned.")
        sys.exit(1)

    root = create_rss(tracks)

    # ElementTree doesn't automatically declare custom namespaces
    # used in tags. Register them before writing.
    ET.register_namespace(
        "itunes",
        "http://www.itunes.com/dtds/podcast-1.0.dtd",
    )

    ET.register_namespace(
        "content",
        "http://purl.org/rss/1.0/modules/content/",
    )

    ET.register_namespace(
        "soundcloud",
        "https://soundcloud.com/",
    )

    write_xml(root)

    print()
    print("RSS generated successfully.")
    print("Tracks:", len(tracks))
    print("File:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
