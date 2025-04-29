import os
import logging
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_from_directory, session
from flask_cors import CORS
from openai import OpenAI
import re

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")
CORS(app)

# Load product feed
try:
    df = pd.read_csv(os.path.join("data", "productfeed.csv"), skipinitialspace=True)
    df = df[df["categorie"].str.contains("Televisies", na=False)]
    unieke_merken = df["merk"].value_counts().index.tolist()
    logging.info(f"Loaded product feed with {len(df)} TVs from {len(unieke_merken)} merken.")
except Exception as e:
    logging.error(f"Failed to load product feed: {e}")
    df = pd.DataFrame()
    unieke_merken = []

merk_opties = "\n".join([f"• {merk}" for merk in unieke_merken])

system_prompt = (
    "Je bent de AI Keuzehulp van Expert.nl. Je bent behulpzaam, vriendelijk en praat alsof je naast de klant staat in de winkel. "
    "Je stelt korte, duidelijke vragen, en geeft antwoorden in maximaal 5 regels. "
    "Gebruik opsommingen (bullets) en hou het bondig. Reageer vriendelijk en praktisch."
    "\n\nGebruik deze vragenstructuur:\n"
    "• Waarvoor gebruik je de TV?\n"
    "• Wat is je budget?\n"
    "• Heb je een voorkeur voor merk? (opties: {merk_opties})\n"
    "• Welk formaat zoek je? (43\", 50\", 55\", 65\", 75\")\n"
    "• Welke schermtechnologie? (OLED, QLED, LED)\n"
    "• Extra functies (Ambilight, HDMI 2.1, Chromecast)"
    "\n\nLet op:\n"
    "• Stel nooit iets voor dat buiten het budget valt.\n"
    "• Corrigeer direct als een combinatie onrealistisch is.\n"
    "• Gebruik bullets voor keuzes.\n"
)

@app.route("/")
def home():
    return "AI Keuzehulp is actief."

@app.route("/keuzehulp")
def keuzehulp():
    session.clear()
    session['messages'] = [{"role": "system", "content": system_prompt}]
    session['answers'] = {}
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_input = data.get("message")

    if not user_input:
        return jsonify({"assistant": "Ik heb geen vraag ontvangen."})

    conversation = session.get("messages", [{"role": "system", "content": system_prompt}])
    conversation.append({"role": "user", "content": user_input})

    answers = session.get("answers", {})
    if any(k in user_input.lower() for k in ["films", "sport", "gamen", "tv-kijken", "combinatie"]):
        answers['usage'] = user_input
    if any(k in user_input.lower() for k in ["750", "1000", "1500", "2000"]):
        answers['budget'] = user_input
    if any(m.lower() in user_input.lower() for m in unieke_merken):
        answers['brand'] = user_input
    if any(s in user_input for s in ["43", "50", "55", "65", "75"]):
        answers['size'] = user_input
    if any(t in user_input.lower() for t in ["oled", "qled", "led"]):
        answers['technology'] = user_input
    session['answers'] = answers

    notes = []

    if 'budget' in answers and 'size' in answers and 'technology' in answers:
        try:
            budget_val = int(''.join(filter(str.isdigit, answers['budget'])))
            size_val = int(''.join(filter(str.isdigit, answers['size'])))
            tech_val = answers['technology'].lower()

            filtered = df[
                (df['formaat'].str.contains(str(size_val), na=False)) &
                (df['technologie'].str.lower().str.contains(tech_val, na=False)) &
                (df['prijs'] <= budget_val)
            ]

            if filtered.empty:
                notes.append(f"Let op: Er zijn geen {size_val}\" {tech_val.upper()} TV's onder €{budget_val}. Adviseer een kleiner formaat of andere technologie.")

        except Exception as e:
            logging.error(f"Fout bij validatie: {e}")

    MAX_HISTORY = 20
    conversation_trimmed = [conversation[0]] + conversation[-MAX_HISTORY:]

    try:
        client = OpenAI()
        prompt_messages = conversation_trimmed
        if notes:
            prompt_messages.append({"role": "system", "content": ' '.join(notes)})

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4-turbo"),
            messages=prompt_messages,
            temperature=0.65,
            max_tokens=600
        )

        antwoord = response.choices[0].message.content

        # Extra: vervang - of * door echte HTML bullets
        antwoord_html = re.sub(r"(?m)^[-\*]\s+", "<li>", antwoord)
        antwoord_html = antwoord_html.replace("\n", "</li>\n")
        if "<li>" in antwoord_html:
            antwoord_html = "<ul>" + antwoord_html + "</ul>"

        conversation.append({"role": "assistant", "content": antwoord_html})
        session["messages"] = conversation

        return jsonify({"assistant": antwoord_html})
    except Exception as e:
        logging.error(f"OpenAI fout: {e}")
        return jsonify({"assistant": f"Fout bij OpenAI: {e}"}), 500

@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory("static", path)

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled exception: {e}")
    return jsonify({"assistant": f"Interne fout: {e}"}), 500

