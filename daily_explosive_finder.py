import requests
import json
from datetime import datetime
import os

# -------------------- تنظیمات --------------------
TELEGRAM_TOKEN = '8499479656:AAEKULHx4fjg50fgSCF7ljLGgI7kcP6MX4U'
CHAT_ID = '8188301472'
# -------------------------------------------------

STATE_FILE = 'sent_coins.json'

def send_telegram(message):
    """ارسال پیام به تلگرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=10)
        print(f"📤 ارسال پیام: {message[:50]}...")
        return response
    except Exception as e:
        print(f"❌ خطا در ارسال پیام: {e}")
        return None

def load_sent():
    """بارگذاری لیست کوین‌های ارسال شده"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_sent(sent_set):
    """ذخیره لیست کوین‌های ارسال شده"""
    with open(STATE_FILE, 'w') as f:
        json.dump(list(sent_set), f)

def fetch_dexscreener():
    """گرفتن لیست کوین‌های سولانا از DexScreener"""
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        response = requests.get(url, timeout=15)
        data = response.json()
        pairs = data.get("pairs", [])
        print(f"📊 DexScreener: {len(pairs)} جفت‌ارز دریافت شد")
        return pairs
    except Exception as e:
        print(f"❌ خطا در دریافت از DexScreener: {e}")
        return []

def fetch_coingecko():
    """گرفتن لیست کوین‌های سولانا از CoinGecko"""
    try:
        url = (
            "https://api.coingecko.com/api/v3/coins/markets"
            "?vs_currency=usd"
            "&category=solana-ecosystem"
            "&order=volume_desc"
            "&per_page=50"
            "&page=1"
            "&sparkline=false"
            "&price_change_percentage=24h"
        )
        headers = {"User-Agent": "DailyBot/1.0"}
        response = requests.get(url, headers=headers, timeout=15)
        data = response.json()
        print(f"📊 CoinGecko: {len(data)} کوین دریافت شد")
        return data
    except Exception as e:
        print(f"❌ خطا در دریافت از CoinGecko: {e}")
        return []

def filter_potential(items):
    """فیلتر کوین‌های پتانسیل‌دار"""
    filtered = []
    
    for item in items:
        try:
            # تشخیص فرمت DexScreener
            if "chainId" in item and item.get("chainId") == "solana":
                symbol = item.get("baseToken", {}).get("symbol", "N/A")
                name = item.get("baseToken", {}).get("name", "N/A")
                address = item.get("baseToken", {}).get("address", "N/A")
                
                volume_h24 = float(item.get("volume", {}).get("h24", 0))
                mc = float(item.get("fdv", 0))  # Fully Diluted Valuation
                liquidity = float(item.get("liquidity", {}).get("usd", 0))
                
                # سن کوین
                age_str = item.get("pairCreatedAt", 0)
                age_h = 999
                if age_str:
                    import time
                    age_seconds = time.time() - (age_str / 1000)
                    age_h = age_seconds / 3600
                
                change_24h = float(item.get("priceChange", {}).get("h24", 0))
                txns_24h = item.get("txns", {}).get("h24", {}).get("buys", 0)
                link = f"https://dexscreener.com/solana/{item.get('pairAddress', '')}"
                
                # فیلترهای اصلی
                if (volume_h24 >= 100000 and 
                    liquidity >= 50000 and 
                    age_h <= 72 and
                    (change_24h > 20 or volume_h24 > 300000)):
                    
                    filtered.append({
                        "source": "DexScreener",
                        "name": name,
                        "symbol": symbol,
                        "address": address,
                        "mc": mc,
                        "volume": volume_h24,
                        "liquidity": liquidity,
                        "age": age_h,
                        "change": change_24h,
                        "txns": txns_24h,
                        "link": link
                    })
            
            # فرمت CoinGecko
            elif "id" in item and "symbol" in item:
                symbol = item.get("symbol", "N/A").upper()
                name = item.get("name", "N/A")
                volume_h24 = float(item.get("total_volume", 0))
                mc = float(item.get("market_cap", 0))
                change_24h = float(item.get("price_change_percentage_24h", 0))
                link = f"https://www.coingecko.com/en/coins/{item.get('id', '')}"
                
                if (volume_h24 >= 200000 and 
                    mc <= 20000000 and 
                    change_24h > 15):
                    
                    filtered.append({
                        "source": "CoinGecko",
                        "name": name,
                        "symbol": symbol,
                        "address": item.get("id", "N/A"),
                        "mc": mc,
                        "volume": volume_h24,
                        "liquidity": 0,
                        "age": 24,
                        "change": change_24h,
                        "txns": 0,
                        "link": link
                    })
        except Exception as e:
            continue
    
    # مرتب‌سازی بر اساس حجم و رشد
    filtered.sort(key=lambda x: (-x["volume"], -x["change"]))
    print(f"🎯 {len(filtered)} کوین پس از فیلتر باقی ماند")
    return filtered[:8]  # حداکثر ۸ تا

def format_message(coins):
    """قالب‌بندی پیام برای تلگرام"""
    if not coins:
        return "😴 امروز کوین پتانسیل‌داری پیدا نشد!\n\nفردا دوباره امتحان کن."
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    msg = "🚀 **لیست روزانه کوین‌های پتانسیل‌دار Solana** 🚀\n"
    msg += f"📆 {now} UTC\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, coin in enumerate(coins[:5], 1):  # حداکثر ۵ تا
        msg += f"**{i}. {coin['name']} ({coin['symbol']})**\n"
        msg += f"💰 MC: `${coin['mc']:,.0f}`\n" if coin['mc'] > 0 else ""
        msg += f"📊 Vol 24h: `${coin['volume']:,.0f}`\n"
        msg += f"💧 Liq: `${coin['liquidity']:,.0f}`\n" if coin['liquidity'] > 0 else ""
        msg += f"⏰ سن: `{int(coin['age'])}h`\n" if coin['age'] < 999 else ""
        msg += f"📈 رشد 24h: **{coin['change']:+.1f}%**\n"
        msg += f"🔄 تراکنش: `{coin['txns']}`\n" if coin['txns'] > 0 else ""
        msg += f"🔗 [مشاهده]({coin['link']})\n"
        msg += f"📎 منبع: `{coin['source']}`\n\n"
    
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "⚠️ **DYOR** - این فقط یک ایده اولیه است!\n"
    msg += "🤖 ربات پتانسیل‌یاب Solana"
    
    return msg

def main():
    print("🚀 شروع اجرای ربات پتانسیل‌یاب Solana...")
    print(f"✅ توکن: {TELEGRAM_TOKEN[:10]}...")
    print(f"✅ چت آیدی: {CHAT_ID}")
    
    # دریافت داده از منابع
    dexscreener_pairs = fetch_dexscreener()
    coingecko_coins = fetch_coingecko()
    
    # ترکیب و فیلتر
    all_items = dexscreener_pairs + coingecko_coins
    print(f"📦 کل آیتم‌های دریافتی: {len(all_items)}")
    
    top_coins = filter_potential(all_items)
    
    # ارسال پیام
    message = format_message(top_coins)
    send_telegram(message)
    
    # ذخیره برای دفعه بعد
    if top_coins:
        sent = load_sent()
        new_sent = {f"{c['symbol']}_{c['address'][:8]}" for c in top_coins if c['address'] != 'N/A'}
        save_sent(sent | new_sent)
    
    print("✅ اجرا پایان یافت")

if __name__ == "__main__":
    main()
