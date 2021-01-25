"""
Quick and dirty script to copy RSS feeds into FeoBlog.
"""

import argparse
from calendar import timegm
from contextlib import contextmanager
from datetime import datetime, timezone
import os
import traceback

import feedparser
import html2text
import toml

from feoblog import Client, UserID, Signature, Password
from feoblog.protos import Item, Profile, Post, ItemType

def main(args):

    options = parse_args(args)

    global debug_enabled
    if options.debug:
        debug_enabled = True

    with open(options.config_file) as f:
        config = toml.load(f)

    cache_dir = config.get("cache_dir", ".")
    
    server = config["server_url"]
    client = Client(base_url=server)

    num_errors = 0

    for feed in config["feeds"]:
        info = FeedInfo.from_config(feed)

        try:
            guid_cache = GUIDCache(cache_dir, cache_name=info.user_id.string)
            with guid_cache.opened():
                sync_feed(client=client, feed=info, guid_cache=guid_cache)
        except Exception as e:
            num_errors += 1
            print(f"Error fetching {info.rss_url}:")
            traceback.print_exc()
            continue


def parse_args(args):
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--config-file",
        default="config.toml",
        help="The configuration file which lists RSS feeds to sync.",
    )

    parser.add_argument(
        "--debug",
        default=False,
        action="store_true",
        help="Enable extra verbose output.",
    )
    
    return parser.parse_args(args)



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

debug_enabled = False

def debug(*argc):
    if not debug_enabled:
        return
    print(*argc)


def sync_feed(client: Client, feed: FeedInfo, guid_cache: "GUIDCache"):
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
        debug()
        debug(post.timestamp, post.title)
        debug("guid", post.guid)
        if post.timestamp <= latest_timestamp:
            debug("skipping old post")
            continue
        if post.timestamp > current_time:
            debug("Refusing to sync post w/ future time:")
            continue
        if post.guid in guid_cache:
            debug("Skipping post with non-unique GUID", post.guid)
            continue

        item_bytes = post.as_item().SerializeToString()
        sig = feed.password.sign(item_bytes)
        client.put_item(feed.user_id, sig, item_bytes)
        guid_cache.add(post.guid)
    

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
        p.guid = entry.guid
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

class GUIDCache:
    """
    RSS provides a string GUID for each post to help clients de-dupe posts which may otherwise change over time.
    This class will load and store those GUIDs in a plain text file to provide functionality to dedupe.
    """

    def __init__(self, cache_dir, cache_name, max_guids=500):
        self.__filename = os.path.join(cache_dir, f"{cache_name}.guids")
        self.max_guids = max_guids

        # Maintain both an ordered list and an unordered set (for fast lookup)
        self.__guid_list = []
        self.__guid_set = set()

    @contextmanager
    def opened(self):
        """
        use:
        with cache.opened: 
            # ...

        Loads caches from the cache file, making them available for `in`.
        After execution, saves the cache back to the same file.
        """
        self.__guid_list = []
        self.__guid_set = set()
        if not os.path.exists(self.__filename):
            # Save an empty file to make sure we can write before we begin:
            self.__save()
        
        self.__load()
        try:
            yield()
        finally:
            # Always try saving any new GUIDs that we may have added:
            self.__save()
    
    def __contains__(self, guid):
        if guid == "":
            debug("Received an empty guid. Skipping it.")
            # return True so that we *don't* save this item. Empty GUIDs can't be deduped.
            return True

        return guid in self.__guid_set

    def add(self, guid):
        if guid in self:
            return

        if guid == "":
            debug("Refusing to add empty guid to cache")
            return

        if "\n" in guid:
            debug("Refusing to add a GUID that contains a newline.")
            return

        self.__guid_list.append(guid)
        self.__guid_set.add(guid)
        

    def __save(self): 
        with open(self.__filename, "w", encoding="utf-8") as f:
            guids = self.__guid_list[-self.max_guids:]
            for guid in guids:
                f.write(guid)
                f.write("\n")

    def __load(self): 
        with open(self.__filename, "r", encoding="utf-8") as f:
            lines = (
                line[:-1]  # remove \n
                for line in f
            )
            self.__guid_list = [
                line
                for line in lines
                if line != ""
            ][-self.max_guids:]
            self.__guid_set = set(self.__guid_list)


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])