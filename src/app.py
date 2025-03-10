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

@app.route("/logout")
def logout():
    # Supabaseからログアウト
    supabase.auth.sign_out()
    
    # セッションからユーザー情報を削除
    session.pop("user_id", None)
    session.pop("email", None)
    
    flash("ログアウトしました。", "success")
    return redirect(url_for("index"))

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