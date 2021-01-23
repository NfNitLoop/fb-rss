A quick and dirty script to sync an RSS feed into a [FeoBlog] blog.

[FeoBlog]: https://www.github.com/nfnitloop/feoblog


Requirements
------------

* `pip install pynacl toml base58 protobuf requests feedparser html2text`

Whoah, feedparser relies on [sgmllib3k] which seems to be unmaintained.
But feedparser seems to be the de facto RSS parser for python.

[sgmllib3k]: https://pypi.org/project/sgmllib3k/