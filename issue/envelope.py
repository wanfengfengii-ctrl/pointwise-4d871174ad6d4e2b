import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass


_ISSUANCE_ID = re.compile(r'[0-9a-f]{32}')
_SHA256 = re.compile(r'[0-9a-f]{64}')


@dataclass(frozen=True)
class V1Envelope:
    issuance_id: str
    body: bytes


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON field {key!r}')
        result[key] = value
    return result


def json_object(raw):
    if type(raw) is not bytes:
        raise ValueError('expected UTF-8 JSON bytes')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_fields)
    except (ValueError, RecursionError) as exc:
        raise ValueError('invalid UTF-8 JSON') from exc


def require_fields(record, fields, label):
    if not isinstance(record, dict) or record.keys() != fields:
        raise ValueError(f'invalid fields in {label}')


def require_issuance_id(value):
    if not isinstance(value, str) or not _ISSUANCE_ID.fullmatch(value):
        raise ValueError('invalid issuance ID')
    return value


def _digest(issuance_id, body):
    digest = hashlib.sha256(b'window-v1\0' + bytes.fromhex(issuance_id))
    digest.update(body)
    return digest.hexdigest()


def seal_envelope(issuance_id, body):
    require_issuance_id(issuance_id)
    if type(body) is not bytes:
        raise ValueError('expected package body bytes')
    return json_bytes({
        'version': 1,
        'issuance_id': issuance_id,
        'body': base64.b64encode(body).decode('ascii'),
        'sha256': _digest(issuance_id, body),
    })


def verify_envelope(packet):
    content = json_object(packet)
    require_fields(content, {'version', 'issuance_id', 'body', 'sha256'}, 'V1 envelope')
    if type(content['version']) is not int or content['version'] != 1:
        raise ValueError('unsupported envelope version')
    issuance_id = require_issuance_id(content['issuance_id'])
    encoded, declared = content['body'], content['sha256']
    if not isinstance(encoded, str):
        raise ValueError('invalid encoded package body')
    if not isinstance(declared, str) or not _SHA256.fullmatch(declared):
        raise ValueError('invalid package checksum')
    try:
        body = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ValueError('invalid Base64 package body') from exc
    if not hmac.compare_digest(declared, _digest(issuance_id, body)):
        raise ValueError('package body checksum mismatch')
    return V1Envelope(issuance_id, body)
