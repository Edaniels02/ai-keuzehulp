import os
import logging
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
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

# Utility to format brand list
merk_opties = "\n".join([f"• {chr(65+i)}: {merk}" for i, merk in enumerate(unieke_merken)])

system_prompt = (
    "Je bent de AI Keuzehulp van Expert.nl. Je helpt klanten persoonlijk, vriendelijk en gestructureerd."
    "\n\nStructuur en logica:\n"
    "• Gebruik puntsgewijze lijsten (•) voor opties.\n"
    "• Houd altijd rekening met eerder gegeven antwoorden en geef daarop passende vervolgstappen.\n"
    "• Stel geen opties of technologieën voor die buiten het budget vallen.\n"
    "• Gebruik de productfeed als context en verwijs alleen naar producten die bestaan.\n"
    "• Als een combinatie (zoals OLED 75 inch voor €1000) niet realistisch is, geef dit eerlijk aan en stel een alternatief voor.\n"
    "• Vraag naar accessoires nadat tv's zijn voorgesteld.\n"
    "\nVragenvolgorde:\n"
    "1. Gebruik van de TV (films, sport, gamen, etc)\n"
    "2. Budget\n"
    "3. Merkvoorkeur → Toon alle merken in bulletvorm, alfabetisch\n"
    f"{merk_opties}\n• Z: Geen voorkeur\n"
    "4. Formaat\n"
    "5. Schermtechnologie\n"
    "6. Extra functies\n"
    "\nProductadvies:\n"
    "• Geef maximaal 3 modellen (die echt beschikbaar zijn) binnen budget.\n"
    "• Noem de prijs, beschikbaarheid en geef korte motivatie.\n"
    "• Doe daarna suggesties voor accessoires: max. 2 muurbeugels, 2 kabels etc.\n"
    "\nToon altijd begrip en licht keuzes vriendelijk toe. Houd het gesprek luchtig maar professioneel."
)

@app.route("/")
def home():
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == "281617":
            session["authenticated"] = True
            return redirect("/keuzehulp")
        return "Wachtwoord onjuist. Probeer opnieuw."
    return '''
        <form method="post">
            <h2>Expert Keuzehulp</h2>
            <label>Wachtwoord:</label>
            <input type="password" name="password">
            <input type="submit" value="Inloggen">
        </form>
    '''

@app.route("/keuzehulp")
def keuzehulp():
    if not session.get("authenticated"):
        return redirect("/login")
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

    # Contextuele validatie vooraf
    def is_ambilight_onmogelijk():
        merkkeuzes = [m for m in unieke_merken if m.lower() in " ".join([msg['content'].lower() for msg in conversation])]
        return any(m in merkkeuzes for m in ["LG", "Sony", "Samsung"]) and "ambilight" in user_input.lower()

    if is_ambilight_onmogelijk():
        assistant_reply = "Ambilight is een unieke functie van Philips en dus niet beschikbaar bij LG, Sony of Samsung. Wil je Philips toevoegen aan je voorkeuren of doorgaan zonder Ambilight?"
        conversation.append({"role": "assistant", "content": assistant_reply})
        session["messages"] = conversation
        return jsonify({"assistant": assistant_reply})

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4"),
            messages=conversation,
            temperature=0.7,
            max_tokens=800
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


