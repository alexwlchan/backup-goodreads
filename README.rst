backup-goodreads
================

This is a Python script for backing up your reviews from Goodreads.  It mimics
the `export function <https://www.goodreads.com/help/show/5-how-do-i-import-or-export-my-books>`_
provided by Goodreads, but in script form.

Installation
************

To install this script, use pip:

.. code-block:: console

   $ pip install -e git+git://github.com/alexwlchan/backup-goodreads.git#egg=backup_gooreads

or `pipsi <https://github.com/mitsuhiko/pipsi>`_:

.. code-block:: console

   $ pipsi install -e git+git://github.com/alexwlchan/backup-goodreads.git#egg=backup_gooreads

You can use Python 2.7 and Python 3.3+.

You need to set up three things before you can use the script::

1. Make your Goodreads reviews public.  This script only uses the basic API,
   not OAuth, and so private reviews can't be backed up.
2. Get your Goodreads user ID.  This is the 8-digit number in the URL of your
   profile page.  For example, if your user page was
   ``https://www.goodreads.com/user/show/12345678-john-smith``, then your
   user ID is ``12345678``.
3. Get a `developer API key <https://www.goodreads.com/api/keys>`_ from the
   Goodreads website.

Usage
*****

Run the script, passing your user ID and API key as command-line flags:

.. code-block:: console

   $ backup_goodreads --user-id=12345678 --api-key=abcdefg123

This will write your Goodreads reviews to ``goodreads_reviews.json``.

To see other options, run with the ``--help`` flag:

.. code-block:: console

   $ backup_goodreads --help

License
*******

This script is licensed under the MIT license.
