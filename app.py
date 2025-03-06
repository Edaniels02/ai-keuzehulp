import os
import json
from flask import Flask, request, jsonify
import pandas as pd
import openai

app = Flask(__name__)

# Load product feed from CSV
PRODUCT_FEED_CSV = "data/productfeed.csv"
if os.path.exists(PRODUCT_FEED_CSV):
    df = pd.read_csv(PRODUCT_FEED_CSV)
    products = df.to_dict(orient='records')
else:
    products = []

# OpenAI API Key (ensure to set this as an environment variable)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

@app.route("/", methods=["GET"])
def home():
    return "AI Keuzehulp is running! Use the /ask endpoint."

@app.route("/ask", methods=["POST"])
def ask_ai():
    user_input = request.json.get("question", "")
    
    if not user_input:
        return jsonify({"error": "No question received"}), 400
    
    # Structured AI Flow to guide users towards the best TV choice
    prompt = f"""
    Jij bent de AI Keuzehulp van Expert.nl. Je helpt klanten bij het kiezen van de perfecte televisie. Je stelt eerst enkele vragen om de behoeften van de klant te begrijpen en daarna geef je een concreet advies. Als een klant vraagt om alternatieven, bied je maximaal drie opties.
    
    ✅ **Stel systematisch de volgende vragen**:
    1️⃣ Waarvoor wil je de TV gebruiken? (Dagelijks TV-kijken, Films & Series, Sport, Gaming, Weet ik niet)
    2️⃣ Welk formaat zoek je? (43", 50", 55", 65", 75"+)
    3️⃣ Heb je voorkeur voor een schermtechnologie? (OLED, QLED, LED, Weet ik niet)
    4️⃣ Wat is je budget? (Bijvoorbeeld: Tot €1000, €1000-€1500, Meer dan €1500)
    5️⃣ Wil je extra smartfuncties of specifieke features? (AirPlay, Google TV, HDMI 2.1 voor gaming, Geen voorkeur)
    
    ✅ **Beperk keuzes niet te snel**
    - Zorg ervoor dat er altijd een TV overblijft.
    - Als een exacte match ontbreekt, bied dan 2-3 alternatieven die zo dicht mogelijk aansluiten bij de wensen.
    - Als een TV niet op voorraad is, geef dit aan en bied een vergelijkbaar alternatief.
    
    ✅ **Extra eisen en service vanuit Expert.nl**
    - Nooit negatieve uitspraken over merken.
    - Geen adviezen over concurrenten, je legt uit waarom Expert een goede keuze is (eigen installateurs, 140 fysieke winkels, lokale service).
    
    ✅ **Productinformatie**
    Hier zijn enkele beschikbare TV's die je kunt aanbevelen:
    {json.dumps(products[:5], indent=2)}
    
    🎯 Op basis van bovenstaande instructies, verwerk de vraag van de klant op een professionele en klantvriendelijke manier.
    
    Vraag van de klant: {user_input}
    """
    
    # Call OpenAI API
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "Je bent een AI keuzehulp voor Expert.nl."},
                      {"role": "user", "content": prompt}]
        )
        answer = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        answer = f"Error processing AI response: {str(e)}"
    
    return jsonify({"answer": answer})

@app.route("/products", methods=["GET"])
def get_products():
    return jsonify(products)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8080)
