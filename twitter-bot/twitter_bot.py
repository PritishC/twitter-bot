#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import json
import urllib2

import tweepy
from pymongo import MongoClient

import google_api
import local_settings
from decorators import retry

logging.basicConfig(
    filename='log.log', level=logging.INFO,
    format='Path %(pathname)s, Line %(lineno)d - %(asctime)s - %(levelname)s - %(message)s'
)


def get_twitter_client():
    """
    Returns authenticated Twitter client object
    """
    auth = tweepy.OAuthHandler(
        local_settings.TWITTER_CONSUMER_KEY,
        local_settings.TWITTER_CONSUMER_SECRET
    )
    auth.set_access_token(
        local_settings.TWITTER_ACCESS_KEY,
        local_settings.TWITTER_ACCESS_SECRET
    )

    return tweepy.API(auth)


@retry((urllib2.HTTPError,), tries=5, logger=logging)
def make_connections():
    """
    Make connections to various servers.
    Retry if any of the exceptions mentioned in the decorator
    is thrown.
    """
    mongo_client = MongoClient(local_settings.MONGO_URL)
    db = mongo_client.tweet_db
    tweets = db.tweets
    logging.info('Got mongo client connection')

    twitter = get_twitter_client()
    logging.info('Got Twitter client')

    jsondata = json.loads(urllib2.urlopen(
        local_settings.SUBREDDIT_URL).read()
    )
    logging.info('Obtained jsondata')

    return (jsondata, tweets, twitter)


@retry((Exception,), tries=3, logger=logging)
def shorten_url(long_url):
    """
    Try to shorten a long URL using Google API.
    """
    return (google_api.create_short_url(long_url))['id']


def run():
    """
    Main run script
    """
    jsondata, tweets, twitter = make_connections()

    if 'data' in jsondata and 'children' in jsondata['data']:
        posts = jsondata['data']['children']
        posts.reverse()

        for index, post in enumerate(posts):
            entry = post['data']
            postid = entry['id']
            score = entry['score']

            # Log permalink and URL
            logging.info('Permalink, URL: %s, %s' % (
                entry['permalink'], entry['url']
            ))

            res = tweets.find_one({'reddit_id': postid})

            if not res and score > 100:
                permalink = shorten_url(
                    'http://www.reddit.com' + entry['permalink']
                )
                url = shorten_url(
                    entry['url']
                )

                status = '%s [%s by %s]' % (
                    url, permalink, entry['author']
                )
                status = (
                    entry['title'][:(120 - len(status))] +
                    '... ' + status
                ).encode('utf-8')

                try:
                    twitter.update_status(status=status)
                except Exception as e:
                    logging.error(e)
                    continue

                logging.info('Status created: %s' % status)

                tweets.insert_one({
                    'reddit_id': postid,
                })


if __name__ == '__main__':
    run()
