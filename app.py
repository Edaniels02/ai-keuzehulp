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
df = None
try:
    df = pd.read_csv(os.path.join("data", "productfeed.csv"), skipinitialspace=True)
    logging.info(f"Loaded product feed with {len(df)} products.")
except Exception as e:
    logging.error(f"Failed to load product feed: {e}")

# System prompt with clearly defined route
system_prompt = (
    "Jij bent de Expert AI van Expert.nl. Je helpt klanten met het vinden van de perfecte televisie. "
    "Je begeleidt de klant stap voor stap via een reeks gerichte vragen. Per stap stel je één duidelijke vraag, "
    "met meerdere keuzemogelijkheden als opsomming. Op basis van de voorkeuren geef je altijd een passend advies.\n\n"

    "📌 Werkwijze:\n"
    "- Stel één gerichte vraag per keer.\n"
    "- Herhaal kort relevante input en bouw voort op eerder gegeven antwoorden.\n"
    "- Gebruik duidelijke bulletpoints met opties waar mogelijk.\n"
    "- Geef pas een advies wanneer je voldoende voorkeuren kent.\n\n"

    "📋 Vragenstructuur:\n"
    "1. Waarvoor wil je de TV gebruiken? (bijv. Films, Sport, Gamen, Dagelijks tv-kijken)\n"
    "2. Welk formaat zoek je? (bijv. 43\", 50\", 55\", 65\", 75+")\n"
    "3. Heb je een voorkeur voor schermtechnologie? (bijv. OLED, QLED, LED, Weet ik niet)\n"
    "4. Wat is je budget? (bijv. Tot €1000, €1000-€1500, Meer dan €1500)\n"
    "5. Zijn er extra features die je belangrijk vindt? (bijv. Ambilight, HDMI 2.1, Chromecast)\n\n"

    "🧠 Let op:\n"
    "- Geef korte, duidelijke antwoorden.\n"
    "- Als een gebruiker iets anders vraagt, beantwoord het kort en leid direct terug naar het keuzeproces.\n"
    "- Geef geen info over andere webshops. Jij bent een adviseur van Expert.nl 😉\n"
    "- Gebruik alleen emoji's als ze iets toevoegen aan de leesbaarheid.\n"
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
