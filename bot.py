import os
import random
import time
import requests
import feedparser
from datetime import datetime
from requests_oauthlib import OAuth1
from bs4 import BeautifulSoup


X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

auth = OAuth1(
    X_API_KEY,
    X_API_SECRET,
    X_ACCESS_TOKEN,
    X_ACCESS_SECRET
)


COINS = {
    "Bitcoin": "BTC",
    "Ethereum": "ETH",
    "Solana": "SOL",
    "Ripple": "XRP",
    "Binancecoin": "BNB",
    "Tron": "TRX",
    "Sui": "SUI",
    "Hyperliquid": "HYPE",
    "Cardano": "ADA",
    "Chainlink": "LINK",
    "Avalanche": "AVAX",
    "Toncoin": "TON",
    "Polkadot": "DOT",
    "Monero": "XMR",
    "Litecoin": "LTC"
}


RSS_FEEDS = [
    "https://decrypt.co/feed",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://www.theblock.co/rss",
    "https://cointelegraph.com/rss",
    "https://bitcoinmagazine.com/feed",
    "https://cryptoslate.com/feed/",
    "https://beincrypto.com/feed/",
    "https://www.newsbtc.com/feed/",
    "https://ambcrypto.com/feed/",
    "https://u.today/rss",
    "https://newsletter.banklesshq.com/feed",
    "https://blockworks.co/feed",
    "https://www.dlnews.com/rss",
    "https://protos.com/feed/",
    "https://bitcoinist.com/feed",
    "https://cryptopotato.com/feed",
    "https://cryptobriefing.com/feed",
    "https://crypto.news/feed",
    "https://www.ccn.com/news/crypto-news/feeds/",
    "https://coinjournal.net/news/feed/",
    "https://cryptonews.com/news/feed",
    "https://web3wire.org/category/web3/feed/gn",
    "https://blog.chain.link/feed",
    "https://avc.com/category/web3/feed",
    "https://web3daily.co/articles?format=rss",
    "https://thenewscrypto.com/feed",
    "https://www.dlnews.com/feed/regulation",
    "https://www.coindesk.com/policy/rss",
    "https://blockworks.co/feed/regulation",
    "https://feeds.reuters.com/reuters/cryptocurrencyNews",
    "https://www.ft.com/crypto?format=rss",
    "https://www.bloomberg.com/feed/podcast/crypto.rss",
    "https://blogs.imf.org/feed/",
    "https://www.weforum.org/agenda/archive/blockchain.rss"
]


def get_prices():
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(COINS.keys())}&vs_currencies=usd"
    res = requests.get(url).json()
    lines = []
    for coin_id, symbol in COINS.items():
        if coin_id in res:
            price = res[coin_id]["usd"]
            lines.append(f"{symbol}: ${price:,.2f}")
    return "\n".join(lines)


def clean_html(raw_html):
    """Remove HTML tags from feed summaries"""
    return BeautifulSoup(raw_html, "html.parser").get_text()



import re

def get_news():
    """Fetch latest crypto news (random from latest entries, no links)"""
    feed_url = random.choice(RSS_FEEDS)
    feed = feedparser.parse(feed_url)

    if not feed.entries:
        return None

    
    latest_entries = sorted(
        feed.entries,
        key=lambda e: getattr(e, "published_parsed", datetime.utcnow()),
        reverse=True
    )[:5]

    entry = random.choice(latest_entries)
    title = entry.title
    summary = getattr(entry, "summary", "")

    text = f"{title} — {summary}"
    text = text.replace("\n", " ").strip()

    
    text = re.sub(r"http\S+", "", text)

    
    text = " ".join(text.split())

    if len(text) > 280:
        text = text[:277] + "..."

    return text




def post_tweet(content):
    url = "https://api.twitter.com/2/tweets"
    payload = {"text": content}
    response = requests.post(url, auth=auth, json=payload)

    if response.status_code == 201:
        print("Posted:", content)
    else:
        print("Error posting:", response.status_code, response.text)


def run_bot():
    """Run alternating posts (price + news)"""
    posts_today = 0
    max_posts = 14
    last_type = "news"

    while posts_today < max_posts:
        if last_type == "news":
            prices = get_prices()
            content = f"Crypto Price Update:\n{prices}"
            post_tweet(content)
            last_type = "price"
        else:
            news = get_news()
            if news:
                post_tweet(news)
            last_type = "news"

        posts_today += 1
        wait_time = random.randint(3600, 7200) 
        print(f"⏳ Waiting {wait_time/60:.1f} minutes before next post...")
        time.sleep(wait_time)


if __name__ == "__main__":
    run_bot()
