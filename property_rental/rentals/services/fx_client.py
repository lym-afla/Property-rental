from typing import TypedDict

import requests
from django.conf import settings


class ReleaseMetadata(TypedDict):
    id: str
    seq: int
    history_epoch: int


class RateBatch(TypedDict):
    results: list[dict]


class FXClient:
    def __init__(self):
        self.base_url = settings.FX_BASE_URL.rstrip('/')
        self.headers = {'Authorization': f'Bearer {settings.FX_TOKEN}'}

    def _request(self, method, path, **kwargs):
        response = requests.request(method, self.base_url + path, headers=self.headers, timeout=(3, 30), **kwargs)
        response.raise_for_status()
        return response.json()

    def current_release(self) -> ReleaseMetadata:
        release = self._request('GET', '/v1/releases/current')
        self._release_id = release['id']
        return release

    def changes(self, after_seq):
        release_id = self._release_id
        cursor = None
        seen = set()
        while True:
            params = {'after_seq': after_seq}
            if cursor is not None:
                params['cursor'] = cursor
            page = self._request('GET', f'/v1/releases/{release_id}/changes', params=params)
            yield page
            cursor = page['next_cursor']
            if cursor is None:
                return
            if cursor in seen:
                raise ValueError('Repeated FX cursor')
            seen.add(cursor)

    def rates(self, release_id, queries) -> RateBatch:
        return self._request('POST', '/v1/rates:batch', json={'release_id': release_id, 'queries': queries})
