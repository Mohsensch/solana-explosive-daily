import requests
import json
from datetime import datetime
import os
from moralis import sol_api

# -------------------- تنظیمات --------------------
TELEGRAM_TOKEN = '8499479656:AAEKULHx4fjg50fgSCF7ljLGgI7kcP6MX4U'
CHAT_ID = '8188301472'
MORALIS_API_KEY = os.environ.get('MORALIS_API_KEY', '')
# -------------------------------------------------
STATE_FILE = 'sent_coins.json'

def send_telegram(message):
    """ارسال پیام به تلگرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        response = requests.post(url, json=payload, timeout=10)
        print(f"📤 ارسال پیام: {message[:50]}...")
        return response
    except Exception as e:
        print(f"❌ خطا در ارسال پیام: {e}")
        return None

def fetch_moralis_tokens():
    """دریافت توکن‌های سولانا با فیلتر رشد ۲۴ ساعته"""
    try:
        print("📡 دریافت داده از Moralis Filtered Tokens API...")
       
        params = {
            "chain": "solana",
            # timeframe حذف شد → داده‌های پیش‌فرض یا کلی‌تر
            "order": "price_change_percentage_desc",
            "min_price_change": 5,       # حداقل ۵٪ رشد (معمولاً ۲۴ ساعته)
            "min_volume": 50000,         # حداقل حجم ۵۰K
            "min_liquidity": 30000,      # حداقل نقدینگی ۳۰K
            "limit": 30
        }
       
        result = sol_api.token.get_filtered_tokens(
            api_key=MORALIS_API_KEY,
            params=params
        )
       
        tokens = result.get('result', [])
        print(f"✅ {len(tokens)} توکن با روند صعودی دریافت شد")
        return tokens
       
    except Exception as e:
        print(f"❌ خطا در Moralis API: {e}")
        return []

def check_token_security(token_address):
    """بررسی امنیت توکن با GoPlus API"""
    try:
        url = f"https://api.gopluslabs.io/api/v1/token_security/101?contract_addresses={token_address}"
        response = requests.get(url, timeout=10)
        data = response.json()
       
        if data.get('code') != 1:
            return None
       
        result = data['result'].get(token_address, {})
       
        score = 100
        reasons = []
       
        if result.get('mint_authority'):
            if result['mint_authority'] != '11111111111111111111111111111111':
                score -= 35
                reasons.append("🚨 Mint Authority فعال")
       
        if result.get('freeze_authority') and result['freeze_authority'] != '':
            if result['freeze_authority'] != '11111111111111111111111111111111':
                score -= 25
                reasons.append("⚠️ Freeze Authority فعال")
       
        top_holder = float(result.get('owner_percent', 0))
        if top_holder > 50:
            score -= 30
            reasons.append(f"🚨 تمرکز بالا: {top_holder:.1f}%")
        elif top_holder > 30:
            score -= 15
            reasons.append(f"⚠️ تمرکز بالا: {top_holder:.1f}%")
        else:
            score += 15
       
        if result.get('is_honeypot') == '1':
            score -= 50
            reasons.append("🚨 Honeypot")
       
        score = max(0, min(100, score))
       
        return {
            'score': int(score),
            'is_safe': score >= 70,
            'reasons': reasons[:2],
            'top_holder_percent': top_holder
        }
       
    except Exception as e:
        print(f"❌ خطا GoPlus: {e}")
        return None

def fetch_dexscreener_fallback():
    """روش جایگزین: DexScreener - رشد ۲۴ ساعته"""
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        response = requests.get(url, timeout=15)
        data = response.json()
        pairs = data.get("pairs", [])
       
        filtered = []
        for pair in pairs[:50]:
            try:
                price_change_24h = float(pair.get('priceChange', {}).get('h24', 0))
                if price_change_24h > 5:  # حداقل ۵٪ رشد ۲۴ ساعته
                    filtered.append({
                        'source': 'DexScreener',
                        'symbol': pair.get('baseToken', {}).get('symbol', 'N/A'),
                        'name': pair.get('baseToken', {}).get('name', 'N/A'),
                        'address': pair.get('baseToken', {}).get('address', 'N/A'),
                        'volume': float(pair.get('volume', {}).get('h24', 0)),
                        'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                        'price_change_24h': price_change_24h,
                        'link': f"https://dexscreener.com/solana/{pair.get('pairAddress', '')}"
                    })
            except:
                continue
       
        print(f"📊 DexScreener: {len(filtered)} توکن با رشد ۲۴ ساعته")
        return filtered
       
    except Exception as e:
        print(f"❌ خطا DexScreener: {e}")
        return []

def process_tokens(tokens):
    """پردازش و فیلتر نهایی توکن‌ها"""
    final_list = []
   
    for token in tokens:
        try:
            if 'address' in token and 'price_change_percentage_24h' in token:
                # Moralis format
                address = token.get('address')
                symbol = token.get('symbol', 'N/A')
                name = token.get('name', 'N/A')
                volume = float(token.get('volume_24h_usd', 0))
                liquidity = float(token.get('liquidity_usd', 0))
                price_change = float(token.get('price_change_percentage_24h', 0))
                source = 'Moralis ✅'
                link = f"https://dexscreener.com/solana/{address}"
            else:
                # DexScreener fallback
                address = token.get('address')
                symbol = token.get('symbol')
                name = token.get('name')
                volume = token.get('volume', 0)
                liquidity = token.get('liquidity', 0)
                price_change = token.get('price_change_24h', 0)
                source = 'DexScreener ⚠️'
                link = token.get('link')
           
            security = None
            if address and address != 'N/A':
                security = check_token_security(address)
                if not security or not security['is_safe']:
                    print(f"⏭️ رد شد (امنیت): {symbol}")
                    continue
           
            final_list.append({
                'name': name,
                'symbol': symbol,
                'address': address,
                'volume': volume,
                'liquidity': liquidity,
                'price_change_24h': price_change,
                'security': security,
                'source': source,
                'link': link
            })
           
        except Exception as e:
            continue
   
    final_list.sort(key=lambda x: -x['price_change_24h'])
    return final_list[:6]

def format_message(coins):
    """قالب‌بندی پیام"""
    if not coins:
        return "😴 امروز کوین با روند صعودی پیدا نشد!\n\nفردا دوباره امتحان کن."
   
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
   
    msg = "🚀 **لیست کوین‌های با روند صعودی قوی** 🚀\n"
    msg += f"📆 {now} UTC\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += "🎯 **فیلترها:**\n"
    msg += " • حداقل ۵٪ رشد قیمت (۲۴ ساعته)\n"
    msg += " • امتیاز امنیتی ≥ ۷۰ (GoPlus)\n"
    msg += " • حجم ≥ ۵۰K | نقدینگی ≥ ۳۰K\n\n"
   
    for i, coin in enumerate(coins, 1):
        msg += f"**{i}. {coin['name']} ({coin['symbol']})**\n"
       
        if coin['address'] and coin['address'] != 'N/A':
            msg += f"📌 CA: `{coin['address'][:8]}...{coin['address'][-8:]}`\n"
       
        msg += f"📊 Vol 24h: `${coin['volume']:,.0f}`\n"
        msg += f"💧 Liq: `${coin['liquidity']:,.0f}`\n"
        msg += f"📈 رشد 24h: **+{coin['price_change_24h']:.1f}%**\n"
       
        if coin['security']:
            sec = coin['security']
            msg += f"🛡️ امنیت: **{sec['score']}/100**\n"
            if sec['reasons']:
                msg += f" • {sec['reasons'][0]}\n"
       
        msg += f"🔗 [مشاهده]({coin['link']})\n"
        msg += f"📎 منبع: `{coin['source']}`\n\n"
   
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "✅ **فقط کوین‌های با روند صعودی قوی**\n"
    msg += "⚠️ DYOR - این فقط یک فیلتر اولیه است!\n"
    msg += "🤖 ربات روندیاب Solana"
   
    return msg

def main():
    print("="*50)
    print("🚀 شروع اجرای ربات روندیاب Solana...")
    print(f"✅ توکن تلگرام: {TELEGRAM_TOKEN[:10]}...")
    print(f"✅ Moralis API: {MORALIS_API_KEY[:15] if MORALIS_API_KEY else 'تنظیم نشده'}...")
    print("="*50)
   
    if not MORALIS_API_KEY:
        send_telegram("⚠️ هشدار: Moralis API Key تنظیم نشده!")
        return
   
    tokens = fetch_moralis_tokens()
   
    if not tokens:
        print("⚠️ Moralis کار نکرد، می‌رم سراغ DexScreener...")
        tokens = fetch_dexscreener_fallback()
   
    if not tokens:
        send_telegram("😴 امروز کوینی پیدا نشد!")
        return
   
    final_coins = process_tokens(tokens)
    message = format_message(final_coins)
    send_telegram(message)
   
    print(f"✅ {len(final_coins)} کوین ارسال شد")
    print("✅ اجرا پایان یافت")

if __name__ == "__main__":
    main()
