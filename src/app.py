import os
import subprocess
import tempfile
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
from dotenv import load_dotenv
from supabase import create_client, Client
from functools import wraps

# 環境変数のロード
load_dotenv()

# プロジェクトのルートディレクトリへのパスを計算
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates_dir = os.path.join(project_root, 'templates')
static_dir = os.path.join(project_root, 'static')

# Flaskアプリケーションの初期化
app = Flask(__name__, 
            template_folder=templates_dir,
            static_folder=static_dir)
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key")

# Supabaseクライアントの初期化
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# ログイン要求デコレータ
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('このページにアクセスするにはログインが必要です', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# 最初のページ - 認証チェック
@app.route("/")
def landing():
    # ユーザーがログイン済みであればダッシュボードへ、そうでなければホームページへ
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template("index.html")

# ホームページ
@app.route("/home")
def index():
    return render_template("index.html")

# レッスン一覧ページ
@app.route("/lessons")
def lessons():
    # レッスン一覧をSupabaseから取得
    lessons_data = supabase.table("lessons").select("*").execute()
    return render_template("lesson.html", lessons=lessons_data.data)

# ダッシュボード（要ログイン）
@app.route('/dashboard')
@login_required
def dashboard():
    # ユーザー情報取得
    try:
        user_response = supabase.auth.get_user(session['user_id'])
        user = user_response.user
        
        # ユーザーの進捗情報取得
        progress = supabase.table("user_progress").select("*").eq("user_id", user.id).execute()
        
        return render_template('dashboard.html', user=user, progress=progress.data)
    except Exception as e:
        flash('ユーザー情報の取得に失敗しました', 'error')
        session.clear()
        return redirect(url_for('login'))

# ログインページ
@app.route('/login', methods=['GET', 'POST'])
def login():
    # すでにログイン済みの場合はダッシュボードへリダイレクト
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    # ログイン処理
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            session['user_id'] = response.user.id
            flash('ログインしました', 'success')
            
            # next パラメータがあればそこにリダイレクト
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash('ログインに失敗しました', 'error')
    
    return render_template('login.html')

# ログアウト処理
@app.route('/logout')
def logout():
    session.clear()
    flash('ログアウトしました', 'success')
    return redirect(url_for('index'))

# サインアップページ
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # すでにログイン済みの場合はダッシュボードへリダイレクト
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
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

# レッスン詳細ページ
@app.route('/lesson/<lesson_id>')
def lesson_detail(lesson_id):
    # レッスンの詳細を取得
    lesson = supabase.table("lessons").select("*").eq("id", lesson_id).execute()
    
    if not lesson.data:
        flash("レッスンが見つかりませんでした。", "error")
        return redirect(url_for("lessons"))
    
    # ユーザーがログインしている場合は進捗情報も取得
    progress = None
    if 'user_id' in session:
        progress_data = supabase.table("user_progress").select("*") \
            .eq("user_id", session['user_id']) \
            .eq("lesson_id", lesson_id) \
            .execute()
        if progress_data.data:
            progress = progress_data.data[0]
    
    return render_template("lesson_detail.html", lesson=lesson.data[0], progress=progress)

# レッスン進捗更新API
@app.route('/lesson/<lesson_id>/update-progress', methods=['POST'])
@login_required
def update_progress(lesson_id):
    data = request.json
    position = data.get('position', 0)
    
    # 進捗情報の更新または作成
    progress_data = supabase.table("user_progress").select("*") \
        .eq("user_id", session['user_id']) \
        .eq("lesson_id", lesson_id) \
        .execute()
    
    if progress_data.data:
        # 既存の進捗情報を更新
        supabase.table("user_progress").update({
            "last_position": position,
            "updated_at": "now()"
        }).eq("id", progress_data.data[0]['id']).execute()
    else:
        # 新しい進捗情報を作成
        supabase.table("user_progress").insert({
            "user_id": session['user_id'],
            "lesson_id": lesson_id,
            "last_position": position,
            "completed": False
        }).execute()
    
    return jsonify({"success": True})

# レッスン完了API
@app.route('/lesson/<lesson_id>/complete', methods=['POST'])
@login_required
def complete_lesson(lesson_id):
    # 進捗情報の更新または作成
    progress_data = supabase.table("user_progress").select("*") \
        .eq("user_id", session['user_id']) \
        .eq("lesson_id", lesson_id) \
        .execute()
    
    if progress_data.data:
        # 既存の進捗情報を更新
        supabase.table("user_progress").update({
            "completed": True,
            "completed_at": "now()",
            "updated_at": "now()"
        }).eq("id", progress_data.data[0]['id']).execute()
    else:
        # 新しい進捗情報を作成
        supabase.table("user_progress").insert({
            "user_id": session['user_id'],
            "lesson_id": lesson_id,
            "completed": True,
            "completed_at": "now()"
        }).execute()
    
    return jsonify({"success": True})

# コードエディター関連
@app.route("/api/execute-code", methods=["POST"])
def execute_code():
    code = request.json.get("code", "")
    exercise_id = request.json.get("exercise_id")
    
    # 一時ファイルの作成
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
        f.write(code.encode())
        temp_file = f.name
    
    try:
        # コードの実行
        result = subprocess.run(
            ['python', temp_file],
            capture_output=True,
            text=True,
            timeout=10
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
                    response["hints"] = exercise_data["hints"][0]
                
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

# デバッグ用のルート
@app.route('/debug')
def debug():
    return {
        'template_folder': app.template_folder,
        'static_folder': app.static_folder,
        'templates_exist': os.path.exists(app.template_folder),
        'static_exists': os.path.exists(app.static_folder),
        'index_exists': os.path.exists(os.path.join(app.template_folder, 'index.html')),
        'project_files': os.listdir(project_root),
        'session': dict(session)
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)