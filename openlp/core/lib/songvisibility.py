"""Remember per-song page exclusions independently of a service file."""
import hashlib
import json
import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from openlp.core.common.applocation import AppLocation

log = logging.getLogger(__name__)


def store_path():
    return AppLocation.get_section_data_path('songs') / 'slide-visibility.json'


def song_key(item):
    if item.edit_id:
        return 'song:' + str(item.edit_id)
    data = item.data_string if isinstance(item.data_string, dict) else {}
    identity = [data.get('ccli_number', ''), data.get('title', item.title), data.get('authors', '')]
    return 'metadata:' + hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode('utf-8')).hexdigest()


def slide_keys(slides):
    counts = {}
    for slide in slides:
        identity = [slide.get('verse', ''), slide.get('text', '')]
        digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode('utf-8')).hexdigest()
        occurrence = counts.get(digest, 0)
        counts[digest] = occurrence + 1
        yield digest + ':' + str(occurrence)


def read_store():
    path = store_path()
    if not path.exists():
        return {'version': 1, 'songs': {}}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if (data.get('version') != 1 or not isinstance(data.get('songs'), dict) or
                any(not isinstance(record, dict) for record in data['songs'].values())):
            raise ValueError('Unsupported song visibility data')
        return data
    except (OSError, ValueError, AttributeError):
        log.exception('Unable to read remembered song visibility')
        raise


def save_visibility(item):
    """Write choices atomically; retain records for sections absent from this arrangement."""
    data = read_store()
    choices = dict(data['songs'].get(song_key(item), {}))
    for key, slide in zip(slide_keys(item.slides), item.slides):
        choices[key] = list(slide.get('hidden_pages', []))
    data['songs'][song_key(item)] = choices
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def apply_visibility(item):
    """Apply remembered choices to a newly generated library/drag/drop service item."""
    if item.name != 'songs':
        return
    try:
        choices = read_store()['songs'].get(song_key(item), {})
    except (OSError, ValueError, AttributeError):
        return
    for key, slide in zip(slide_keys(item.slides), item.slides):
        pages = choices.get(key)
        if isinstance(pages, list):
            slide['hidden_pages'] = [page for page in pages if type(page) is int and page >= 0]
    item._clear_slides_cache()
