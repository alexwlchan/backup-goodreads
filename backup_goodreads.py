#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""A script for backing up your Goodreads library.  Writes a backup to
`goodreads_backup.json`, or you can provide an alternative name as the first
command-line argument.

See the README for more details.

"""

from __future__ import print_function

import argparse
import itertools
import json

try:
    from datetime import timezone
except ImportError:  # Python 2
    from time import timezone

from datetime import datetime
from xml.etree import ElementTree as ET

import keyring
import requests


def identity(x):
    """Identity function."""
    return x.text


def convert_date(element):
    """Convert a date string from the Goodreads API into an ISO-8601 UTC
    string."""
    # We may get ``None`` if the API is missing any information for a
    # particular date field -- for example, the ``date_read`` field is
    # only filled in when a book is read.
    date_str = element.text
    if date_str is None:
        return None
    else:
        # In the API responses, dates are returned in the form
        # "Mon Oct 24 12:26:31 -0700 2016"
        date_obj = datetime.strptime(date_str, '%a %b %d %H:%M:%S %z %Y')
        return str(date_obj.astimezone(timezone.utc))


def convert_rating(element):
    """Convert a rating from the Goodreads API."""
    rating = element.text

    # The Goodreads API returns '0' to indicate an unrated book; make
    # this a proper null type.
    if rating == '0':
        return None
    else:
        return rating


def convert_authors(element):
    """Get the names of the authors for this book."""
    # The Goodreads API returns information about authors in an <authors>
    # element on the <review> element, in the following format:
    #
    #    <authors>
    #      <author>
    #        <id>1234</id>
    #        <name>John Smith</name>
    #        <snip>...</snip>
    #      </author>
    #      <author>
    #        <id>5678</id>
    #        <name>Jane Doe</name>
    #        <snip>...</snip>
    #      </author>
    #    </authors>
    #
    return [author.find('name').text for author in element.findall('author')]


def convert_shelves(element):
    """Get the names of all the shelves that hold this book."""
    # The shelves for a review are returned in the following format:
    #
    #    <shelves>
    #      <shelf name="read" exclusive="true"/>
    #      <shelf name="fiction" exclusive="false" review_shelf_id="1234"/>
    #    </shelves>
    #
    return [shelf.attrib['name'] for shelf in element.findall('shelf')]


def convert_page_count(element):
    try:
        return int(element.text)
    except TypeError:
        return None


def convert_body(element):
    return element.text.strip()


# Map from <review> tag name to pair (output key, converter)
REVIEW_TAGS = {
    'read_at':      ('date_read',   convert_date),
    'date_added':   ('date_added',  convert_date),
    'body':         ('review',      convert_body),
    'rating':       ('my_rating',   convert_rating),
    'shelves':      ('bookshelves', convert_shelves)
}

# Map from <book> tag name to pair (output key, converter)
BOOK_TAGS = {
    'authors':          ('authors',             convert_authors),
    'id':               ('book_id',             identity),
    'title':            ('title',               identity),
    'isbn':             ('isbn',                identity),
    'isbn13':           ('isbn13',              identity),
    'average_rating':   ('average_rating',      identity),
    'publisher':        ('publisher',           identity),
    'format':           ('binding',             identity),
    'num_pages':        ('page_count',          convert_page_count),
    'publication_year': ('publication_year',    identity),
    'published':        ('orig_year_published', identity),
}


def _get_data_from_goodreads_api(user_id, api_key, page_no):
    """Retrieve data about the reviews of a given user from the Goodreads API.
    Returns a Request object if successful, raises an Exception if not.

    :param user_id: The ID of the Goodreads user.
    :param api_key: The Goodreads API key.
    :param page_no: Which page of reviews to fetch.

    """
    # reviews.list (https://www.goodreads.com/api/index#reviews.list) gets
    # all the books on somebody's shelf.
    req = requests.get('https://www.goodreads.com/review/list.xml', params={
        'v': '2',
        'key': api_key,
        'id': user_id,
        'page': str(page_no),
    })
    if req.status_code != 200:
        raise Exception(
            'Unexpected error code from Goodreads API: %s\n'
            'Error message: %r' % (req.status_code, req.text)
        )
    return req


def _get_reviews_from_api(user_id, api_key):
    """Generates <review> elements from the API data.

    :param user_id: The ID of the Goodreads user.
    :param api_key: The Goodreads API key.

    """
    for page_no in itertools.count(1):
        req = _get_data_from_goodreads_api(
            user_id=user_id, api_key=api_key, page_no=page_no
        )
        reviews = ET.fromstring(req.text).find('reviews')
        for r in reviews:
            yield r
        if int(reviews.attrib['end']) >= int(reviews.attrib['total']):
            break


def get_reviews(user_id, api_key):
    """Generate reviews associated with a Goodreads user as dictionaries.

    :param user_id: The ID of the Goodreads user.
    :param api_key: The Goodreads API key.

    """
    for review in _get_reviews_from_api(user_id, api_key=api_key):
        data = {}

        def convert(element, tag_mapping):
            if element.tag in tag_mapping:
                key, converter = tag_mapping[element.tag]
                data[key] = converter(element)

        for review_elt in review:
            if review_elt.tag == 'book':
                for book_elt in review_elt:
                    convert(book_elt, BOOK_TAGS)
            else:
                convert(review_elt, REVIEW_TAGS)
        yield data


def read_config():
    """Returns configuration for using the script.

    Configuration is read from one of two places:
     1. The system keychain
     2. Command-line arguments

    Command-line arguments take precedence over keychain values.  If the
    keychain values are empty/missing, the command-line switches are required.

    """
    # Read some initial config from the system keychain: if this doesn't
    # exist, then we read it from command-line arguments.
    user_id = keyring.get_password('goodreads', 'user_id')
    api_key = keyring.get_password('goodreads', 'api_key')

    parser = argparse.ArgumentParser(
        description='A script to back up reviews from Goodreads.')

    parser.add_argument(
        '--output', default='goodreads_reviews.json',
        help='output path for the backup file')
    parser.add_argument(
        '--user-id', required=(user_id is None),
        help='Goodreads user ID')
    parser.add_argument(
        '--api-key', required=(api_key is None),
        help='Goodreads API key (https://www.goodreads.com/api/keys)')

    config = vars(parser.parse_args())

    if config['user_id'] is None:
        config['user_id'] = user_id
    if config['api_key'] is None:
        config['api_key'] = api_key

    return config


def main():
    """Parse the Goodreads API and save the reviews to disk."""
    cfg = read_config()
    reviews = get_reviews(user_id=cfg['user_id'], api_key=cfg['api_key'])
    json_str = json.dumps(list(reviews), indent=2, sort_keys=True)
    with open(cfg['output'], 'w', encoding='utf-8') as f:
        f.write(json_str)


if __name__ == '__main__':
    main()
