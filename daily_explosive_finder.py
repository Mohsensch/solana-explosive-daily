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
SECURITY_SCORE_THRESHOLD = 70  # فقط کوین‌های با امنیت بالای ۷۰

# ============== تشخیص ترند روز (AI, Politics, Meme, ...) ==============
def detect_daily_trends():
    """تشخیص اینکه امروز چه دسته‌بندی‌هایی ترند هستن"""
    trends = []
    
    # 1. چک کردن اخبار سیاسی/جهانی (مثال ساده)
    try:
        # اینجا می‌تونی از یه API خبری استفاده کنی
        # فعلاً ساده شده:
        current_hour = datetime.now().hour
        current_day = datetime.now().day
        
        # نمونه: اگه رویداد خاصی توی تقویم هست
        political_events = {
            (2, 12): "Super Bowl - Trump AI Ad",  # [citation:6]
            (1, 20): "Inauguration Day",
            (3, 15): "Election Season"
        }
        
        if (current_day, current_hour) in political_events:
            trends.append("Politics")
            
    except:
        pass
    
    # 2. چک کردن ترندهای کلی از CoinGecko
    try:
        url = "https://api.coingecko.com/api/v3/search/trending"
        headers = {"User-Agent": "DailyBot/1.0"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        coins = data.get('coins', [])[:5]
        for coin in coins:
            item = coin.get('item', {})
            # سعی میکنیم دسته‌بندی رو حدس بزنیم
            name = item.get('name', '').lower()
            if 'ai' in name or 'gpt' in name or 'robot' in name:
                trends.append("AI")
            if 'doge' in name or 'bonk' in name or 'wif' in name:
                trends.append("Meme")
            if 'defi' in name or 'lend' in name:
                trends.append("DeFi")
    except:
        pass
    
    # 3. چک کردن حجم بحث در X (LunarCrush - بعداً)
    
    # حذف تکراری‌ها
    trends = list(set(trends))
    if not trends:
        trends = ["General"]  # پیش‌فرض
    
    print(f"📊 ترندهای امروز: {trends}")
    return trends

# ============== دریافت Galaxy Score از LunarCrush ==============
def get_lunarcrush_social_score(symbol):
    """دریافت امتیاز سوشال مدیا از LunarCrush"""
    try:
        # LunarCrush API نیاز به API Key داره
        # اینجا با توجه به مستنداتش باید کلید بگیری
        # نمونه کد:
        """
        url = f"https://lunarcrush.com/api3/coins/{symbol}/v1"
        headers = {"Authorization": "Bearer YOUR_API_KEY"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        return data.get('data', [{}])[0].get('galaxy_score', 0)
        """
        # فعلاً برگرداندن مقدار ساختگی
        return 65  # TODO: API Key واقعی
    except:
        return 0

# ============== بررسی امنیت پیشرفته با GoPlus ==============
def check_token_security_goplus(token_address):
    """بررسی کامل امنیت توکن با GoPlus API [citation:3][citation:7]"""
    try:
        url = f"https://api.gopluslabs.io/api/v1/token_security/1?contract_addresses={token_address}"
        # توجه: chain_id=1 برای اتریوم، برای سولانا 101
        # برای سولانا: 
        url = f"https://api.gopluslabs.io/api/v1/token_security/101?contract_addresses={token_address}"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('code') != 1:
            return None
        
        result = data['result'].get(token_address, {})
        
        # امتیازدهی وزنی (0-100)
        score = 100
        reasons = []
        
        # 1. Mint authority (بحرانی)
        if result.get('mint_authority'):
            if result['mint_authority'] == '11111111111111111111111111111111':
                score += 0  # بورن شده
            else:
                score -= 35
                reasons.append("🚨 Mint Authority فعال (خطر چاپ بی‌نهایت)")
        
        # 2. Freeze authority
        if result.get('freeze_authority') and result['freeze_authority'] != '':
            if result['freeze_authority'] != '11111111111111111111111111111111':
                score -= 25
                reasons.append("⚠️ Freeze Authority فعال (خطر فریز کیف پول)")
        
        # 3. لیکوییدیتی قفل شده
        liquidity_locked = result.get('liquidity_locked', [])
        if liquidity_locked:
            total_locked = sum(float(l.get('amount', 0)) for l in liquidity_locked)
            if total_locked > 0:
                score += 20
                reasons.append("✅ لیکوییدیتی قفل شده")
            else:
                score -= 30
                reasons.append("🚨 لیکوییدیتی قفل نیست (ریسک Rug Pull)")
        
        # 4. توزیع توکن
        top_holder = float(result.get('owner_percent', 0))
        if top_holder > 50:
            score -= 30
            reasons.append(f"🚨 تمرکز بالا: تاپ هولدر {top_holder:.1f}%")
        elif top_holder > 30:
            score -= 15
            reasons.append(f"⚠️ تمرکز بالا: تاپ هولدر {top_holder:.1f}%")
        else:
            score += 15
            reasons.append(f"✅ توزیع خوب: تاپ هولدر {top_holder:.1f}%")
        
        # 5. Honeypot
        if result.get('is_honeypot') == '1':
            score -= 50
            reasons.append("🚨 Honeypot (فقط خرید، فروش ممنوع)")
        
        # 6. توکن 2022
        if result.get('is_token_2022') == '1':
            score -= 10
            reasons.append("⚠️ توکن 2022 (ریسک بیشتر)")
        
        # 7. مالک قرارداد
        owner = result.get('owner_address', '')
        if owner and owner != '11111111111111111111111111111111':
            score -= 15
            reasons.append("⚠️ قرارداد غیر قابل تغییر نیست")
        
        # محدود کردن امتیاز
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
            'reasons': reasons[:2],  # حداکثر 2 دلیل
            'is_safe': score >= SECURITY_SCORE_THRESHOLD,
            'holders': result.get('holder_count', 0),
            'top_holder_percent': top_holder,
            'liquidity_locked': bool(liquidity_locked)
        }
        
    except Exception as e:
        print(f"❌ خطا GoPlus: {e}")
        return None

# ============== تشخیص دسته‌بندی توکن ==============
def detect_token_category(name, symbol, address):
    """تشخیص اینکه توکن متعلق به کدوم دسته‌ست"""
    name_lower = f"{name} {symbol}".lower()
    
    categories = {
        "AI": ['ai', 'gpt', 'robot', 'agent', 'smart', 'brain', 'neural', 'compute', 'deep'],
        "Politics": ['trump', 'biden', 'president', 'election', 'political', 'whitehouse', 'congress', 'senate'],
        "Meme": ['doge', 'bonk', 'pepe', 'woof', 'cat', 'dog', 'penguin', 'fish', 'frog'],
        "DeFi": ['lend', 'swap', 'pool', 'yield', 'farm', 'stake', 'dao', 'protocol'],
        "Gaming": ['game', 'play', 'guild', 'raid', 'quest', 'rpg', 'metaverse'],
        "Infrastructure": ['bridge', 'oracle', 'rpc', 'node', 'validator', 'storage']
    }
    
    detected = []
    for cat, keywords in categories.items():
        if any(k in name_lower for k in keywords):
            detected.append(cat)
    
    return detected if detected else ["Other"]

# ============== دریافت از DexScreener با فیلتر هوشمند ==============
def fetch_dexscreener():
    """گرفتن لیست کوین‌ها و تشخیص ترند [citation:9]"""
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        response = requests.get(url, timeout=15)
        data = response.json()
        pairs = data.get("pairs", [])
        
        # مرتب‌سازی بر اساس ترند (حجم + سن)
        sorted_pairs = sorted(pairs, 
            key=lambda x: (float(x.get("volume", {}).get("h24", 0)), -float(x.get("pairCreatedAt", 0))),
            reverse=True
        )[:50]
        
        print(f"📊 DexScreener: {len(sorted_pairs)} جفت‌ارز برتر")
        return sorted_pairs
    except Exception as e:
        print(f"❌ خطا DexScreener: {e}")
        return []

# ============== فیلتر نهایی ==============
def filter_potential(items, daily_trends):
    """فیلتر هوشمند - فقط کوین‌های امن + ترند سوشال + مرتبط با ترند روز"""
    filtered = []
    
    for item in items:
        try:
            if "chainId" not in item or item.get("chainId") != "solana":
                continue
            
            # اطلاعات پایه
            symbol = item.get("baseToken", {}).get("symbol", "N/A")
            name = item.get("baseToken", {}).get("name", "N/A")
            address = item.get("baseToken", {}).get("address", "N/A")
            
            # اطلاعات مالی
            volume_h24 = float(item.get("volume", {}).get("h24", 0))
            liquidity = float(item.get("liquidity", {}).get("usd", 0))
            
            # سن توکن
            age_str = item.get("pairCreatedAt", 0)
            age_h = 999
            if age_str:
                age_seconds = time.time() - (age_str / 1000)
                age_h = age_seconds / 3600
            
            change_24h = float(item.get("priceChange", {}).get("h24", 0))
            
            # ========== فیلترهای اولیه ==========
            if volume_h24 < 50000:  # حجم حداقل
                continue
            if liquidity < 30000:   # نقدینگی حداقل
                continue
            if age_h > 168:         # حداکثر 7 روز
                continue
            
            # ========== بررسی امنیت ==========
            security = check_token_security_goplus(address)
            if not security or not security['is_safe']:
                print(f"⏭️ رد شد (امنیت): {symbol} - {security['score'] if security else 'N/A'}")
                continue
            
            # ========== تشخیص دسته‌بندی ==========
            categories = detect_token_category(name, symbol, address)
            
            # ========== بررسی ارتباط با ترند روز ==========
            is_trending = False
            for cat in categories:
                if cat in daily_trends:
                    is_trending = True
                    break
            
            # اگه ترند نیست، وزن کمتری میده
            trend_boost = 1.5 if is_trending else 0.8
            
            # ========== امتیاز سوشال (LunarCrush) ==========
            social_score = get_lunarcrush_social_score(symbol)
            social_boost = 1 + (social_score / 200)  # 50 -> 1.25x, 80 -> 1.4x
            
            # ========== امتیاز نهایی ==========
            final_score = (
                (volume_h24 / 100000) * 0.4 +
                (change_24h + 100) * 0.3 +
                (100 - age_h) * 0.1 +
                security['score'] * 0.2
            ) * trend_boost * social_boost
            
            filtered.append({
                "source": "DexScreener",
                "name": name,
                "symbol": symbol,
                "address": address,
                "volume": volume_h24,
                "liquidity": liquidity,
                "age": age_h,
                "change": change_24h,
                "link": f"https://dexscreener.com/solana/{item.get('pairAddress', '')}",
                "security": security,
                "categories": categories,
                "is_trending": is_trending,
                "social_score": social_score,
                "final_score": final_score
            })
            
        except Exception as e:
            continue
    
    # مرتب‌سازی بر اساس امتیاز نهایی
    filtered.sort(key=lambda x: -x['final_score'])
    print(f"🎯 {len(filtered)} کوین امن پیدا شد")
    return filtered[:6]  # حداکثر ۶ تا

# ============== قالب‌بندی پیام ==============
def format_message(coins, daily_trends):
    """قالب‌بندی پیام با همه اطلاعات"""
    if not coins:
        return "😴 امروز کوین امن و پتانسیل‌داری پیدا نشد!\n\nفردا دوباره امتحان کن."
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    msg = "🚀 **لیست روزانه کوین‌های امن + ترند Solana** 🚀\n"
    msg += f"📆 {now} UTC\n"
    msg += f"🔥 **ترندهای امروز:** {', '.join(daily_trends)}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, coin in enumerate(coins, 1):
        # عنوان با ایموجی ترند
        trend_emoji = "🔥" if coin['is_trending'] else "📌"
        msg += f"{trend_emoji} **{i}. {coin['name']} ({coin['symbol']})**\n"
        
        # 📌 آدرس قرارداد
        if coin['address'] and coin['address'] != 'N/A':
            msg += f"📌 CA: `{coin['address'][:8]}...{coin['address'][-8:]}`\n"
        
        # 💰 اطلاعات مالی
        msg += f"📊 Vol 24h: `${coin['volume']:,.0f}`\n"
        msg += f"💧 Liq: `${coin['liquidity']:,.0f}`\n"
        msg += f"⏰ سن: `{int(coin['age'])}h`\n"
        msg += f"📈 رشد 24h: **{coin['change']:+.1f}%**\n"
        
        # 🛡️ امنیت (فقط سبزها هستن)
        sec = coin['security']
        msg += f"🛡️ **{sec['risk_level']}** (امتیاز: {sec['score']}/100)\n"
        if sec['reasons']:
            msg += f"   • {sec['reasons'][0]}\n"
        
        # 🏷️ دسته‌بندی
        msg += f"🏷️ دسته: {', '.join(coin['categories'])}\n"
        
        # 🐦 فعالیت سوشال
        if coin['social_score'] > 0:
            msg += f"🐦 Galaxy Score: **{coin['social_score']}/100**\n"
        
        # 🔗 لینک‌ها
        msg += f"🔗 [DexScreener]({coin['link']})"
        if coin['address'] and coin['address'] != 'N/A':
            msg += f" | [Solscan](https://solscan.io/token/{coin['address']})"
        
        msg += f"\n📎 منبع: `{coin['source']}`\n\n"
    
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "✅ **فقط کوین‌های امن نمایش داده شدن**\n"
    msg += "⚠️ **DYOR** - بازم تحقیق کن!\n"
    msg += "🤖 ربات پتانسیل‌یاب Solana v2.0"
    
    return msg

# ============== اصلی ==============
def main():
    print("🚀 شروع اجرای ربات پتانسیل‌یاب Solana v2.0...")
    print(f"✅ توکن: {TELEGRAM_TOKEN[:10]}...")
    print(f"✅ چت آیدی: {CHAT_ID}")
    print(f"✅ آستانه امنیت: >{SECURITY_SCORE_THRESHOLD}")
    
    # تشخیص ترندهای روز
    daily_trends = detect_daily_trends()
    
    # دریافت داده
    dexscreener_pairs = fetch_dexscreener()
    
    # فیلتر نهایی
    top_coins = filter_potential(dexscreener_pairs, daily_trends)
    
    # ارسال پیام
    message = format_message(top_coins, daily_trends)
    
    # ارسال به تلگرام
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    response = requests.post(url, json=payload, timeout=10)
    
    if response.status_code == 200:
        print("✅ پیام با موفقیت ارسال شد")
    else:
        print(f"❌ خطا در ارسال: {response.status_code}")
    
    print("✅ اجرا پایان یافت")

if __name__ == "__main__":
    main()
