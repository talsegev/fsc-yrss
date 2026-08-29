import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import format_datetime

CLIENT_ID = os.environ.get("SOUNDCLOUD_CLIENT_ID")
USER_ID = "19053868"

API_URL = f"https://api-v2.soundcloud.com/users/{USER_ID}/tracks"
OUTPUT_FILE = "yonder.xml"

HEADERS = {
"User-Agent": (
"Mozilla/5.0 (X11; Linux x86_64) "
"AppleWebKit/537.36 (KHTML, like Gecko) "
"Chrome/140 Safari/537.36"
),
"Accept": "application/json",
"Referer": "https://soundcloud.com/yondertapes",
}

if not CLIENT_ID:
raise RuntimeError("SOUNDCLOUD_CLIENT_ID is not set")

session = requests.Session()
session.headers.update(HEADERS)

tracks = []
url = API_URL

while url:
response = session.get(
url,
params={
"client_id": CLIENT_ID,
"limit": 50,
},
timeout=30,
)

response.raise_for_status()

data = response.json()
tracks.extend(data.get("collection", []))
url = data.get("next_href")


if not tracks:
raise RuntimeError("SoundCloud returned no tracks")

rss = ET.Element(
"rss",
{
"version": "2.0",
"xmlns:atom": "http://www.w3.org/2005/Atom",
},
)

channel = ET.SubElement(rss, "channel")

ET.SubElement(channel, "title").text = "Yonder SoundCloud"
ET.SubElement(channel, "link").text = "https://soundcloud.com/yondertapes"
ET.SubElement(channel, "description").text = "Latest tracks from Yonder"

for track in tracks:
item = ET.SubElement(channel, "item")

permalink = track.get("permalink_url", "")

ET.SubElement(item, "title").text = track.get("title", "Untitled")
ET.SubElement(item, "link").text = permalink
ET.SubElement(item, "guid").text = permalink
ET.SubElement(item, "description").text = track.get("description", "")

created_at = track.get("created_at")

if created_at:
    try:
        dt = datetime.fromisoformat(
            created_at.replace("Z", "+00:00")
        )
        ET.SubElement(item, "pubDate").text = format_datetime(dt)
    except ValueError:
        pass


ET.indent(rss, space=" ")

ET.ElementTree(rss).write(
OUTPUT_FILE,
encoding="utf-8",
xml_declaration=True,
)

print(f"Generated {OUTPUT_FILE} with {len(tracks)} tracks")
