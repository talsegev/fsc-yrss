import re
import html
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime

PROFILE_URL = "https://soundcloud.com/yondertapes"
OUTPUT_FILE = "yonder.xml"
MAX_TRACKS = 500

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; YonderRSS/1.0)"
}


def get_profile_html():
    r = requests.get(PROFILE_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def extract_tracks(page):
    """
    Extract track information embedded in SoundCloud's public profile HTML.
    """
    tracks = []

    # SoundCloud embeds JSON data in the page.
    # Find JSON-LD / hydration data containing track URLs.
    urls = re.findall(
        r'https://soundcloud\.com/yondertapes/[^"\\]+',
        page
    )

    seen = set()

    for url in urls:
        url = html.unescape(url)

        if url in seen:
            continue

        # Ignore profile / playlist URLs
        if "/sets/" in url:
            continue

        seen.add(url)

        slug = url.rstrip("/").split("/")[-1]
        title = slug.replace("-", " ").strip()

        tracks.append({
            "title": title,
            "url": url
        })

    return tracks


def rss_escape(value):
    return html.escape(value, quote=False)


def build_rss(tracks):
    rss = ET.Element("rss", {
        "version": "2.0",
        "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"
    })

    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "Yonder — SoundCloud"
    ET.SubElement(channel, "link").text = PROFILE_URL
    ET.SubElement(channel, "description").text = (
        "All tracks published by Yonder on SoundCloud."
    )
    ET.SubElement(channel, "language").text = "en"

    ET.SubElement(
        channel,
        "lastBuildDate"
    ).text = format_datetime(datetime.now(timezone.utc))

    for track in tracks[:MAX_TRACKS]:
        item = ET.SubElement(channel, "item")

        ET.SubElement(item, "title").text = track["title"]
        ET.SubElement(item, "link").text = track["url"]
        ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = track["url"]

        ET.SubElement(
            item,
            "description"
        ).text = f"Yonder — {track['title']}"

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")

    tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True
    )


def main():
    print("Fetching Yonder SoundCloud profile...")
    page = get_profile_html()

    print("Extracting tracks...")
    tracks = extract_tracks(page)

    print(f"Found {len(tracks)} tracks.")

    if not tracks:
        raise RuntimeError(
            "No tracks found. SoundCloud may have changed its page format."
        )

    build_rss(tracks)

    print(f"RSS written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
