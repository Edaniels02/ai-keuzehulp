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
app.secret_key = os.getenv("SECRET_KEY", "supersecret")  # Needed for session management
CORS(app)

# Load product feed
product_feed_path = os.path.join("data", "productfeed.csv")
df = None
try:
    df = pd.read_csv(product_feed_path, skipinitialspace=True)
    logging.info(f"Loaded product feed with {len(df)} products.")
except Exception as e:
    logging.error(f"Failed to load product feed: {e}")

# Static system prompt for initial context
system_prompt = (
    "Jij bent de Expert AI van Expert.nl. Je helpt klanten met het vinden van de perfecte televisie. "
    "Je begeleidt de klant door een reeks gerichte vragen en zorgt ervoor dat er altijd een geschikte aanbeveling uitkomt.\n\n"
    "🚀 Werkwijze:\n"
    "- Stel systematisch vragen om de behoeften van de klant te achterhalen.\n"
    "- Leid de klant naar een concreet advies op basis van de opgegeven voorkeuren.\n"
    "- Geef altijd een of meerdere opties; er mag geen situatie zijn waarin je geen aanbeveling doet.\n\n"
    "✅ Vragenstructuur:\n"
    "1. Waarvoor wil je de TV gebruiken?\n"
    "2. Welk formaat zoek je?\n"
    "3. Heb je voorkeur voor een schermtechnologie?\n"
    "4. Wat is je budget?\n"
    "5. Wil je extra smartfuncties of specifieke features?\n\n"
    "📌 Advies en Resultaten:\n"
    "- Zorg dat er altijd een TV overblijft.\n"
    "- Als een exacte match ontbreekt, bied dan 2-3 alternatieven die zo dicht mogelijk aansluiten.\n"
    "- Als een TV niet op voorraad is, geef dit aan en bied een alternatief met uitleg.\n\n"
    "✅ Expert.nl Focus:\n"
    "- Geen negatieve uitspraken over merken.\n"
    "- Geen adviezen over of vergelijkingen met andere winkels of webshops.\n"
    "- Geef aan dat je als Expert AI exclusief adviseert voor Expert.nl — met een knipoog of glimlach mag best! 😉\n"
    "- Leg uit waarom Expert een goede keuze is: eigen installateurs, 140 fysieke winkels, lokale service.\n\n"
    "🧠 Let op:\n"
    "- Reageer kort, vriendelijk en duidelijk.\n"
    "- Als de gebruiker een onverwachte vraag stelt, geef daar kort antwoord op en vervolg met een gerichte keuzevraag.\n"
    "- Gebruik emoji's spaarzaam en alleen als ze echt iets toevoegen."
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

    # Retrieve or start session messages
    conversation = session.get("messages", [{"role": "system", "content": system_prompt}])
    conversation.append({"role": "user", "content": user_input})

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=conversation,
            temperature=0.7,
            max_tokens=500
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
