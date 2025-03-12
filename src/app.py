import os
import subprocess
import tempfile
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
from dotenv import load_dotenv
from supabase import create_client, Client

# 環境変数のロード
load_dotenv()

# プロジェクトのルートディレクトリへのパスを計算
# src/app.py から見て、親ディレクトリ（プロジェクトルート）を指定
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates_dir = os.path.join(project_root, 'templates')
static_dir = os.path.join(project_root, 'static')

# Flaskアプリケーションの初期化 - テンプレートとスタティックフォルダを明示的に指定
app = Flask(__name__, 
            template_folder=templates_dir,
            static_folder=static_dir)
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key")

# Supabaseクライアントの初期化
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# 以下にルートを定義
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

@app.route("/code-editor/<exercise_id>")
def code_editor(exercise_id):
    # エクササイズの詳細を取得
    exercise = supabase.table("exercises").select("*").eq("id", exercise_id).execute()
    
    if not exercise.data:
        flash("エクササイズが見つかりませんでした。", "error")
        return redirect(url_for("lessons"))
    
    return render_template("code_editor.html", exercise=exercise.data[0])

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

# 追加のルート定義
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/lessons")
def lessons():
    # レッスン一覧をSupabaseから取得
    lessons_data = supabase.table("lessons").select("*").execute()
    return render_template("lesson.html", lessons=lessons_data.data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # ログイン処理を実装
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            session['user_id'] = response.user.id
            flash('ログインしました', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash('ログインに失敗しました', 'error')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # 新規ユーザー登録処理
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('パスワードが一致しません', 'error')
            return render_template('signup.html')
        
        try:
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "username": username
                    }
                }
            })
            flash('アカウントが作成されました。メールを確認してください。', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('アカウント作成に失敗しました', 'error')
    
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    # ユーザーのダッシュボード表示
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # ユーザー情報取得
    user_response = supabase.auth.get_user(session['user_id'])
    user = user_response.user
    
    # ユーザーの進捗情報取得
    progress = supabase.table("user_progress").select("*").eq("user_id", user.id).execute()
    
    return render_template('dashboard.html', user=user, progress=progress.data)

# jinja2フィルターの設定
@app.template_filter('markdown')
def markdown_filter(text):
    try:
        import markdown
        return markdown.markdown(text)
    except ImportError:
        return text
    
@app.template_filter('datetime')
def datetime_filter(timestamp):
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y年%m月%d日 %H:%M')
    except:
        return timestamp

# デバッグ用のルート - テンプレート検索パスを確認
@app.route('/debug')
def debug():
    return {
        'template_folder': app.template_folder,
        'static_folder': app.static_folder,
        'templates_exist': os.path.exists(app.template_folder),
        'static_exists': os.path.exists(app.static_folder),
        'index_exists': os.path.exists(os.path.join(app.template_folder, 'index.html')),
        'project_files': os.listdir(project_root)
    }

# Herokuで必要なポート設定
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)