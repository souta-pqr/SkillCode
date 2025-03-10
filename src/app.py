import os
import subprocess
import tempfile
import markdown
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
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

# Markdownフィルタを追加
@app.template_filter('markdown')
def render_markdown(text):
    return markdown.markdown(text, extensions=['fenced_code', 'tables', 'nl2br'])

# メインルート
@app.route("/")
def index():
    return render_template("index.html")

# レッスン一覧
@app.route("/lessons")
def lessons():
    # Supabaseからレッスンデータを取得する例
    lessons = supabase.table("lessons").select("*").execute()
    return render_template("lessons.html", lessons=lessons.data)

# レッスン詳細
@app.route("/lesson/<lesson_id>")
def lesson_detail(lesson_id):
    # レッスンの詳細を取得
    lesson = supabase.table("lessons").select("*").eq("id", lesson_id).execute()
    
    if not lesson.data:
        flash("レッスンが見つかりませんでした。", "error")
        return redirect(url_for("lessons"))
    
    lesson_data = lesson.data[0]
    
    # ユーザーがログインしている場合は進捗を取得
    progress = None
    if "user_id" in session:
        user_id = session["user_id"]
        progress_result = supabase.table("user_progress").select("*").eq("user_id", user_id).eq("lesson_id", lesson_id).execute()
        
        if progress_result.data:
            progress = progress_result.data[0]
        else:
            # 進捗レコードがなければ新規作成
            progress = {
                "user_id": user_id,
                "lesson_id": lesson_id,
                "completed": False,
                "last_position": 0
            }
            supabase.table("user_progress").insert(progress).execute()
    
    return render_template("lesson_detail.html", lesson=lesson_data, progress=progress)

# レッスン完了
@app.route("/lesson/<lesson_id>/complete", methods=["POST"])
def complete_lesson(lesson_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "ログインが必要です"}), 401
    
    user_id = session["user_id"]
    
    # レッスンを完了としてマーク
    supabase.table("user_progress").update({
        "completed": True,
        "completed_at": "now()"
    }).eq("user_id", user_id).eq("lesson_id", lesson_id).execute()
    
    return jsonify({"success": True})

# 進捗更新
@app.route("/lesson/<lesson_id>/update-progress", methods=["POST"])
def update_progress(lesson_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "ログインが必要です"}), 401
    
    user_id = session["user_id"]
    position = request.json.get("position", 0)
    
    # 進捗を更新
    supabase.table("user_progress").update({
        "last_position": position
    }).eq("user_id", user_id).eq("lesson_id", lesson_id).execute()
    
    return jsonify({"success": True})

# サインアップ
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        username = request.form.get("username")
        
        try:
            # Supabaseで新規ユーザー登録
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            # ユーザーのプロファイル情報を保存
            user_id = auth_response.user.id
            supabase.table("users").insert({
                "id": user_id,
                "email": email,
                "username": username
            }).execute()
            
            flash("アカウントが作成されました。メールを確認してアカウントを有効化してください。", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"アカウント作成に失敗しました: {str(e)}", "error")
    
    return render_template("signup.html")

# ログイン
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        try:
            # Supabaseでログイン
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            # セッションにユーザー情報を保存
            session["user_id"] = auth_response.user.id
            session["email"] = email
            
            flash("ログインしました。", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"ログインに失敗しました: {str(e)}", "error")
    
    return render_template("login.html")

# ログアウト
@app.route("/logout")
def logout():
    # Supabaseからログアウト
    supabase.auth.sign_out()
    
    # セッションからユーザー情報を削除
    session.pop("user_id", None)
    session.pop("email", None)
    
    flash("ログアウトしました。", "success")
    return redirect(url_for("index"))

# ダッシュボード
@app.route("/dashboard")
def dashboard():
    # ユーザーがログインしているか確認
    if "user_id" not in session:
        flash("ログインが必要です。", "error")
        return redirect(url_for("login"))
    
    # ユーザー情報を取得
    user_id = session["user_id"]
    user = supabase.table("users").select("*").eq("id", user_id).execute()
    
    # ユーザーの学習進捗を取得
    progress = supabase.table("user_progress").select(
        "*, lessons(id, title)"
    ).eq("user_id", user_id).execute()
    
    return render_template("dashboard.html", user=user.data[0], progress=progress.data)

# コードエディタ（エクササイズ指定）
@app.route("/code-editor/<exercise_id>")
def code_editor(exercise_id):
    # エクササイズの詳細を取得
    exercise = supabase.table("exercises").select("*").eq("id", exercise_id).execute()
    
    if not exercise.data:
        flash("エクササイズが見つかりませんでした。", "error")
        return redirect(url_for("lessons"))
    
    return render_template("code_editor.html", exercise=exercise.data[0])

# コードエディタ（空）
@app.route("/code-editor")
def blank_editor():
    # 空のエディタを表示
    default_exercise = {
        "title": "フリーコードエディタ",
        "description": "自由にPythonコードを書いて実行できます。",
        "initial_code": "# ここにPythonコードを書いてください\nprint('Hello, SkillCode!')",
        "hints": []
    }
    
    return render_template("code_editor.html", exercise=default_exercise)

# コード実行API
@app.route("/api/execute-code", methods=["POST"])
def execute_code():
    code = request.json.get("code", "")
    exercise_id = request.json.get("exercise_id")
    
    # 一時ファイルの作成
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
        f.write(code.encode())
        temp_file = f.name
    
    try:
        # コードの実行（サンドボックス化やセキュリティ対策が必要）
        result = subprocess.run(
            ['python', temp_file],
            capture_output=True,
            text=True,
            timeout=10  # 10秒のタイムアウト
        )
        
        # 結果の準備
        response = {
            "stdout": result.stdout,
            "stderr": result.stderr
        }
        
        # エクササイズがある場合は検証
        if exercise_id:
            exercise = supabase.table("exercises").select("*").eq("id", exercise_id).execute()
            if exercise.data:
                exercise_data = exercise.data[0]
                # テストコードの実行
                test_code = exercise_data.get("test_code", "")
                with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
                    # ユーザーコードとテストコードを結合
                    f.write((code + "\n\n" + test_code).encode())
                    test_file = f.name
                
                test_result = subprocess.run(
                    ['python', test_file],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                response["success"] = test_result.returncode == 0
                
                # 失敗した場合はヒントを追加
                if not response["success"] and exercise_data.get("hints"):
                    response["hints"] = exercise_data["hints"][0]  # 最初のヒントを提供
                
                # 一時ファイルの削除
                os.unlink(test_file)
        
        return jsonify(response)
    
    except subprocess.TimeoutExpired:
        return jsonify({
            "stdout": "",
            "stderr": "コードの実行がタイムアウトしました（10秒）。無限ループがないか確認してください。"
        })
    except Exception as e:
        return jsonify({
            "stdout": "",
            "stderr": f"エラーが発生しました: {str(e)}"
        })
    finally:
        # 一時ファイルの削除
        os.unlink(temp_file)

# アプリケーション起動
if __name__ == "__main__":
    app.run(debug=True)