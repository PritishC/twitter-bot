# -*- coding: utf-8 -*-

from apiclient.discovery import build
import tweepy


def get_google_url_shortener(config):
    """
    This method returns a Google URL Shortener object for
    use in making API calls.
    """
    return build(
        'urlshortener', 'v1',
        developerKey=config['GOOGLE_API_KEY']
    )


def create_short_url(config, long_url):
    """
    Returns a dictionary containing API response params,
    including the shortened URL.
    """
    api = get_google_url_shortener(config)

    return api.url().insert(body={
        'longUrl': long_url,
    }).execute()


def get_twitter_client(config):
    """
    Returns authenticated Twitter client object.

    :param config: Dict of Twitter API settings
    """
    auth = tweepy.OAuthHandler(
        config['TWITTER_CONSUMER_KEY'],
        config['TWITTER_CONSUMER_SECRET']
    )
    auth.set_access_token(
        config['TWITTER_ACCESS_KEY'],
        config['TWITTER_ACCESS_SECRET']
    )

    return tweepy.API(auth)
