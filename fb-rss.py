"""
Quick and dirty script to copy RSS feeds into FeoBlog.
"""

from datetime import datetime, timezone
from calendar import timegm
import traceback

import feedparser
import html2text
import toml

from feoblog import Client, UserID, Signature, Password
from feoblog.protos import Item, Profile, Post, ItemType

def main(args):
    with open("config.toml") as f:
        config = toml.load(f)
    
    server = config["server_url"]
    client = Client(base_url=server)

    num_errors = 0

    for feed in config["feeds"]:
        info = FeedInfo.from_config(feed)

        try: 
            sync_feed(client=client, feed=info)
        except Exception as e:
            num_errors += 1
            print(f"Error fetching {info.rss_url}:")
            traceback.print_exc()
            continue

class FeedInfo:
    @staticmethod
    def from_config(config):
        feed = FeedInfo()

        feed.name = config.get("name", "")
        feed.rss_url = config["rss_url"]
        feed.user_id = UserID.from_string(config["user_id"])
        feed.password = Password.from_string(config["password"])
        if not feed.password.matches_user(feed.user_id):
            raise f"Password incorrect for user {user_id}"

        return feed
    
    """ Generate a default profile for this feed."""
    def default_profile(self):
        item = Item()
        item.timestamp_ms_utc = fb_timestamp(datetime.now(tz=timezone.utc))
        profile = item.profile
        profile.display_name = self.name
        profile.about = "\n".join([
            "This account contains items from the following RSS feed:  ",
            f"<{self.rss_url}>"
        ])

        return item

def debug(*argc):
    print(*argc)
    return


def sync_feed(client: Client, feed: FeedInfo):
    debug("Syncing", feed.name)
    has_items = False
    # The timestamp of the last item that was saved to the blog.
    latest_timestamp = 0

    # Are there already posts? If so, what's the latest one?
    for item in client.get_user_items(feed.user_id):
        has_items = True
        if item.item_type != ItemType.POST:
            continue
        else:
            latest_timestamp = item.timestamp_ms_utc
            break

    debug("latest_timestamp", latest_timestamp)

    # Create a default profile for this ID.
    # This is handy in that it will check whether we're allowed to
    # post to the server before we even begin.
    if not has_items:
        item = feed.default_profile()
        item_bytes = item.SerializeToString()
        signature = feed.password.sign(item_bytes)
        client.put_item(feed.user_id, signature, item_bytes)

    result = feedparser.parse(feed.rss_url)
    posts = [Post.from_entry(e) for e in result.entries]

    # Send posts oldest first in case we fail part-way, so we can resume:
    posts.sort(key=lambda p: p.timestamp)


    current_time = now()
    for post in posts:
        debug(post.timestamp, post.title)
        if post.timestamp <= latest_timestamp:
            debug("skipping post")
            continue
        if post.timestamp > current_time:
            debug("Refusing to sync post w/ future time:")
            debug(post.timestmap, post.title)
            continue
        
        item_bytes = post.as_item().SerializeToString()
        sig = feed.password.sign(item_bytes)
        client.put_item(feed.user_id, sig, item_bytes)
    

h2t = html2text.HTML2Text()
# Wrapping links breaks them. 😣
h2t.wrap_links = False
h2t.wrap_list_items = False

class Post:
    @staticmethod
    def from_entry(entry):
        p = Post()
        p.title = entry.title
        p.link = entry.link
        p.description = entry.description
        p.timestamp = parsed_time_to_ts(entry.published_parsed)
        return p

    
    def as_item(self) -> Item:
        item = Item()
        item.timestamp_ms_utc = self.timestamp

        p = item.post
        p.title = self.title

        body = h2t.handle(self.description)
        if self.link not in body:
            body += f"  \n<{self.link}>"
        
        p.body = body

        return item

def fb_timestamp(dt: datetime) -> int:
    """Returns the milliseconds since unix epoch, in utc timezone."""
    if not dt.tzinfo:
        raise Exception("Refusing to work with naive datetimes")

    return int(dt.timestamp() * 1000)


def parsed_time_to_ts(time_struct) -> int:
    # feedparser gives us a time_struct in UTC. Odd. OK.
    timestamp = timegm(time_struct)
    return int(timestamp * 1000)

def now() -> int:
    now = datetime.now(tz=timezone.utc)
    return fb_timestamp(now)


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])