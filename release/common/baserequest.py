"""
request client
"""
import requests


class BaseRequest(object):
    _headers = {
        'Content-Type': 'application/json'
    }

    @classmethod
    def post(cls, payload, url):
        response = requests.request("POST", url, headers=cls._headers, json=payload, timeout=5)
        return response.json()
