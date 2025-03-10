import os
from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
from supabase import create_client, Client

# 環境変数の読み込み
load_dotenv()

# Supabaseクライアントの初期化
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Flaskアプリケーションの初期化
app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = os.getenv("SECRET_KEY", "default_dev_key")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/lessons")
def lessons():
    # Supabaseからレッスンデータを取得する例
    lessons = supabase.table("lessons").select("*").execute()
    return render_template("lessons.html", lessons=lessons.data)

if __name__ == "__main__":
    app.run(debug=True)