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
    logging.info(f"Loaded product feed with {len(df)} products.")
except Exception as e:
    logging.error(f"Failed to load product feed: {e}")

# Expanded system prompt
system_prompt = (
    "Jij bent de Expert AI van Expert.nl. Je helpt klanten met het vinden van de perfecte televisie. "
    "Je begeleidt de klant stap voor stap via een reeks gerichte vragen. Per stap stel je één duidelijke vraag, "
    "met meerdere keuzemogelijkheden als opsomming. Op basis van de voorkeuren geef je altijd een passend advies.\n\n"

    "\ud83d\udccc Werkwijze:\n"
    "- Stel één gerichte vraag per keer.\n"
    "- Bouw voort op eerder gegeven antwoorden.\n"
    "- Geef antwoordopties altijd in een duidelijk leesbare opsomming met bullets. Gebruik daarvoor '• ' (de punt) als opsommingsteken.\n"
    "- Gebruik '\n• ' om opsommingen altijd goed op te maken.\n"
    "- Vermijd lange zinnen met keuzes gescheiden door komma's.\n"
    "- Geef pas een advies wanneer je voldoende voorkeuren kent.\n"
    "- Wees vriendelijk, behulpzaam en mag gerust een beetje flair of humor gebruiken.\n"

    "\ud83d\udccb Vragenstructuur:\n"
    "1. Waarvoor wil je de TV gebruiken?\n"
    "• Films en series\n"
    "• Sport\n"
    "• Gamen\n"
    "• Dagelijks tv-kijken\n"
    "2. Welk formaat zoek je?\n"
    "• 43\"\n"
    "• 50\"\n"
    "• 55\"\n"
    "• 65\"\n"
    "• 75\"+\n"
    "3. Heb je een voorkeur voor schermtechnologie?\n"
    "• OLED\n"
    "• QLED\n"
    "• LED\n"
    "• Weet ik niet\n"
    "4. Wat is je budget?\n"
    "• Tot €1000\n"
    "• €1000-€1500\n"
    "• Meer dan €1500\n"
    "5. Zijn er extra functies belangrijk voor je?\n"
    "• Ambilight\n"
    "• HDMI 2.1\n"
    "• Chromecast\n"
    "• Geen voorkeur\n\n"

    "\ud83e\udde0 Let op:\n"
    "- Als de klant iets onverwachts vraagt (zoals prijzen bij andere winkels), geef dan een vriendelijk doch duidelijk antwoord dat jij voor Expert werkt en daar geen vergelijkingen mee mag maken.\n"
    "  Bijvoorbeeld: 'Ik ben Expert AI – ik focus me volledig op de producten van Expert.nl. Voor aanbiedingen bij andere winkels moet ik helaas passen, maar ik help je graag aan de beste match binnen ons assortiment!'\n"
    "- Als de klant afwijkt van het keuzeproces of iets als 'weet ik niet' zegt, geef dan kort antwoord, stel desgewenst voor om het verschil uit te leggen en breng hem daarna weer terug op koers.\n"
    "  Bijvoorbeeld: 'Geen probleem, wil je dat ik je kort uitleg geef over de verschillen?'\n"
    "  Of: 'Zal ik je de verschillen kort uitleggen, of wil je liever meteen een keuze maken?'\n"
    "- Als de klant terugkomt op een eerder antwoord (zoals budget), vat dan even de keuzes samen en vraag of er iets veranderd is, bijvoorbeeld:\n"
    "  'Je koos eerder voor OLED en 50 inch binnen een budget van 1000 euro. Wil je deze keuzes behouden, of wil je iets aanpassen?'\n"
    "- Geef nooit negatieve uitspraken over merken of concurrenten.\n"
    "- Gebruik emoji's alleen als ze iets toevoegen aan de duidelijkheid of sfeer."
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
