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

# Vraag flow
questions = [
    "Waarvoor wil je de TV gebruiken? (Dagelijks TV-kijken, Films & Series, Sport, Gaming, Weet ik niet)",
    "Welk formaat zoek je? (43\", 50\", 55\", 65\", 75\"+)",
    "Heb je voorkeur voor een schermtechnologie? (OLED, QLED, LED, Weet ik niet)",
    "Wat is je budget? (Bijvoorbeeld: Tot €1000, €1000-€1500, Meer dan €1500)",
    "Wil je extra smartfuncties of specifieke features? (AirPlay, Google TV, HDMI 2.1 voor gaming, Geen voorkeur)"
]

# OpenAI API prompts
def get_prompt(user_input, current_question):
    return f"""
    Jij bent de AI Keuzehulp van Expert.nl. Je helpt klanten bij het kiezen van de perfecte televisie. 
    Je stelt eerst enkele vragen om de behoeften van de klant te begrijpen en daarna geef je een concreet advies.

    Vragen:
    1. Waarvoor wil je de TV gebruiken?
    2. Welk formaat zoek je?
    3. Heb je voorkeur voor een schermtechnologie?
    4. Wat is je budget?
    5. Wil je extra smartfuncties of specifieke features?

    Huidige vraag: {current_question}
    Antwoord van de klant: {user_input}
    """

@app.route("/", methods=["GET"])
def home():
    return "AI Keuzehulp is running! Use the /ask endpoint."

@app.route("/ask", methods=["GET", "POST"])
def ask_ai():
    if request.method == 'GET':
        # Voor een GET verzoek, stuur de eerste vraag
        return jsonify({
            "answer": questions[0]
        })
    
    elif request.method == 'POST':
        # Als een POST verzoek binnenkomt, stel dan vragen en geef antwoorden via OpenAI
        user_input = request.json.get("question", "")
        
        if not user_input:
            return jsonify({"error": "Geen vraag ontvangen"}), 400
        
        # Vraagnummer bijhouden
        question_index = int(request.json.get("question_index", 0))

        # Geef de juiste vraag gebaseerd op de vorige antwoorden
        if question_index < len(questions):
            current_question = questions[question_index]
        else:
            current_question = "Bedankt voor je antwoorden, hier zijn enkele suggesties gebaseerd op je voorkeuren."

        prompt = get_prompt(user_input, current_question)

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "system", "content": "Je bent een AI keuzehulp voor Expert.nl."},
                          {"role": "user", "content": prompt}]
            )
            answer = response["choices"][0]["message"]["content"].strip()
        except Exception as e:
            answer = f"Fout bij het verwerken van het AI-antwoord: {str(e)}"
        
        return jsonify({"answer": answer, "next_question_index": question_index + 1})

@app.route("/products", methods=["GET"])
def get_products():
    return jsonify(products)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8080)
