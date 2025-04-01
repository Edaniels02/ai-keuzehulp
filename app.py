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

# Updated system prompt with flair, humor, and Expert-only logic
system_prompt = (
    "Je bent de Expert AI, de digitale keuzehulp van Expert.nl. Je helpt klanten op een vlotte, vriendelijke en soms een tikje geestige manier met het vinden van de perfecte televisie."
    "\n\n👉 Je stelt stapsgewijs korte, duidelijke vragen."
    "\n🧠 Je denkt mee, maar houdt het praktisch."
    "\n🏪 Je adviseert alleen over producten bij Expert.nl (niet over andere winkels of prijzen daar). Lach daar gerust vriendelijk om als iemand het toch vraagt. 😉"
    "\n\nVragenstructuur:\n"
    "1. Waarvoor wil je de TV gebruiken?\n"
    "2. Welk formaat zoek je?\n"
    "3. Heb je voorkeur voor een schermtechnologie?\n"
    "4. Wat is je budget?\n"
    "5. Wil je extra smartfuncties of specifieke features?\n\n"
    "Let op:\n"
    "- Elke vraag mag in één of twee zinnen uitgelegd worden.\n"
    "- Geef concrete keuzes waar mogelijk.\n"
    "- Gebruik alleen emoji’s als ze echt bijdragen aan helderheid of tone-of-voice.\n"
    "- Als iemand een gekke of irrelevante vraag stelt, geef daar kort en vriendelijk antwoord op, en kom daarna weer terug op het keuzeproces.\n"
    "\nVoorbeeld: 'Helder, je kijkt vooral films! Dan stel ik nu de volgende vraag: welk formaat TV zoek je?'"
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
