import os
import logging
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_from_directory, session
from flask_cors import CORS
from openai import OpenAI

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")
CORS(app)

# Load product feed
df = None
try:
    df = pd.read_csv(os.path.join("data", "productfeed.csv"), skipinitialspace=True)
    df = df[df["categorie"].str.contains("Televisies", na=False)]
    unieke_merken = df["merk"].value_counts().index.tolist()
    logging.info(f"Loaded product feed with {len(df)} TVs from {len(unieke_merken)} merken.")
except Exception as e:
    logging.error(f"Failed to load product feed: {e}")
    unieke_merken = []

merk_opties = "\n".join([f"\u2022 {merk}" for merk in unieke_merken])

system_prompt = (
    "Je bent de AI Keuzehulp van Expert.nl. Je bent behulpzaam, vriendelijk en praat alsof je naast de klant staat in de winkel. "
    "Je stelt gerichte vragen, legt duidelijk uit, en maakt het gesprek leuk én nuttig. Gebruik een natuurlijke en ontspannen toon — het mag menselijk klinken. "
    "Wees behulpzaam, nieuwsgierig, positief en een tikje luchtig."
    "\n\nWerkwijze:\n"
    "• Stel steeds één duidelijke vraag.\n"
    "• Reageer op eerdere antwoorden en bouw daar logisch op verder.\n"
    "• Antwoord op een manier die natuurlijk voelt: alsof je een gesprek voert, niet een lijstje afwerkt.\n"
    "• Gebruik opsommingen waar dat helpt om structuur te bieden.\n"
    "• Gebruik emoji's alleen wanneer het helpt om een emotie te verduidelijken.\n"
    "• Vat elk antwoord vriendelijk samen, zodat duidelijk is dat je het goed hebt begrepen."
    "\n\nVragenstructuur:\n"
    "1. Waarvoor wil je de TV gebruiken?\n"
    "• Films en series\n"
    "• Sport\n"
    "• Gamen\n"
    "• Dagelijks tv-kijken\n"
    "• Combinatie van meerdere\n"
    "2. Wat is je budget?\n"
    "• A: Tot €750\n"
    "• B: €750–€1000\n"
    "• C: €1000–€1500\n"
    "• D: €1500–€2000\n"
    "• E: Meer dan €2000\n"
    "(Gebruik dit direct om het aanbod te beperken in de catalogus en vervolgvragen te richten op realistische opties.)\n"
    "3. Heb je een voorkeur voor een merk?\n"
    f"{merk_opties}\n"
    "• Geen voorkeur\n"
    "4. Welk formaat zoek je?\n"
    "• 43\"\n"
    "• 50\"\n"
    "• 55\"\n"
    "• 65\"\n"
    "• 75\"+\n"
    "• Ik weet het nog niet\n"
    "5. Heb je een voorkeur voor schermtechnologie?\n"
    "• OLED\n"
    "• QLED\n"
    "• LED\n"
    "• Weet ik niet\n"
    "(Leg indien nodig kort de verschillen uit.)\n"
    "6. Zijn er extra functies belangrijk voor je?\n"
    "• Ambilight\n"
    "• HDMI 2.1\n"
    "• Chromecast\n"
    "• Geen voorkeur\n"
    "\n\nAccessoire-advies:\n"
    "• Als de klant een muurbeugel of accessoire noemt, filter op formaat, bevestigingstype en VESA-maat.\n"
    "• Toon maximaal 2 suggesties met prijs en klikbare link als beschikbaar."
    "\n\nOpeningsvraag:\n"
    "Zullen we samen even door een paar vragen lopen om de perfecte tv voor jou te vinden?\n"
    "• Als de klant akkoord gaat, begin dan meteen vriendelijk en met energie aan vraag 1.\n"
    "• Bij twijfel: stel gerust, en bied aan om alsnog samen te kijken."
    "\n\nProductcatalogus gebruik:\n"
    "• Gebruik alleen tv’s uit de catalogus die binnen het opgegeven budget passen.\n"
    "• Gebruik merk, formaat en features om keuzes te filteren.\n"
    "• Vermeld kort prijs en waarom een model goed past.\n"
    "• Zeg het erbij als iets niet op voorraad is en stel een alternatief voor."
    "\n\nLet op:\n"
    "• Herhaal geen vragen die al beantwoord zijn.\n"
    "• Vraag bij twijfel of iemand terug wil naar een vorige stap.\n"
    "• Geef geen negatieve uitspraken over merken of concurrenten.\n"
    "• Gebruik emoji’s alleen als het helpt om een gevoel of nuance duidelijk te maken."
    "\n\nWeergave instructies:\n"
    "• Gebruik altijd bullets (ronde stippen) als je meerdere keuzes toont. Zet nooit meerdere opties in één zin, maar elk op een aparte regel.\n"
    "• Gebruik de exacte merkenlijst die is aangeleverd in de system prompt. Als de gebruiker vraagt naar merken (of de vraag herhaalt), toon dan opnieuw dezelfde lijst — en verzin geen andere merken.\n"
    "• Verzin geen extra merken die niet in de lijst staan."
)

@app.route("/")
def home():
    return "AI Keuzehulp is actief."

@app.route("/keuzehulp")
def keuzehulp():
    session.clear()
    session['messages'] = [{"role": "system", "content": system_prompt}]
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_input = data.get("message")

    if not user_input:
        return jsonify({"assistant": "Ik heb geen vraag ontvangen."})

    conversation = session.get("messages", [{"role": "system", "content": system_prompt}])
    conversation.append({"role": "user", "content": user_input})

    # Trim conversation to improve speed (keep system + last 20 messages)
    MAX_HISTORY = 20
    conversation_trimmed = [conversation[0]] + conversation[-MAX_HISTORY:]

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4-turbo"),
            messages=conversation_trimmed,
            temperature=0.7,
            max_tokens=700
        )
        antwoord = response.choices[0].message.content
        conversation.append({"role": "assistant", "content": antwoord})
        session["messages"] = conversation
        return jsonify({"assistant": antwoord})
    except Exception as e:
        logging.error(f"Fout bij OpenAI-call: {e}")
        return jsonify({"assistant": f"Fout bij OpenAI: {e}"}), 500

@app.route("/static/<path:path>")
def send_static(path):
    response = send_from_directory("static", path)
    response.headers["Cache-Control"] = "public, max-age=31536000"
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled exception: {e}")
    return jsonify({"assistant": f"Interne fout: {e}"}), 500


