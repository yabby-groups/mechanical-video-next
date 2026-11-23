"""Source restrictions for newly created production ledgers."""

from functools import lru_cache
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from scripts.common import filehash, read_input_json

FIELD = 'no_patent_policy_version'
NO_PATENT_POLICY_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]
PUBLICATION = re.compile(
    r'(?<![a-z0-9])(?:US|EP|WO|CN|JP|KR|DE|GB|FR|CA|TW|AU|RU)[\s-]*'
    r'(?:\d[\s,./-]*){6,14}[ABCUYST]\d?(?![a-z0-9])', re.I)
PATENT_HEADER = re.compile(
    r'(?im)^\s*(?:\(12\)\s*)?(?:(?:united states|european)\s+)?'
    r'(?:patent(?: application publication| specification)?|发明专利申请|实用新型专利|发明专利)\s*$')
PATENT_OFFICES = {'patents.google.com', 'patentscope.wipo.int', 'worldwide.espacenet.com',
                  'data.epo.org', 'patentimages.storage.googleapis.com',
                  'image-ppubs.uspto.gov', 'ppubs.uspto.gov', 'patentcenter.uspto.gov'}
IDENTITY = {'url', 'source_url', 'canonical_url', 'origin_url', 'original_url', 'location',
            'document_id', 'publication_number', 'patent_number', 'source_name',
            'document_title', 'path', 'reference_id', 'source_id', 'source_ids', 'source'}
SOURCE_LISTS = {'references', 'product_references', 'subject_references'}
LINKED_RECORDS = {'assembly_config', 'blueprint_evidence', 'production_config',
                  'source_manifest', 'model_provenance', 'media_provenance'}


def enabled(document):
    if FIELD not in document:
        return False
    if type(document[FIELD]) is not int or document[FIELD] != NO_PATENT_POLICY_VERSION:
        raise ValueError('Unsupported no-patent policy version')
    return True


def forbidden(source):
    raise ValueError(f'PATENT_SOURCE_FORBIDDEN: new productions cannot use patents ({source})')


def check_identity(value):
    if not isinstance(value, str):
        return
    value = unquote(value).strip()
    if not value:
        return
    url = urlsplit(value) if value.lower().startswith(('https://', 'http://')) else None
    if (PUBLICATION.search(value) or PATENT_HEADER.search(value)
            or re.search(r'(?i)\bpatents?\s*(?:no\.?|number|publication)\s*[:#]?\s*\d', value)
            or (url and (url.hostname in PATENT_OFFICES or '/patent/' in url.path.lower()))):
        forbidden(value)


@lru_cache(maxsize=128)
def inspect_pdf(path, sha256):
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(path)
        metadata = reader.metadata or {}
        front = '\n'.join(reader.pages[index].extract_text() for index in range(min(len(reader.pages), 2)))
    except (OSError, PyPdfError, ValueError) as error:
        raise ValueError(f'SOURCE_IDENTITY_UNKNOWN: unreadable PDF ({path})') from error
    for key in ('/Title', '/Subject', '/Author'):
        check_identity(metadata.get(key))
    if (PATENT_HEADER.search(front)
            or (re.search(r'\(1[0129]\)', front) and PUBLICATION.search(front[:3500]))):
        forbidden(path)
    if not front.strip():
        raise ValueError(f'SOURCE_IDENTITY_UNKNOWN: PDF needs a searchable identification page ({path})')


def validate_sources(document, *, policy):
    """Inspect structured source identity and linked evidence, without scanning prose."""
    if not enabled(policy):
        return
    seen = set()

    def visit(value, field=None):
        if isinstance(value, list):
            if field in SOURCE_LISTS and any(not isinstance(row, dict) for row in value):
                raise ValueError('References must be a list of source records')
            for item in value:
                visit(item, field)
            return
        if isinstance(value, dict):
            if FIELD in value:
                enabled(value)
            if field in SOURCE_LISTS:
                field = None
            for key, item in value.items():
                if (key in {'type', 'source_kind', 'document_type', 'source_type', 'identity_basis'}
                        and isinstance(item, str)
                        and item.strip().lower() in {'patent', 'patent application', 'utility model', '专利'}):
                    forbidden(value.get('location') or value.get('path') or item)
                if key in {'patent_number', 'patent_id'} and item:
                    forbidden(item)
                if key in SOURCE_LISTS and not isinstance(item, list):
                    raise ValueError('References must be a list of source records')
                if key == 'path':
                    inspect_binding(item, value.get('sha256'), field)
                elif key in {'location', 'source'} and isinstance(item, str):
                    if Path(item).suffix.lower() == '.pdf' and not urlsplit(item).scheme:
                        inspect_binding(item, None, key)
                elif key in LINKED_RECORDS and isinstance(item, str):
                    inspect_binding(item, None, key)
                visit(item, key)
            return
        if field in IDENTITY:
            check_identity(value)

    def inspect_binding(location, expected, field):
        if not isinstance(location, str) or not location:
            return
        check_identity(location)
        path = (ROOT / location).resolve()
        if not path.is_file():
            if field in LINKED_RECORDS or path.suffix.lower() == '.pdf':
                raise ValueError(f'SOURCE_IDENTITY_UNKNOWN: missing source ({path})')
            return
        with path.open('rb') as stream:
            signature = stream.read(1024)
        is_pdf = path.suffix.lower() == '.pdf' or b'%PDF-' in signature
        linked = field in LINKED_RECORDS and path.suffix.lower() == '.json'
        text_source = (path.suffix.lower() in {'.txt', '.md', '.html'}
                       and field in {'source', 'sources', 'source_files', 'evidence_files', 'basis', 'evidence'})
        if not (is_pdf or text_source or linked and path not in seen):
            return
        actual = filehash(path)
        if expected is not None and expected != actual:
            label = 'config missing or changed' if field == 'production_config' else 'source changed'
            raise ValueError(f'SOURCE_IDENTITY_UNKNOWN: {label} ({path})')
        if is_pdf:
            inspect_pdf(str(path), actual)
        elif text_source:
            with path.open('rb') as stream:
                front = stream.read(8192).decode('utf-8', errors='replace')
            if PATENT_HEADER.search(front):
                forbidden(path)
        else:
            seen.add(path)
            visit(read_input_json(path))

    visit(document)


def require_source_ids(record, allowed, label):
    source_ids = record.get('source_ids')
    if (not isinstance(source_ids, list) or not source_ids
            or not all(isinstance(key, str) and key in allowed for key in source_ids)):
        raise ValueError(f'SOURCE_IDENTITY_UNKNOWN: {label} needs verified source IDs')
    return set(source_ids)
