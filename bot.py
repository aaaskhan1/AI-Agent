import os
import random
import time
import requests
import feedparser
import signal
import sys
import logging
from datetime import datetime
from requests_oauthlib import OAuth1
import re
import bs4
from openai import OpenAI

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_flag = False

def signal_handler(signum, frame):
    global shutdown_flag
    logger.info("Shutdown signal received. Stopping bot gracefully...")
    shutdown_flag = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Environment variables
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validate required environment variables
required_vars = [X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, OPENAI_API_KEY]
if not all(required_vars):
    logger.error("Missing required environment variables")
    sys.exit(1)

auth = OAuth1(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
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
    "https://coinjournal.net/news/feed/",
    "https://cryptonews.com/news/feed",
    "https://thenewscrypto.com/feed",
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_prices():
    """Fetch cryptocurrency prices with error handling"""
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(COINS.keys())}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        res = response.json()
        lines = []
        for coin_id, symbol in COINS.items():
            if coin_id in res:
                price = res[coin_id]["usd"]
                lines.append(f"{symbol}: ${price:,.2f}")
        
        return "\n".join(lines) if lines else None
    except Exception as e:
        logger.error(f"Failed to fetch prices: {e}")
        return None

def extract_article(entry):
    """Extract article content with improved error handling"""
    raw_text = ""
    
    try:
        # Try content first
        if hasattr(entry, "content") and entry.content:
            raw_text = entry.content[0].value.strip()
        # Then summary if long enough
        elif hasattr(entry, "summary") and len(entry.summary.strip()) > 300:
            raw_text = entry.summary.strip()
        # Finally scrape the article
        else:
            article_url = entry.link
            response = requests.get(article_url, timeout=10, headers=HEADERS)
            response.raise_for_status()
            
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            raw_text = " ".join(paragraphs[:5])
            
    except Exception as e:
        logger.warning(f"Failed to extract article from {entry.link}: {e}")
        raw_text = entry.title + " — " + getattr(entry, "summary", "")
    
    return raw_text

def get_news(max_retries=3):
    """Fetch crypto news with improved retry logic"""
    for attempt in range(max_retries):
        try:
            # Try RSS feeds first
            valid_feeds = []
            for url in random.sample(RSS_FEEDS, min(5, len(RSS_FEEDS))):  # Only try 5 random feeds
                try:
                    feed = feedparser.parse(url)
                    if feed.entries:
                        valid_feeds.append(feed)
                        break  # Stop after finding one valid feed
                except Exception as e:
                    logger.warning(f"Failed to parse RSS feed {url}: {e}")
                    continue
            
            if valid_feeds:
                feed = random.choice(valid_feeds)
                latest_entries = sorted(
                    feed.entries,
                    key=lambda e: getattr(e, "published_parsed", datetime.now().timetuple()),
                    reverse=True
                )[:5]
                entry = random.choice(latest_entries)
                raw_text = extract_article(entry)
                
                if raw_text and len(raw_text.strip()) > 50:  # Ensure meaningful content
                    return process_news_content(raw_text)
            
            # Fallback to OpenAI if RSS fails
            logger.info("RSS feeds failed, trying OpenAI fallback...")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Generate a realistic crypto news headline and brief summary."},
                    {"role": "user", "content": "Create one recent cryptocurrency news story (not investment advice)."}
                ],
                max_tokens=150
            )
            raw_text = response.choices[0].message.content.strip()
            return process_news_content(raw_text)
            
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed to get news: {e}")
            if attempt < max_retries - 1:
                time.sleep(30 * (attempt + 1))  # Exponential backoff
            
    logger.error("All attempts to fetch news failed")
    return None

def process_news_content(raw_text):
    """Process and clean news content"""
    try:
        # Clean the text
        raw_text = re.sub(r"http\S+", "", raw_text)  # Remove URLs
        raw_text = re.sub(r"<[^>]+>", "", raw_text)  # Remove HTML tags
        raw_text = " ".join(raw_text.split())  # Normalize whitespace
        
        # Summarize with OpenAI
        prompt = """Summarize this crypto news in exactly one tweet (max 280 characters):
        - Remove HTML tags and links
        - Use clear, engaging language
        - Include key facts only
        - No investment advice"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You create concise crypto news summaries."},
                {"role": "user", "content": f"{prompt}\n\n{raw_text}"}
            ],
            max_tokens=100
        )
        
        summary = response.choices[0].message.content.strip()
        
        # Ensure 280 character limit with better truncation
        if len(summary) > 280:
            summary = summary[:277] + "..."
            
        return summary
        
    except Exception as e:
        logger.error(f"Failed to process news content: {e}")
        return None

def post_tweet(content, max_retries=3):
    """Post tweet with retry logic"""
    for attempt in range(max_retries):
        try:
            url = "https://api.twitter.com/2/tweets"
            payload = {"text": content}
            response = requests.post(url, auth=auth, json=payload, timeout=10)
            
            if response.status_code == 201:
                logger.info(f"✅ Posted: {content[:50]}...")
                return True
            elif response.status_code == 429:  # Rate limited
                logger.warning("Rate limited, waiting before retry...")
                time.sleep(900)  # Wait 15 minutes for rate limit reset
            else:
                logger.error(f"Tweet failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} to post tweet failed: {e}")
            
        if attempt < max_retries - 1:
            time.sleep(60 * (attempt + 1))  # Wait before retry
    
    return False

def run_bot():
    """Main bot loop with improved error handling"""
    post_cycle = ["price", "news", "news", "news"]
    cycle_index = 0
    consecutive_failures = 0
    max_consecutive_failures = 5
    
    logger.info("🚀 Crypto bot started!")
    
    while not shutdown_flag:
        try:
            post_type = post_cycle[cycle_index]
            success = False
            
            if post_type == "price":
                logger.info("Fetching price update...")
                prices = get_prices()
                if prices:
                    content = f"💰 Crypto Price Update:\n\n{prices}\n\n#Crypto #Prices"
                    success = post_tweet(content)
                else:
                    logger.warning("Price data not available, skipping...")
                    
            elif post_type == "news":
                logger.info("Fetching crypto news...")
                news = get_news()
                if news:
                    content = f"📰 {news}\n\n#CryptoNews"
                    success = post_tweet(content)
                else:
                    logger.warning("News not available, skipping...")
            
            # Track consecutive failures
            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                
            if consecutive_failures >= max_consecutive_failures:
                logger.error(f"Too many consecutive failures ({consecutive_failures}). Stopping bot.")
                break
            
            # Move to next in cycle
            cycle_index = (cycle_index + 1) % len(post_cycle)
            
            # Wait with random interval (1-2 hours)
            if not shutdown_flag:
                wait_time = random.randint(3600, 7200)
                logger.info(f"⏳ Waiting {wait_time/60:.1f} minutes before next post...")
                
                # Sleep in smaller chunks to allow graceful shutdown
                for _ in range(wait_time // 60):
                    if shutdown_flag:
                        break
                    time.sleep(60)
                    
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            consecutive_failures += 1
            time.sleep(300)  # Wait 5 minutes before retrying
    
    logger.info("Bot stopped gracefully.")

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
