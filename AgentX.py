import os
import random
import time
import requests
import feedparser
from datetime import datetime



X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

COINS = ["bitcoin", "ethereum", "solana", "ripple", "binancecoin", "tron"]

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
    "https://protos.com/feed/"
]



def get_prices():
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(COINS)}&vs_currencies=usd"
    res = requests.get(url).json()
    lines = []
    for coin in COINS:
        price = res[coin]["usd"]
        lines.append(f"{coin.capitalize()}: ${price:,.2f}")
    return "\n".join(lines)


# ====== NEWS FETCHING ======
def get_news():
    feed_url = random.choice(RSS_FEEDS)
    feed = feedparser.parse(feed_url)
    if not feed.entries:
        return None
    entry = random.choice(feed.entries)
    title = entry.title
    summary = getattr(entry, "summary", "")
    text = f"{title} — {summary}"
    text = text.replace("\n", " ").strip()
    if len(text) > 280:
        text = text[:277] + "..."
    return text



def post_tweet(content):
    url = "https://api.twitter.com/2/tweets"
    headers = {
        "Authorization": f"Bearer {X_BEARER_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"text": content}
    response = requests.post(url, headers=headers, json=payload)

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
            content = f"📊 Crypto Price Update:\n{prices}"
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
