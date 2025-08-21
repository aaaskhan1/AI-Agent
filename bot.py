import os
import random
import time
import requests
import feedparser
from datetime import datetime
from requests_oauthlib import OAuth1
import re
from openai import OpenAI


X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

auth = OAuth1(
    X_API_KEY,
    X_API_SECRET,
    X_ACCESS_TOKEN,
    X_ACCESS_SECRET
)

client = OpenAI(api_key=OPENAI_API_KEY)


COINS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "ripple": "XRP",
    "binancecoin": "BNB",
    "tron": "TRX",
    "sui": "SUI",
    "hyperliquid": "HYPE",
    "cardano": "ADA",
    "chainlink": "LINK",
    "avalanche": "AVAX",
    "toncoin": "TON",
    "polkadot": "DOT",
    "monero": "XMR",
    "litecoin": "LTC"
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


def get_news():
    """Fetch and summarize news using OpenAI"""
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
    raw_text = f"{entry.title} — {getattr(entry, 'summary', '')}"

    raw_text = raw_text.replace("\n", " ").strip()
    raw_text = re.sub(r"http\S+", "", raw_text)
    raw_text = " ".join(raw_text.split())

    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You summarize crypto news."},
            {"role": "user", "content": f"Summarize this in simple English & humanly style, max 280 characters:\n\n{raw_text}"}
        ],
        max_tokens=100
    )

    summary = response.choices[0].message.content.strip()

    
    if len(summary) > 280:
        summary = summary[:277] + "..."

    return summary


def post_tweet(content):
    url = "https://api.twitter.com/2/tweets"
    payload = {"text": content}
    response = requests.post(url, auth=auth, json=payload)

    if response.status_code == 201:
        print("✅ Posted:", content)
    else:
        print("❌ Error posting:", response.status_code, response.text)


def run_bot():
    posts_today = 0
    max_posts = 14
    last_type = "news"

    while posts_today < max_posts:
        if last_type == "news":
            prices = get_prices()
            if prices.strip():
                content = f"Crypto Price Update:\n\n{prices}"
                post_tweet(content)
            else:
                print("⚠️ Price data not fetched, skipping price post...")
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
