#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import logging.handlers
import json
import urllib2
import argparse
import os

from pymongo import MongoClient

import apis
from decorators import retry

if os.environ.get('SYSLOG', None):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.handlers.SysLogHandler(
        facility=logging.handlers.SysLogHandler.LOG_DAEMON,
        address="/dev/log"
    )
    formatter = logging.Formatter(
        'Path %(pathname)s, Line %(lineno)d - %(asctime)s - %(levelname)s - %(message)s'
    )
    handler.formatter = formatter
    logger.addHandler(handler)
else:
    logging.basicConfig(
        filename='log.log', level=logging.INFO,
        format='Path %(pathname)s, Line %(lineno)d - %(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging


class TwitterBot(object):
    """
    Reddit2Twitter Bot
    """
    def __init__(self, *args, **kwargs):
        twitter_keys = [
            'TWITTER_CONSUMER_KEY', 'TWITTER_CONSUMER_SECRET',
            'TWITTER_ACCESS_KEY', 'TWITTER_ACCESS_SECRET'
        ]
        google_keys = ['GOOGLE_API_KEY']

        for key in twitter_keys + google_keys:
            assert os.environ[key]

        # Set configs
        self.twitter_config = {
            key: os.environ[key] for key in twitter_keys
        }
        self.google_config = {
            key: os.environ[key] for key in google_keys
        }

        # Set URLs
        subs = kwargs['subreddits'].split(';')
        self.subreddits = {}

        for fragment in subs:
            sub, limit = fragment.split(',')
            self.subreddits[sub] = limit
        self.mongo_url = kwargs['mongo_url']

    @retry((Exception,), tries=2, logger=logger)
    def make_connections(self):
        """
        Make connections to various servers.
        Retry if any of the exceptions mentioned in the decorator
        is thrown.
        """
        mongo_client = MongoClient(self.mongo_url)
        db = mongo_client.tweet_db
        tweets = db.tweets
        logger.info('Got mongo client connection')

        twitter = apis.get_twitter_client(self.twitter_config)
        logger.info('Got Twitter client')

        return (tweets, twitter)

    @retry((urllib2.HTTPError), tries=5, logger=logger)
    def get_subreddit_data(self):
        """
        Gets data from reddit's JSON API and proceeds to
        stash them into a dictionary.
        """
        res = {}

        for sub, limit in self.subreddits.iteritems():
            url = (
                'http://reddit.com/r/' + sub +
                '.json?limit=' + limit
            )
            res[sub] = json.loads(urllib2.urlopen(url).read())

        return res

    @retry((Exception,), tries=3, logger=logger)
    def shorten_url(self, long_url):
        """
        Try to shorten a long URL using Google API.
        """
        return (apis.create_short_url(self.google_config, long_url))['id']

    def run(self):
        """
        Main run script
        """
        tweets, twitter = self.make_connections()
        data = self.get_subreddit_data()

        for key in data:
            jsondata = data[key]
            logger.info("On subreddit url %s" % key)

            if 'data' in jsondata and 'children' in jsondata['data']:
                posts = jsondata['data']['children']
                posts.reverse()

                for index, post in enumerate(posts):
                    entry = post['data']
                    postid = entry['id']
                    score = entry['score']
                    num_comments = entry['num_comments']

                    # Log permalink and URL
                    logger.info('Permalink, URL: %s, %s' % (
                        entry['permalink'], entry['url']
                    ))

                    res = tweets.find_one({'reddit_id': key + '/' + postid})

                    if not res and (score > 100 or num_comments >= 5):
                        permalink = self.shorten_url(
                            'http://www.reddit.com' + entry['permalink']
                        )
                        url = self.shorten_url(
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
                            logger.error(e)
                            continue

                        logger.info('Status created: %s' % status)

                        tweets.insert_one({
                            'reddit_id': key + '/' + postid,
                        })
                    else:
                        logger.info(
                            "Post %s with score %d and comment count %d was"
                            " either already in DB or did not satisfy"
                            " criteria" %
                            (postid, score, num_comments)
                        )
            else:
                logger.info("Skipping subredit url %s as no data" % key)


parser = argparse.ArgumentParser(description='Reddit2Twitter Bot')
parser.add_argument(
    '--subreddits', required=True,
    help='String of the form "sub1,limit1;sub2,limit2..."'
)
parser.add_argument(
    '--mongo-url', required=True,
    help='MongoDB URL'
)
args = parser.parse_args()

TwitterBot(subreddits=args.subreddits, mongo_url=args.mongo_url).run()
