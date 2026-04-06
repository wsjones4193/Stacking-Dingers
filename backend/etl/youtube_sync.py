"""
YouTube RSS feed sync → podcast_episodes table.

Fetches the 15 most recent videos from the @StackingDingers YouTube channel
via the public Atom RSS feed (no API key required). Upserts into
podcast_episodes on youtube_id — existing episodes are never duplicated.

Feed URL:
  https://www.youtube.com/feeds/videos.xml?channel_id=<CHANNEL_ID>

The channel ID for @StackingDingers is resolved from the handle once and
hardcoded below. To re-resolve: visit
  https://www.youtube.com/@StackingDingers
and inspect the page source for "channelId".
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Optional

import httpx
from sqlmodel import Session, select

from backend.db.models import PodcastEpisode

logger = logging.getLogger(__name__)

# Channel ID for @StackingDingers — resolved from the YouTube handle
YOUTUBE_CHANNEL_ID = "UCBYZM8KdBBhf4LRu-cGXmmw"
YOUTUBE_RSS_URL = (
    f"https://www.youtube.com/feeds/videos.xml?channel_id={YOUTUBE_CHANNEL_ID}"
)

# Atom / YouTube XML namespaces
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt":   "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


def _parse_date(raw: str) -> date:
    """Parse an ISO 8601 datetime string from the YouTube feed to a date."""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except Exception:
        return date.today()


def _fetch_feed(url: str) -> Optional[str]:
    """Fetch the RSS feed XML. Returns the raw text or None on failure."""
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.error(f"Failed to fetch YouTube RSS feed: {e}")
        return None


def _parse_feed(xml_text: str) -> list[dict]:
    """
    Parse Atom XML from the YouTube feed into a list of episode dicts.
    Each dict has: youtube_id, title, published_date, description, thumbnail_url.
    """
    episodes: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error(f"Failed to parse YouTube RSS XML: {e}")
        return episodes

    for entry in root.findall("atom:entry", _NS):
        yt_id_el = entry.find("yt:videoId", _NS)
        title_el = entry.find("atom:title", _NS)
        published_el = entry.find("atom:published", _NS)
        media_group = entry.find("media:group", _NS)

        if yt_id_el is None or title_el is None:
            continue

        youtube_id = yt_id_el.text or ""
        title = title_el.text or ""
        published_date = _parse_date(published_el.text or "") if published_el is not None else date.today()

        description = ""
        thumbnail_url = None
        if media_group is not None:
            desc_el = media_group.find("media:description", _NS)
            if desc_el is not None:
                description = desc_el.text or ""
            thumb_el = media_group.find("media:thumbnail", _NS)
            if thumb_el is not None:
                thumbnail_url = thumb_el.attrib.get("url")

        if youtube_id:
            episodes.append({
                "youtube_id": youtube_id,
                "title": title,
                "published_date": published_date,
                "description": description,
                "thumbnail_url": thumbnail_url,
            })

    return episodes


def sync_youtube_feed(session: Session) -> dict:
    """
    Fetch the YouTube RSS feed and upsert new episodes into podcast_episodes.
    Skips episodes that already exist (matched on youtube_id).

    Returns a summary dict with counts.
    """
    xml_text = _fetch_feed(YOUTUBE_RSS_URL)
    if xml_text is None:
        return {"new_episodes": 0, "error": "Feed fetch failed"}

    episodes = _parse_feed(xml_text)
    if not episodes:
        logger.info("YouTube RSS: no episodes parsed from feed")
        return {"new_episodes": 0}

    # Load existing youtube_ids to skip duplicates
    existing_ids = {
        row.youtube_id
        for row in session.exec(select(PodcastEpisode)).all()
    }

    new_count = 0
    for ep in episodes:
        if ep["youtube_id"] in existing_ids:
            continue

        episode = PodcastEpisode(
            youtube_id=ep["youtube_id"],
            title=ep["title"],
            published_date=ep["published_date"],
            description=ep["description"],
            thumbnail_url=ep["thumbnail_url"],
        )
        session.add(episode)
        new_count += 1

    session.commit()
    logger.info(f"YouTube RSS sync: {new_count} new episodes added")
    return {"new_episodes": new_count, "feed_entries": len(episodes)}
