import os
import random
import time
import requests
import feedparser
from datetime import datetime
from requests_oauthlib import OAuth1
import re
import bs4
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
    "https://cointelegraph.com/rss",
    "https://bitcoinmagazine.com/feed",
    "https://cryptoslate.com/feed/",
    "https://www.newsbtc.com/feed/",
    "https://protos.com/feed/",
    "https://bitcoinist.com/feed",
    "https://cryptopotato.com/feed",
    "https://www.ccn.com/news/crypto-news/feeds/",
    "https://coinjournal.net/news/feed/",
    "https://cryptonews.com/news/feed",
    "https://web3wire.org/category/web3/feed/gn",
    "https://thenewscrypto.com/feed",
    "https://cointelegraph.com/rss"
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


def extract_article(entry):
    """Decide whether entry has full article, summary, or just headline. If headline only → scrape link."""

    raw_text = ""

    
    if hasattr(entry, "content") and entry.content:
        raw_text = entry.content[0].value.strip()

    
    elif hasattr(entry, "summary") and len(entry.summary.strip()) > 300:
        raw_text = entry.summary.strip()

   
    else:
        try:
            article_url = entry.link
            html = requests.get(article_url, timeout=10).text
            soup = bs4.BeautifulSoup(html, "html.parser")

            
            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            raw_text = " ".join(paragraphs[:5])  
        except Exception as e:
            print(f"⚠️ Failed to scrape {entry.link}: {e}")
            raw_text = entry.title + " — " + getattr(entry, "summary", "")

    return raw_text


def get_news():
    """Fetch crypto news: Try RSS → APIs → OpenAI fallback"""

    raw_text = None

    
    valid_feeds = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        if feed.entries:
            valid_feeds.append(feed)

    if valid_feeds:
        feed = random.choice(valid_feeds)
        latest_entries = sorted(
            feed.entries,
            key=lambda e: getattr(e, "published_parsed", datetime.utcnow()),
            reverse=True
        )[:5]
        entry = random.choice(latest_entries)
        raw_text = extract_article(entry)

    
    if not raw_text:
        api_sources = [
            f"https://cryptonewsapi.online/api/v1?tickers=BTC,ETH&items=1&token={os.getenv('CRYPTO_NEWS_API_KEY')}",
            f"https://api.thenewsapi.net/v1/news/top?categories=cryptocurrency&language=en&api_token={os.getenv('THENEWS_API_KEY')}",
            f"https://apitube.io/crypto/news?limit=1&apikey={os.getenv('APITUBE_API_KEY')}"
        ]

        for api_url in api_sources:
            try:
                res = requests.get(api_url, timeout=10).json()
                if "data" in res and res["data"]:
                    article = res["data"][0]
                    raw_text = article.get("title", "") + " — " + article.get("description", "")
                    break
                elif "articles" in res and res["articles"]:
                    article = res["articles"][0]
                    raw_text = article.get("title", "") + " — " + article.get("description", "")
                    break
            except Exception as e:
                print(f"⚠️ API failed: {api_url} ({e})")
                continue

    
    if not raw_text:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You generate crypto news."},
                    {"role": "user", "content": "One latest news related to crypto."}
                ],
                max_tokens=150
            )
            raw_text = response.choices[0].message.content.strip()
        except Exception as e:
            print("⚠️ OpenAI fallback failed:", e)

    
    if not raw_text:
        for delay in [300, 120, 600]:
            print(f"⏳ No news found, retrying in {delay//60} minutes...")
            time.sleep(delay)
            return get_news()
        return None  

   
    raw_text = raw_text.replace("\n", " ").strip()
    raw_text = re.sub(r"http\S+", "", raw_text)
    raw_text = " ".join(raw_text.split())

    prompt = """
    You are a helpful assistant. Summarize the following news:
    1. Remove all HTML tags and links
    2. Write it in simple humanly English
    3. Keep it concise with summaries of max 280 characters with meaningful content
    4. you can't exceed more than 280 chracters (max no of characters supported by the X posts)
    """

    response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You summarize crypto news."},
        {"role": "user", "content": f"{prompt}\n\n{raw_text}"}
    ],
    max_tokens=120
)

summary = response.choices[0].message.content.strip()



    # Hard enforce 280 chars max
    if len(summary) > 280:
        summary = summary[: summary.rfind(" ", 0, 280)]

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
    post_cycle = ["price", "news", "news", "news"]  
    cycle_index = 0  

    while True:  
        post_type = post_cycle[cycle_index]

        if post_type == "price":
            prices = get_prices()
            if prices.strip():
                content = f"Crypto Price Update:\n\n{prices}"
                post_tweet(content)
            else:
                print("⚠️ Price data not fetched, skipping price post...")

        elif post_type == "news":
            news = get_news()
            if news:
                post_tweet(news)
            else:
                print("⚠️ News not fetched, skipping news post...")

       
        cycle_index = (cycle_index + 1) % len(post_cycle)

        
        wait_time = random.randint(3600, 7000)
        print(f"⏳ Waiting {wait_time/60:.1f} minutes before next post...")
        time.sleep(wait_time)


if __name__ == "__main__":
    run_bot() 





