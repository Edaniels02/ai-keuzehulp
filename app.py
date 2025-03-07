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

@app.route("/ask", methods=["GET", "POST"])
def ask_ai():
    if request.method == 'GET':
        # Voor een GET verzoek, stuur een welkom bericht en start het gesprek met de tv-vragen
        return jsonify({
            "answer": "Welkom bij de AI Keuzehulp! Laten we beginnen met het stellen van enkele vragen over tv's. "
                       "1️⃣ Waarvoor wil je de TV gebruiken? (Dagelijks TV-kijken, Films & Series, Sport, Gaming, Weet ik niet)"
        })
    
    elif request.method == 'POST':
        # Als een POST verzoek binnenkomt, stel dan vragen en geef antwoorden via OpenAI
        user_input = request.json.get("question", "")
        
        if not user_input:
            return jsonify({"error": "Geen vraag ontvangen"}), 400
        
        # Start het gesprek met de tv-vragen en stuur verder met OpenAI
        prompt = f"""
        Jij bent de AI Keuzehulp van Expert.nl. Je helpt klanten bij het kiezen van de perfecte televisie. 
        Je stelt eerst enkele vragen om de behoeften van de klant te begrijpen en daarna geef je een concreet advies.
        
        Vraag van de klant: {user_input}
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "system", "content": "Je bent een AI keuzehulp voor Expert.nl."},
                          {"role": "user", "content": prompt}]
            )
            answer = response["choices"][0]["message"]["content"].strip()
        except Exception as e:
            answer = f"Fout bij het verwerken van het AI-antwoord: {str(e)}"
        
        return jsonify({"answer": answer})

@app.route("/products", methods=["GET"])
def get_products():
    return jsonify(products)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8080)

