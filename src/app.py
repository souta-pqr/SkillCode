import subprocess
import tempfile
import os
from flask import jsonify

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