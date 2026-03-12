from flask import Flask, render_template, request, redirect, url_for, session, flash, request as flask_request
import sqlite3
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = "mini_social_secret_key"
DB_NAME = "social.db"

UPLOAD_FOLDER_AVATARS = "static/uploads/avatars"
UPLOAD_FOLDER_POSTS = "static/uploads/posts"

app.config["UPLOAD_FOLDER_AVATARS"] = UPLOAD_FOLDER_AVATARS
app.config["UPLOAD_FOLDER_POSTS"] = UPLOAD_FOLDER_POSTS

os.makedirs(UPLOAD_FOLDER_AVATARS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_POSTS, exist_ok=True)


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def unique_filename(filename: str) -> str:
    base, ext = os.path.splitext(secure_filename(filename))
    return f"{base}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            bio TEXT DEFAULT '',
            birth_date TEXT DEFAULT '',
            info TEXT DEFAULT '',
            avatar TEXT DEFAULT ''
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            from_user INTEGER,
            type TEXT,
            post_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT DEFAULT '',
            image TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            UNIQUE(user_id, post_id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (post_id) REFERENCES posts (id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (post_id) REFERENCES posts (id)
        )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS follows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        follower_id INTEGER NOT NULL,
        following_id INTEGER NOT NULL,
        UNIQUE(follower_id, following_id),
        FOREIGN KEY (follower_id) REFERENCES users (id),
        FOREIGN KEY (following_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("home"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not fullname or not username or not password:
            flash("Barcha maydonlarni to‘ldiring.", "error")
            return redirect(url_for("register"))

        conn = get_db_connection()
        existing_user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing_user:
            conn.close()
            flash("Bu username band.", "error")
            return redirect(url_for("register"))

        conn.execute(
            "INSERT INTO users (fullname, username, password) VALUES (?, ?, ?)",
            (fullname, username, password)
        )
        conn.commit()
        conn.close()

        flash("Ro‘yxatdan o‘tish muvaffaqiyatli bajarildi. Endi kiring.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["fullname"] = user["fullname"]
            session["username"] = user["username"]

            flash("Tizimga muvaffaqiyatli kirildi.", "success")
            return redirect(url_for("home"))
        else:
            flash("Login yoki parol noto‘g‘ri.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Hisobdan chiqildi.", "success")
    return redirect(url_for("login"))

@app.route("/chat/<int:user_id>", methods=["GET","POST"])
def chat(user_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    if request.method == "POST":
        text = request.form["message"]

        conn.execute("""
        INSERT INTO messages (sender_id, receiver_id, content)
        VALUES (?, ?, ?)
        """,(session["user_id"], user_id, text))

        conn.commit()

    messages = conn.execute("""
    SELECT messages.*, users.username
    FROM messages
    JOIN users ON messages.sender_id = users.id
    WHERE
    (sender_id=? AND receiver_id=?)
    OR
    (sender_id=? AND receiver_id=?)
    ORDER BY id
    """,(session["user_id"],user_id,user_id,session["user_id"])).fetchall()

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    conn.close()

    return render_template(
        "chat.html",
        messages=messages,
        user=user
    )

@app.route("/notifications")
def notifications():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    notifications = conn.execute("""
        SELECT notifications.*, users.username
        FROM notifications
        JOIN users ON notifications.from_user = users.id
        WHERE notifications.user_id = ?
        ORDER BY notifications.id DESC
    """, (session["user_id"],)).fetchall()

    conn.execute(
        "UPDATE notifications SET is_read=1 WHERE user_id=?",
        (session["user_id"],)
    )

    conn.commit()
    conn.close()

    return render_template("notifications.html", notifications=notifications)

@app.route("/follow/<int:user_id>")
def follow_user(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if user_id == session["user_id"]:
        return redirect(url_for("users"))

    conn = get_db_connection()
    conn.execute("""INSERT INTO notifications (user_id, from_user, type)VALUES (?, ?, 'follow')
        """, (user_id, session["user_id"]))
    existing = conn.execute(
        "SELECT 1 FROM follows WHERE follower_id = ? AND following_id = ?",
            (session["user_id"], user_id)
    ).fetchone()

    if existing:
        conn.execute(
            "DELETE FROM follows WHERE follower_id = ? AND following_id = ?",
            (session["user_id"], user_id)
        )
        flash("Obuna bekor qilindi.", "success")
    else:
        conn.execute(
            "INSERT INTO follows (follower_id, following_id) VALUES (?, ?)",
            (session["user_id"], user_id)
        )
        flash("Obuna bo‘lindi.", "success")

    conn.commit()
    conn.close()

    return redirect(url_for("users"))


@app.route("/home", methods=["GET", "POST"])
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    current_user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        image_file = request.files.get("post_image")
        image_name = ""

        if image_file and image_file.filename != "":
            filename = unique_filename(image_file.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER_POSTS"], filename)
            image_file.save(image_path)
            image_name = filename

        if not content and not image_name:
            flash("Post uchun matn yoki rasm kiriting.", "error")
            conn.close()
            return redirect(url_for("home"))

        conn.execute(
            "INSERT INTO posts (user_id, content, image, created_at) VALUES (?, ?, ?, ?)",
            (
                session["user_id"],
                content,
                image_name,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )
        conn.commit()
        flash("Post joylandi.", "success")

    raw_posts = conn.execute("""
        SELECT posts.*, users.fullname, users.username, users.avatar,
               (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count
        FROM posts
        JOIN users ON posts.user_id = users.id
        ORDER BY posts.id DESC
    """).fetchall()

    posts = []
    for post in raw_posts:
        comments = conn.execute("""
            SELECT comments.*, users.fullname, users.username
            FROM comments
            JOIN users ON comments.user_id = users.id
            WHERE comments.post_id = ?
            ORDER BY comments.id ASC
        """, (post["id"],)).fetchall()

        liked = conn.execute(
            "SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?",
            (session["user_id"], post["id"])
        ).fetchone()

        posts.append({
            "id": post["id"],
            "user_id": post["user_id"],
            "fullname": post["fullname"],
            "username": post["username"],
            "avatar": post["avatar"],
            "content": post["content"],
            "image": post["image"],
            "created_at": post["created_at"],
            "like_count": post["like_count"],
            "liked": liked is not None,
            "comments": comments
        })

    conn.close()
    return render_template("home.html", posts=posts, current_user=current_user)

@app.route("/following_feed")
def following_feed():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    current_user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    raw_posts = conn.execute("""
        SELECT posts.*, users.fullname, users.username, users.avatar,
               (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.user_id IN (
            SELECT following_id
            FROM follows
            WHERE follower_id = ?
        )
        ORDER BY posts.id DESC
    """, (session["user_id"],)).fetchall()

    posts = []
    for post in raw_posts:
        comments = conn.execute("""
            SELECT comments.*, users.fullname, users.username
            FROM comments
            JOIN users ON comments.user_id = users.id
            WHERE comments.post_id = ?
            ORDER BY comments.id ASC
        """, (post["id"],)).fetchall()

        liked = conn.execute(
            "SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?",
            (session["user_id"], post["id"])
        ).fetchone()

        posts.append({
            "id": post["id"],
            "user_id": post["user_id"],
            "fullname": post["fullname"],
            "username": post["username"],
            "avatar": post["avatar"],
            "content": post["content"],
            "image": post["image"],
            "created_at": post["created_at"],
            "like_count": post["like_count"],
            "liked": liked is not None,
            "comments": comments
        })

    conn.close()
    return render_template("following_feed.html", posts=posts, current_user=current_user)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if user is None:
        conn.close()
        return redirect(url_for("home"))

    if request.method == "POST":
        bio = request.form.get("bio", "").strip()
        birth_date = request.form.get("birth_date", "").strip()
        info = request.form.get("info", "").strip()
        avatar_file = request.files.get("avatar")

        if avatar_file and avatar_file.filename != "":
            filename = secure_filename(avatar_file.filename)
            base, ext = os.path.splitext(filename)
            filename = f"{base}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"

            avatar_path = os.path.join(app.config["UPLOAD_FOLDER_AVATARS"], filename)
            avatar_file.save(avatar_path)

            conn.execute("""
                UPDATE users
                SET bio = ?, birth_date = ?, info = ?, avatar = ?
                WHERE id = ?
            """, (bio, birth_date, info, filename, session["user_id"]))
        else:
            conn.execute("""
                UPDATE users
                SET bio = ?, birth_date = ?, info = ?
                WHERE id = ?
            """, (bio, birth_date, info, session["user_id"]))

        conn.commit()
        flash("Profil yangilandi.", "success")

        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

    posts = conn.execute("""
        SELECT * FROM posts
        WHERE user_id = ?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "profile.html",
        user=user,
        user_posts=posts
    )


@app.route("/like/<int:post_id>")
def like_post(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    existing = conn.execute(
        "SELECT * FROM likes WHERE user_id = ? AND post_id = ?",
        (session["user_id"], post_id)
    ).fetchone()

    if existing:
        conn.execute(
            "DELETE FROM likes WHERE user_id = ? AND post_id = ?",
            (session["user_id"], post_id)
        )
    else:
        conn.execute(
            "INSERT INTO likes (user_id, post_id) VALUES (?, ?)",
                (session["user_id"], post_id)
        )
    post = conn.execute(
    "SELECT user_id FROM posts WHERE id=?",(post_id,)).fetchone()

    if post["user_id"] != session["user_id"]:
        conn.execute("""
            INSERT INTO notifications (user_id, from_user, type, post_id)VALUES (?, ?, 'like', ?)
            """, (post["user_id"], session["user_id"], post_id))

    conn.commit()
    conn.close()

    return redirect(flask_request.referrer or url_for("home"))

@app.route("/delete_post/<int:post_id>")
def delete_post(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    post = conn.execute(
        "SELECT * FROM posts WHERE id = ?",
        (post_id,)
    ).fetchone()

    if post is None:
        conn.close()
        flash("Post topilmadi.", "error")
        return redirect(url_for("profile"))

    if post["user_id"] != session["user_id"]:
        conn.close()
        flash("Siz faqat o‘z postingizni o‘chira olasiz.", "error")
        return redirect(url_for("profile"))

    if "image" in post.keys() and post["image"]:
        image_path = os.path.join(app.config["UPLOAD_FOLDER_POSTS"], post["image"])
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass

    conn.execute("DELETE FROM likes WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()

    flash("Post o‘chirildi.", "success")
    return redirect(url_for("profile"))


@app.route("/comment/<int:post_id>", methods=["POST"])
def comment_post(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    content = request.form.get("comment_content", "").strip()

    if not content:
        flash("Komment bo‘sh bo‘lmasin.", "error")
        return redirect(url_for("home"))
    post = conn.execute(
    "SELECT user_id FROM posts WHERE id=?",(post_id,)).fetchone()
    if post["user_id"] != session["user_id"]:
        conn.execute("""
            INSERT INTO notifications (user_id, from_user, type, post_id)VALUES (?, ?, 'comment', ?)
            """, (post["user_id"], session["user_id"], post_id))
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO comments (user_id, post_id, content, created_at) VALUES (?, ?, ?, ?)",
        (
            session["user_id"],
            post_id,
            content,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )
    conn.commit()
    conn.close()

    flash("Komment qo‘shildi.", "success")
    return redirect(url_for("home"))





@app.route("/users")
def users():
    if "user_id" not in session:
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    conn = get_db_connection()

    if search:
        raw_users = conn.execute("""
            SELECT id, fullname, username, avatar, bio
            FROM users
            WHERE (fullname LIKE ? OR username LIKE ?)
            AND id != ?
            ORDER BY id DESC
        """, (f"%{search}%", f"%{search}%", session["user_id"])).fetchall()
    else:
        raw_users = conn.execute("""
            SELECT id, fullname, username, avatar, bio
            FROM users
            WHERE id != ?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()

    users_list = []
    for user in raw_users:
        is_following = conn.execute(
            "SELECT 1 FROM follows WHERE follower_id = ? AND following_id = ?",
            (session["user_id"], user["id"])
        ).fetchone()

        followers_count = conn.execute(
            "SELECT COUNT(*) AS total FROM follows WHERE following_id = ?",
            (user["id"],)
        ).fetchone()["total"]

        following_count = conn.execute(
            "SELECT COUNT(*) AS total FROM follows WHERE follower_id = ?",
            (user["id"],)
        ).fetchone()["total"]

        users_list.append({
            "id": user["id"],
            "fullname": user["fullname"],
            "username": user["username"],
            "avatar": user["avatar"],
            "bio": user["bio"],
            "is_following": is_following is not None,
            "followers_count": followers_count,
            "following_count": following_count
        })

    conn.close()
    return render_template("users.html", users_list=users_list, search=search)

@app.route("/user/<int:user_id>")
def view_user(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if user is None:
        conn.close()
        flash("Foydalanuvchi topilmadi.", "error")
        return redirect(url_for("users"))

    user_posts = conn.execute("""
        SELECT posts.*,
               (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count
        FROM posts
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    followers_count = conn.execute(
        "SELECT COUNT(*) AS total FROM follows WHERE following_id = ?",
        (user_id,)
    ).fetchone()["total"]

    following_count = conn.execute(
        "SELECT COUNT(*) AS total FROM follows WHERE follower_id = ?",
        (user_id,)
    ).fetchone()["total"]

    is_following = conn.execute(
        "SELECT 1 FROM follows WHERE follower_id = ? AND following_id = ?",
        (session["user_id"], user_id)
    ).fetchone()

    conn.close()

    return render_template(
        "view_user.html",
        user=user,
        user_posts=user_posts,
        followers_count=followers_count,
        following_count=following_count,
        is_following=is_following is not None
    )


if __name__ == "__main__":
    app.run(debug=True)
