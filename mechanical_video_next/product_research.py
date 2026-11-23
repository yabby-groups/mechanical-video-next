"""Bounded discovery for the existing Producer research handoff."""

import argparse
import json
from pathlib import Path
import re
from urllib.error import URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .reference_library import canonical_video_id, product_implementations
from .source_policy import check_identity
from scripts.common import digest

VERSION = 1
MAX_RESPONSE = 1024 * 1024


def search(query):
    if query['category'] == 'ifixit':
        url = 'https://www.ifixit.com/api/2.0/search/' + quote(query['query'], safe='') + '?limit=6'
    else:
        url = 'https://www.bing.com/search?' + urlencode(
            {'format': 'rss', 'q': query['query'], 'setlang': query['language']})
    with urlopen(Request(url, headers={'User-Agent': 'MechanicalVideoNext/1.0'}), timeout=5) as response:
        body = response.read(MAX_RESPONSE + 1)
    if len(body) > MAX_RESPONSE:
        raise ValueError('Search response exceeds the byte budget')
    if query['category'] == 'ifixit':
        return [(row['url'], row.get('title', '')) for row in json.loads(body)['results'] if row.get('url')]
    root = ElementTree.fromstring(body)
    if root.tag != 'rss':
        raise ValueError('Search provider did not return RSS')
    return [(row.findtext('link'), row.findtext('title')) for row in root.findall('./channel/item')]


def discover(plan, *, lookup=search):
    """Keep all search hits as leads until a located inspection is registered."""
    pinned = plan['model'] if plan['model_locked'] else None
    implementations = product_implementations(plan['cached'], pinned_model=pinned)
    leads, attempts = {}, []
    seen = {row['canonical_id'] for row in plan['cached']}
    limit = plan['budget']['distinct_sources']
    product_terms = set(re.findall(r'[a-z0-9][a-z0-9-]{2,}', plan['product'].casefold()))

    def relevant(url, title, query):
        if query['category'] == 'ifixit':
            return True
        text = (title + ' ' + url).casefold()
        if plan['product'].casefold() in text or (plan['model'] and plan['model'].casefold() in text):
            return True
        # Feeds occasionally substitute unrelated results. Preserve results in
        # other scripts for human inspection when the product has no Latin terms.
        return not product_terms or any(term in text for term in product_terms)

    def add(url, title, category):
        if not url or urlsplit(url).scheme not in {'http', 'https'}:
            return
        try:
            check_identity(url)
            check_identity(title)
            key = canonical_video_id(url)
        except ValueError:
            return
        if key not in seen and len(leads) < limit:
            leads.setdefault(key, dict(url=url, title=title, category=category,
                                       status='UNKNOWN', license='REFERENCE_ONLY'))

    for url in plan['seeds']:
        add(url, '', 'user_reference')
    complete = any(not candidate['missing'] for candidate in implementations)
    if not complete:
        attempted = set()
        for query in plan['queries'][:plan['budget']['total_queries']]:
            key = query['category'], query['language'], query['query']
            if key in attempted:
                continue
            attempted.add(key)
            try:
                results = lookup(query)
            except (OSError, URLError, ValueError, KeyError, ElementTree.ParseError) as error:
                attempts.append(dict(query, status='UNKNOWN', error=str(error)))
                continue
            attempts.append(dict(query, status='SEARCHED', results=len(results)))
            # Reserve space for alternate models and asset categories.
            matching = [(url, title) for url, title in results
                        if url and relevant(url, title or '', query)]
            for url, title in matching[:2]:
                add(url, title, query['category'])
    return dict(version=VERSION, plan_sha256=digest(plan), product=plan['product'],
                question=plan['question'], attempts=attempts, leads=list(leads.values()),
                implementations=implementations,
                status='CACHED_EVIDENCE' if complete else 'INSPECTION_REQUIRED')


def discover_task(task):
    """Run once per plan in the existing task directory."""
    from .workflow import load, lock, write

    task = Path(task)
    data = load(task)
    path = task / data['product_search_plan']
    with lock(task / 'research/.product-discovery.lock', wait=True):
        plan = json.loads(path.read_text())
        output = path.with_name('product-discovery.json')
        if output.is_file() and json.loads(output.read_text()).get('plan_sha256') == digest(plan):
            return output
        write(output, discover(plan))
        return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task', type=Path)
    print(discover_task(parser.parse_args().task))
