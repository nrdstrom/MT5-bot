import os, re, requests, asyncio
from dotenv import load_dotenv
import discord
from discord import Intents

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
INPUT_CHANNEL_ID = int(os.getenv("INPUT_CHANNEL_ID", "0"))
OUTPUT_CHANNEL_ID = int(os.getenv("OUTPUT_CHANNEL_ID", "0"))
print("OCR API KEY:", OCR_API_KEY)
OCR_API_KEY = os.getenv("OCR_API_KEY")  # ocr.space

# Enkla mönster – kan finslipas efter era screenshots
INSTRUMENT_RE = re.compile(r"(NAS100|US30|SPX500|XAUUSD|EURUSD|GBPUSD|NQ|ES|[A-Z]{2,6}\d*)", re.I)
TYPE_RE = re.compile(r"\b(BUY|SELL|LONG|SHORT)\b", re.I)
NUM = r"(\d+(?:\.\d+)?)"
ENTRY_RE = re.compile(r"(ENTRY|EN|E|@)\D*"+NUM, re.I)
SL_RE = re.compile(r"(SL|STOP(?: LOSS)?)\D*"+NUM, re.I)
TP1_RE = re.compile(r"(TP1|TP 1|TARGET 1)\D*"+NUM, re.I)
TP2_RE = re.compile(r"(TP2|TP 2|TARGET 2)\D*"+NUM, re.I)

def ocr_image_url(url: str) -> str:
    # Enkel OCR via ocr.space – gratisnivån funkar fint för textoverlay
    resp = requests.post(
        "https://api.ocr.space/parse/imageurl",
        data={"apikey": OCR_API_KEY, "url": url, "OCREngine": 2, "scale": True, "isTable": False, "detectOrientation": True},
        timeout=30
    )
    resp.raise_for_status()
    j = resp.json()
    if not j.get("ParsedResults"):
        return ""
    return "\n".join(p["ParsedText"] for p in j["ParsedResults"] if "ParsedText" in p)

def parse_signal(text: str):
    t = text.replace(",", ".")
    d = {}
    if m := INSTRUMENT_RE.search(t): d["instrument"] = m.group(1).upper()
    if m := TYPE_RE.search(t): d["type"] = "BUY" if m.group(1).upper() in ("BUY","LONG") else "SELL"
    if m := ENTRY_RE.search(t): d["entry"] = m.group(2)
    if m := SL_RE.search(t): d["sl"] = m.group(2)
    if m := TP1_RE.search(t): d["tp1"] = m.group(2)
    if m := TP2_RE.search(t): d["tp2"] = m.group(2)
    d["found"] = sum(k in d for k in ("instrument","type","entry","sl","tp1","tp2"))
    return d

def fmt(d):
    return (
        f"Instrument: {d.get('instrument','?')}\n"
        f"Type: {d.get('type','?')}\n"
        f"Entry: {d.get('entry','?')}\n"
        f"SL: {d.get('sl','?')}\n"
        f"TP1: {d.get('tp1','?')}\n"
        f"TP2: {d.get('tp2','?')}"
    )

class Bot(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        if message.channel.id != INPUT_CHANNEL_ID: return
        if not message.attachments: return

        # Ta första bilden
        att = message.attachments[0]
        if not att.content_type or not att.content_type.startswith("image"):
            return

        # OCR via URL (Discord attachment-URL)
        try:
            text = ocr_image_url(att.url)
        except Exception as e:
            await message.reply(f"OCR error: {e}")
            return

        parsed = parse_signal(text)
        # Om vi saknar mycket → skicka OCR-dump för snabb manuell fix
        if parsed["found"] < 4:
            preview = (text[:1500] + "...") if len(text) > 1500 else text
            await message.reply("Couldn't confidently parse 🤖\n```\n" + preview + "\n```")
            return

        out_ch = self.get_channel(OUTPUT_CHANNEL_ID)
        await out_ch.send(fmt(parsed))

intents = Intents.default()
intents.message_content = True
client = Bot(intents=intents)
client.run(DISCORD_TOKEN)
