import requests
import json
from datetime import datetime
import os
import time

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
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        response = requests.post(url, json=payload, timeout=10)
        print(f"📤 ارسال پیام: {message[:50]}...")
        return response
    except Exception as e:
        print(f"❌ خطا در ارسال پیام: {e}")
        return None

def load_sent():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_sent(sent_set):
    with open(STATE_FILE, 'w') as f:
        json.dump(list(sent_set), f)

def check_token_security(token_address):
    """بررسی امنیت توکن با GoPlus API [citation:2][citation:6]"""
    try:
        url = f"https://api.gopluslabs.io/api/v1/token_security/{token_address}?chain_id=101"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('code') != 1 or not data.get('result'):
            return None
        
        result = data['result'].get(token_address, {})
        
        # امتیاز امنیتی (0-100)
        score = 100
        reasons = []
        
        # 1. بررسی Mint Authority [citation:4]
        if result.get('mint_authority') and result['mint_authority'] != '':
            if result.get('mint_authority') == '11111111111111111111111111111111':
                score += 0  # بورن شده
            else:
                score -= 30
                reasons.append("🚨 Mint Authority فعال (قابلیت چاپ بی‌نهایت)")
        
        # 2. بررسی Freeze Authority [citation:4]
        if result.get('freeze_authority') and result['freeze_authority'] != '':
            if result['freeze_authority'] != '11111111111111111111111111111111':
                score -= 20
                reasons.append("⚠️ Freeze Authority فعال (میتونه کیف پول‌ها رو فریز کنه)")
        
        # 3. بررسی لیکوییدیتی قفل شده [citation:1]
        if result.get('liquidity_locked'):
            if result['liquidity_locked'] == '1':
                score += 15
                reasons.append("✅ لیکوییدیتی قفل شده")
            else:
                score -= 25
                reasons.append("🚨 لیکوییدیتی قفل نیست (ریسک Rug Pull)")
        
        # 4. بررسی توزیع توکن [citation:4][citation:7]
        top_holder = float(result.get('owner_percent', 0))
        if top_holder > 50:
            score -= 30
            reasons.append(f"🚨 تمرکز بالا: تاپ هولدر {top_holder:.1f}%")
        elif top_holder > 30:
            score -= 15
            reasons.append(f"⚠️ تمرکز نسبتاً بالا: تاپ هولدر {top_holder:.1f}%")
        else:
            score += 10
            reasons.append(f"✅ توزیع خوب: تاپ هولدر {top_holder:.1f}%")
        
        # 5. بررسی توکن honeypot [citation:1]
        if result.get('is_honeypot') == '1':
            score -= 40
            reasons.append("🚨 توکن Honeypot (فقط میتونی بخری، نمیتونی بفروشی)")
        
        # 6. بررسی فشرده سازی
        if result.get('holder_count', 0) < 50:
            score -= 15
            reasons.append(f"⚠️ تعداد هولدر کم: {result.get('holder_count', 0)} نفر")
        else:
            score += 5
        
        # 7. بررسی توکن 2022
        if result.get('is_token_2022') == '1':
            score -= 10
            reasons.append("⚠️ توکن 2022 - ریسک بیشتر")
        
        # محدود کردن امتیاز بین 0 تا 100
        score = max(0, min(100, score))
        
        # سطح ریسک
        if score >= 70:
            risk_level = "🟢 کم‌ریسک"
        elif score >= 40:
            risk_level = "🟡 متوسط"
        else:
            risk_level = "🔴 پرریسک"
        
        return {
            'score': int(score),
            'risk_level': risk_level,
            'reasons': reasons[:3],  # حداکثر 3 دلیل
            'holders': result.get('holder_count', 0),
            'top_holder_percent': top_holder,
            'mint_burned': result.get('mint_authority') == '11111111111111111111111111111111',
            'liquidity_locked': result.get('liquidity_locked') == '1'
        }
        
    except Exception as e:
        print(f"❌ خطا در بررسی امنیت {token_address[:10]}: {e}")
        return None

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
                mc = float(item.get("fdv", 0))
                liquidity = float(item.get("liquidity", {}).get("usd", 0))
                
                age_str = item.get("pairCreatedAt", 0)
                age_h = 999
                if age_str:
                    age_seconds = time.time() - (age_str / 1000)
                    age_h = age_seconds / 3600
                
                change_24h = float(item.get("priceChange", {}).get("h24", 0))
                link = f"https://dexscreener.com/solana/{item.get('pairAddress', '')}"
                
                # فیلترهای اصلی
                if (volume_h24 >= 100000 and 
                    liquidity >= 50000 and 
                    age_h <= 72 and
                    (change_24h > 20 or volume_h24 > 300000)):
                    
                    # بررسی امنیت توکن
                    security = check_token_security(address)
                    
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
                        "link": link,
                        "security": security
                    })
            
            # فرمت CoinGecko
            elif "id" in item and "symbol" in item:
                symbol = item.get("symbol", "N/A").upper()
                name = item.get("name", "N/A")
                address = item.get("id", "N/A")  # CG آدرس نداره
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
                        "address": address,
                        "mc": mc,
                        "volume": volume_h24,
                        "liquidity": 0,
                        "age": 24,
                        "change": change_24h,
                        "link": link,
                        "security": None
                    })
        except Exception as e:
            continue
    
    # حذف کوین‌های پرریسک (اختیاری - اگه می‌خوای فقط امن‌ها برن)
    filtered = [c for c in filtered if not (c['security'] and c['security']['score'] < 30)]
    
    # مرتب‌سازی بر اساس حجم و رشد
    filtered.sort(key=lambda x: (-x["volume"], -x["change"]))
    print(f"🎯 {len(filtered)} کوین پس از فیلتر باقی ماند")
    return filtered[:6]  # حداکثر ۶ تا

def format_message(coins):
    """قالب‌بندی پیام برای تلگرام"""
    if not coins:
        return "😴 امروز کوین پتانسیل‌داری پیدا نشد!\n\nفردا دوباره امتحان کن."
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    msg = "🚀 **لیست روزانه کوین‌های پتانسیل‌دار Solana** 🚀\n"
    msg += f"📆 {now} UTC\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, coin in enumerate(coins[:5], 1):
        msg += f"**{i}. {coin['name']} ({coin['symbol']})**\n"
        
        # 📌 آدرس قرارداد (Contract Address)
        if coin['address'] and coin['address'] != 'N/A':
            msg += f"📌 CA: `{coin['address'][:8]}...{coin['address'][-8:]}`\n"
        
        # 💰 اطلاعات مالی
        if coin['mc'] > 0:
            msg += f"💰 MC: `${coin['mc']:,.0f}`\n"
        msg += f"📊 Vol 24h: `${coin['volume']:,.0f}`\n"
        if coin['liquidity'] > 0:
            msg += f"💧 Liq: `${coin['liquidity']:,.0f}`\n"
        if coin['age'] < 999:
            msg += f"⏰ سن: `{int(coin['age'])}h`\n"
        msg += f"📈 رشد 24h: **{coin['change']:+.1f}%**\n"
        
        # 🛡️ بررسی امنیت GoPlus
        if coin['security']:
            sec = coin['security']
            msg += f"🛡️ **امنیت: {sec['risk_level']}** (امتیاز: {sec['score']}/100)\n"
            if sec['reasons']:
                msg += f"   • {sec['reasons'][0]}\n"
        else:
            msg += "🛡️ امنیت: قابل بررسی نیست\n"
        
        # 🔗 لینک
        msg += f"🔗 [مشاهده]({coin['link']})"
        if coin['address'] and coin['address'] != 'N/A' and coin['source'] == 'DexScreener':
            msg += f" | [Solscan](https://solscan.io/token/{coin['address']})"
        
        msg += f"\n📎 منبع: `{coin['source']}`\n\n"
    
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "⚠️ **DYOR** - ریسک میم‌کوین‌ها بالاست!\n"
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
