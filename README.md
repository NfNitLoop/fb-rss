A "quick and dirty" script to sync an RSS feed into a [FeoBlog] blog.

[FeoBlog]: https://www.github.com/nfnitloop/feoblog

You should use a unique userID for each feed, so that each can have its
own profile, and track post GUIDs separately.

If you've been granted access to a server (aka: you're a "server user"), you can create new IDs for your RSS feeds on the "Log In" page and follow them. That's enough to grant this script permission to sends posts to the server to show up in your feed.

Requirements
------------

* `pip install pynacl toml base58 protobuf requests feedparser html2text`

Whoah, feedparser relies on [sgmllib3k] which seems to be unmaintained.
But feedparser seems to be the de facto RSS parser for python.

[sgmllib3k]: https://pypi.org/project/sgmllib3k/