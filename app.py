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

merk_opties = "\n".join([f"• {merk}" for merk in unieke_merken])

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
    "6. Zijn er extra functies belangrijk voor je?\n"
    "• Ambilight\n"
    "• HDMI 2.1\n"
    "• Chromecast\n"
    "• Geen voorkeur\n"
    "\n\nAccessoire-advies:\n"
    "• Als de klant een muurbeugel of accessoire noemt, filter op formaat, bevestigingstype en VESA-maat.\n"
    "• Toon maximaal 2 suggesties met prijs en klikbare link als beschikbaar.\n"
    "\n\nLet op:\n"
    "• Gebruik altijd bullets.\n"
    "• Verzin geen merken die niet in de aangeleverde lijst staan.\n"
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
    if any(keyword in user_input.lower() for keyword in ["films", "sport", "gamen", "tv-kijken", "combinatie"]):
        answers['usage'] = user_input
    if any(keyword in user_input.lower() for keyword in ["750", "1000", "1500", "2000"]):
        answers['budget'] = user_input
    if any(merk.lower() in user_input.lower() for merk in unieke_merken):
        answers['brand'] = user_input
    if any(size in user_input for size in ["43", "50", "55", "65", "75"]):
        answers['size'] = user_input
    if any(tech in user_input.lower() for tech in ["oled", "qled", "led"]):
        answers['technology'] = user_input
    session['answers'] = answers

    notes = []
    suggesties = []

    if 'brand' in answers and 'ambilight' in user_input.lower() and 'philips' not in answers['brand'].lower():
        notes.append("Ambilight is alleen beschikbaar bij Philips.")

    if 'budget' in answers and 'size' in answers and 'technology' in answers:
        try:
            budget_value = int(''.join(filter(str.isdigit, answers['budget'])))
            size_value = int(''.join(filter(str.isdigit, answers['size'])))
            tech_value = answers['technology'].lower()

            filtered_df = df.copy()
            filtered_df = filtered_df[
                (filtered_df['formaat'].str.contains(str(size_value), na=False)) &
                (filtered_df['technologie'].str.lower().str.contains(tech_value, na=False)) &
                (filtered_df['prijs'] <= budget_value)
            ]

            if filtered_df.empty:
                notes.append("Let op: Er zijn geen TV's beschikbaar die voldoen aan het gekozen formaat, technologie en budget.")
                
                # Alternatieven zoeken en sorteren
                alternative_df = df.copy()
                alternative_df = alternative_df[alternative_df['prijs'] <= budget_value]
                alternative_df['sort_formaat'] = alternative_df['formaat'].str.extract(r'(\\d+)').astype(float)
                tech_priority = {'oled': 1, 'qled': 2, 'led': 3}
                alternative_df['sort_technologie'] = alternative_df['technologie'].str.lower().map(tech_priority).fillna(99)
                alternative_df = alternative_df.sort_values(by=['sort_formaat', 'sort_technologie'])

                suggestions = alternative_df[['formaat', 'technologie']].drop_duplicates().values.tolist()
                suggesties = [f"{s[0]} {s[1]}" for s in suggestions]

                if suggesties:
                    notes.append("Mogelijke alternatieven: " + ', '.join(suggesties[:5]))
        except Exception as e:
            logging.error(f"Fout bij realiteitscontrole: {e}")

    MAX_HISTORY = 20
    conversation_trimmed = [conversation[0]] + conversation[-MAX_HISTORY:]

    try:
        client = OpenAI()
        prompt_messages = conversation_trimmed
        if notes:
            prompt_messages.append({"role": "system", "content": "Belangrijke opmerkingen: " + ' '.join(notes)})
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4-turbo"),
            messages=prompt_messages,
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

