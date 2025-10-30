import time

from vdbpy.config import SONGLIST_API_URL, WEBSITE
from vdbpy.types.core import SonglistCategory
from vdbpy.utils.logger import get_logger
from vdbpy.utils.network import (
    fetch_json,
    fetch_json_items,
    fetch_json_items_with_total_count,
    fetch_text,
)

type Songlist = dict  # TODO

logger = get_logger()


def get_featured_songlists(params) -> list[Songlist]:
    return fetch_json_items(SONGLIST_API_URL + "/featured", params=params)


def get_featured_songlist(params) -> Songlist:
    result = fetch_json(SONGLIST_API_URL + "/featured", params=params)
    return result["items"][0] if result["items"] else {}


def get_featured_songlists_with_total_count(
    params, max_results=10**9
) -> tuple[list[Songlist], int]:
    return fetch_json_items_with_total_count(
        SONGLIST_API_URL + "/featured", params=params, max_results=max_results
    )


def create_or_update_songlist(
    session,
    song_ids: list[int],
    author_id: int,
    notes: list[str] | None = None,
    songlist_id=0,
    title="",
    description="",
    category: SonglistCategory = "Nothing",
) -> None:
    """Create or update a songlist.

    Specfify songlist_id for updating a list.
    Omit songlist_id to create a new list.
    """
    data = {
        "songLinks": [],
        "author": {"id": author_id},
        "name": title,
        "featuredCategory": category,
        "description": description,
        "status": "Finished",
        "updateNotes": "",
    }

    if songlist_id:
        data["id"] = songlist_id

    order = 1
    if notes is None:
        notes = [""] * len(song_ids)
    for song_id, note in zip(song_ids, notes):
        songlist_line = {
            "order": order,
            "song": {"id": song_id},
            "notes": note,
        }
        data["songLinks"].append(songlist_line)
        order += 1

    songlist_request = session.post(SONGLIST_API_URL, json=data)
    songlist_request.raise_for_status()
    if songlist_id:
        logger.info(f"Updated songlist at {WEBSITE}/SongList/Details/{songlist_id}")
        logger.debug(f"DATA: {data}")
    else:
        songlist_id = songlist_request.json()
        logger.info(f"Created songlist at {WEBSITE}/SongList/Details/{songlist_id}")
        logger.debug(f"DATA: {data}")


def create_songlists_with_size_limit(
    session, song_ids: list[int], author_id, title="", max_length=200
) -> None:
    """Create songlists with a maximum size limit, splitting the songlist into sublists."""
    if not title.strip():
        title = "Songlist"
    counter = 1

    for i in range(1 + len(song_ids) // max_length):
        sublist = song_ids[i * max_length : (i + 1) * max_length]
        if not sublist:
            break

        if len(song_ids) > max_length:
            logger.info(f"Posting sublist {counter}")
            create_or_update_songlist(
                session, sublist, author_id, title=f"{title} #{counter}"
            )
            time.sleep(3)

        else:
            logger.info("Posting songlist")
            create_or_update_songlist(session, sublist, author_id, title=title)

        counter += 1


def export_songlist(songlist_id: int) -> list[str]:
    text = fetch_text(f"{WEBSITE}/SongList/Export/{songlist_id}").splitlines()
    # notes;publishdate;title;url;pv.original.niconicodouga;pv.original.!niconicodouga;pv.reprint
    table_without_header = text[1:]
    new_header = "songlist_notes;published;title;url;nico_pv;original_pv;reprint_pv"
    return [new_header, *table_without_header]


def parse_csv_songlist(csv: list[str], delimiter=";") -> list[list[str]]:
    lines = [line.split(delimiter) for line in csv if line.strip()]
    logger.debug(f"Parsing csv of length {len(csv)}. First lines: {csv[:2]}")
    for line in lines[1:]:
        extra_length = len(line) - 7
        if extra_length:
            # Title contains delimiter chars
            # ['127 537 views', '1/26/2023', '"PLS (-__-', ')"', 'https://vocadb.net/S/471057', '', 'https://youtu.be/CMPfzVbEX4E', '']
            logger.debug("Exported CSV contains title with delimiter chars:")
            logger.debug(line)
            # Merge items starting from index 2:
            fixed_line = line[:2] + line[2 : 2 + extra_length] + line[-4:]
            logger.debug(f"Fixed line (len={len(fixed_line)}) is:")
            assert len(fixed_line) == 7  # noqa: S101
            lines[lines.index(line)] = fixed_line
    return lines
