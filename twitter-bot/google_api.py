# -*- coding: utf-8 -*-

from apiclient.discovery import build
from local_settings import GOOGLE_API_KEY


def get_google_url_shortener():
    """
    This method returns a Google URL Shortener object for
    use in making API calls.
    """
    return build(
        'urlshortener', 'v1',
        developerKey=GOOGLE_API_KEY
    )


def create_short_url(long_url):
    """
    Returns a dictionary containing API response params,
    including the shortened URL.
    """
    api = get_google_url_shortener()

    return api.url().insert(body={
        'longUrl': long_url,
    }).execute()
