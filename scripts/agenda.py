"""Daily agenda for horshim-btelem: match today's headlines to Telem archive articles via Claude.
Runs in GitHub Actions; needs ANTHROPIC_API_KEY. Writes news.json only when it gets a valid result."""
import json, os, re, sys, urllib.request
from datetime import datetime, timezone, timedelta

FEEDS = [("https://www.ynet.co.il/Integration/StoryRss2.xml", "ynet"),
         ("https://rss.walla.co.il/feed/1?type=main", "וואלה")]
MODEL = "claude-sonnet-5"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (horshim-btelem agenda)"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

headlines = []
for url, src in FEEDS:
    try:
        titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", get(url), re.S)[1:40]
        headlines += [f"[{src}] {t.strip()}" for t in titles if t.strip()]
    except Exception as e:
        print("feed failed", src, e)
if len(headlines) < 5:
    sys.exit("not enough headlines, keeping yesterday's agenda")

index = json.load(open("search-index.json", encoding="utf-8"))
ids = {a["id"] for a in index}
catalog = "\n".join(f'{a["id"]}|{a["t"]}|{", ".join(a["w"])}|{a["d"][:7]}|{" ".join(a["kw"][:6])}' for a in index)

prompt = f"""אתה עורך את "על סדר היום" באתר חורשים בתלם, ארכיון כתב העת תלם (פוליטיקה, חברה, כלכלה, מבית קרן ברל כצנלסון).

כותרות החדשות של היום:
{chr(10).join(headlines)}

ארכיון הכתבות (מזהה|כותרת|כותבים|חודש|מילות מפתח):
{catalog}

משימה:
1. קבץ את הכותרות ל־4 עד 6 נושאים מהותיים: פוליטיקה, מדיניות, ביטחון, כלכלה, חברה, דמוקרטיה. אחד כותרות קשורות לנושא אחד עם כותרת משולבת. דלג על פלילים, רכילות, ספורט ותוכן וולגרי.
2. לכל נושא בחר 2 עד 3 כתבות מהארכיון שמדברות עליו באמת. אם אין התאמה אמיתית, השמט את הנושא.
3. לכל כתבה כתוב משפט אחד בעברית שמסביר למה היא מדברת לחדשות של היום. בלי קו מפריד ארוך, בלי שאלות רטוריות, בלי קלישאות. הזכר את שם הכותב כשזה מוסיף משקל.

החזר JSON בלבד, בלי טקסט נוסף ובלי גדרות קוד:
{{"topics": [{{"headline": "כותרת הנושא", "source": "ynet | וואלה | ynet, וואלה", "matches": [{{"id": "מזהה", "why": "משפט"}}]}}]}}"""

body = json.dumps({"model": MODEL, "max_tokens": 4000,
                   "messages": [{"role": "user", "content": prompt}]}).encode()
req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
    "Content-Type": "application/json", "x-api-key": os.environ["ANTHROPIC_API_KEY"],
    "anthropic-version": "2023-06-01"})
text = json.load(urllib.request.urlopen(req, timeout=180))["content"][0]["text"]
out = json.loads(re.search(r"\{[\s\S]*\}", text).group(0))

topics = []
for t in out.get("topics", []):
    matches = [{"id": str(m["id"]), "why": str(m["why"]).replace("—", ",").replace("–", ",")}
               for m in t.get("matches", []) if str(m.get("id")) in ids and m.get("why")]
    if matches:
        topics.append({"headline": str(t["headline"]).replace("—", ",").replace("–", ","),
                       "source": t.get("source", ""), "matches": matches[:3]})
if not topics:
    sys.exit("no valid topics, keeping yesterday's agenda")

now = datetime.now(timezone(timedelta(hours=3)))
json.dump({"updated": f"{now.day}.{now.month}.{now.year}", "topics": topics[:6]},
          open("news.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("wrote", len(topics), "topics")
