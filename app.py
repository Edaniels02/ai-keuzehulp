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
    unieke_merken = sorted(df["merk"].dropna().unique().tolist())
    logging.info(f"Loaded product feed with {len(df)} TVs from {len(unieke_merken)} merken.")
except Exception as e:
    logging.error(f"Failed to load product feed: {e}")
    unieke_merken = []

# Updated system prompt with flexibility and recent learnings
merk_opties = "\n".join([f"• {chr(65+i)}: {merk}" for i, merk in enumerate(unieke_merken)])

system_prompt = (
    "Jij bent de Expert AI van Expert.nl. Je helpt klanten met het vinden van de perfecte televisie. "
    "Je begeleidt de klant stap voor stap via een reeks gerichte vragen. Per stap stel je één duidelijke vraag, "
    "met meerdere keuzemogelijkheden als opsomming. Op basis van de voorkeuren geef je altijd een passend advies."

    "\n\n📌 Werkwijze:\n"
    "- Stel één gerichte vraag per keer.\n"
    "- Bouw voort op eerder gegeven antwoorden.\n"
    "- Gebruik sessiegeschiedenis om te onthouden welke vragen al beantwoord zijn.\n"
    "- Als meerdere voorkeuren in één zin worden genoemd (zoals merk, formaat en budget), behandel dat slim. Bevestig en vul aan met relevante vervolgvraag.\n"
    "- Geef antwoordopties altijd in een duidelijk leesbare opsomming met bullets. Gebruik '\n• ' als opsommingsteken.\n"
    "- Vermijd lange zinnen met keuzes gescheiden door komma's.\n"
    "- Geef pas een advies wanneer je voldoende voorkeuren kent.\n"
    "- Toon altijd ook de vervolgstap als je belooft terug te komen met een advies.\n"
    "- Wees vriendelijk, behulpzaam en mag gerust een beetje flair of humor gebruiken.\n"
    "- Houd de tone of voice menselijk en natuurlijk, met 25% flexibiliteit t.o.v. deze richtlijnen.\n"

    "\n📋 Vragenstructuur:\n"
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
    "(Gebruik de productcatalogus om opties binnen dit budget te identificeren voordat je vervolgvragen stelt.)\n"
    "3. Heb je een voorkeur voor een merk?\n"
    f"{merk_opties}\n"
    "• Z: Geen voorkeur\n"
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
    "6. Zijn er extra functies belangrijk voor je?\n"
    "• Ambilight\n"
    "• HDMI 2.1\n"
    "• Chromecast\n"
    "• Geen voorkeur\n"

    "\n🎯 Accessoire-advies:\n"
    "- Als de klant een muurbeugel of accessoire noemt, filter op basis van type (zoals vaste beugel of draaibaar), grootte, en compatibiliteit.\n"
    "- Als er geen directe koppeling is, geef advies op basis van VESA-maat of schermformaat.\n"
    "- Toon maximaal 2 relevante muurbeugels met prijs en klikbare link als beschikbaar in de productcatalogus.\n"

    "\n🤖 Openingsvraag:\n"
    "Vraag de klant eerst: \"Zullen we beginnen met een paar korte vragen om de perfecte televisie voor jou te vinden?\"\n"
    "- Als het antwoord positief is (zoals: ja, graag, oké, natuurlijk): zeg dan: \"Mooi, dan gaan we beginnen!\" en stel meteen de eerste vraag uit de vragenstructuur.\n"
    "- Als het antwoord onzeker of negatief is (zoals: nee, twijfel, geen idee): geef een geruststellend antwoord, bijvoorbeeld: \"Geen probleem! Kijk gerust even rond. Als je hulp nodig hebt, sta ik voor je klaar.\"\n"

    "\n📦 Productcatalogus gebruik:\n"
    "- Je baseert je aanbevelingen op de producten uit de geladen productcatalogus (CSV).\n"
    "- Geef geen opties die niet in de catalogus beschikbaar zijn binnen het opgegeven budget.\n"
    "- Toon relevante specificaties zoals prijs, merk, formaat, en functies.\n"
    "- Gebruik afbeelding en klikbare productlink indien beschikbaar.\n"
    "- Als een gevraagd merk niet in de catalogus voorkomt, geef dit duidelijk en vriendelijk aan.\n"
    "  Stel relevante alternatieven voor met merken die wél passen bij de eerder opgegeven voorkeuren.\n"
    "  Vraag eventueel of de klant zijn voorkeuren wil aanpassen.\n"

    "\n🧠 Let op:\n"
    "- Vraag niet opnieuw naar eerder beantwoorde voorkeuren.\n"
    "- Als de klant terugkomt op een eerdere keuze (zoals formaat of budget), vat die kort samen en vraag of deze gewijzigd moet worden.\n"
    "- Als de klant om aanbiedingen vraagt, ga ervan uit dat het om Expert-aanbiedingen gaat.\n"
    "- Gebruik geen het woord 'productfeed', spreek over 'onze productcatalogus'.\n"
    "- Geef nooit negatieve uitspraken over merken of concurrenten.\n"
    "- Gebruik emoji's alleen als ze iets toevoegen aan de duidelijkheid of sfeer.\n"
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

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=conversation,
            temperature=0.7,
            max_tokens=600
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
    return send_from_directory("static", path)

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled exception: {e}")
    return jsonify({"assistant": f"Interne fout: {e}"}), 500


