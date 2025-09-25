from flask import Flask, request, render_template_string, session, g
import sqlite3, os

APP_DB = 'challenge.db'
STARTING_POINTS = 50
TARGET_TRICK_VOTES = 30
FLAG_IMAGE = 'you_have_been_tricked.jpg'  # Place this in static folder

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev_secret_replace_me')

# --- HTML Templates ---
CHALLENGE_PAGE = '''
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>30th Halloween Party</title>
<style>
body { background: linear-gradient(135deg,#1a1a1a,#4b0000); font-family: Arial, sans-serif; color:#ffb86b;
       display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
.card{background:rgba(0,0,0,0.6);padding:24px;border-radius:12px;box-shadow:0 8px 20px rgba(0,0,0,0.6);width:520px;}
h1{margin:0 0 8px 0;color:#ff9f43;text-align:center}
input[type=text]{width:100%;padding:10px;margin:12px 0;border-radius:8px;border:none;background:#2b0000;color:#ffcc99;text-align:center}
input[type=submit], .btn {background:#cc6600;color:#1a1a1a;padding:10px 12px;border-radius:8px;border:none;cursor:pointer}
.row{display:flex;gap:8px;justify-content:center}
.center{display:flex;justify-content:center;margin-top:12px;}
.result{background:#2e0000;padding:10px;border-radius:8px;margin-top:12px;color:#ffd7b5;word-wrap:break-word;text-align:center}
.small{font-size:0.9rem;color:#ffdfba;margin-top:6px;text-align:center}
a.btn { display:inline-block; text-decoration:none; line-height:28px; }
</style>
</head>
<body>
<div class="card">
<h1>🎃 30th Halloween Party 🎃</h1>
<div class="small">Points: {{ points }}</div>
<div class="small" style="color:#ff6b6b;font-weight:bold;">Goal: Make 'trick' win!!</div>

<form method="post" action="/">
  <input type="text" name="choice" placeholder="Type Trick or Treat (or try payloads)" autocomplete="off" />
  <div class="row">
    <input type="submit" value="Submit Vote" />
    <a class="btn" href="{{ url_for('vote_console') }}" style="margin-left:8px;">Vote Count</a>
  </div>
</form>

{% if trickery_message %}
  <div class="result">{{ trickery_message|safe }}</div>
  <div class="center">
    <a class="btn" href="{{ url_for('you_lose') }}" target="_blank">See Your Result</a>
  </div>
{% endif %}

<hr style="border:none;border-top:1px solid #3a0000;margin:10px 0" />

<form method="post" action="/">
  <input type="text" name="flag" placeholder="Enter flag here to submit" autocomplete="off" />
  <div class="center">
    <input type="submit" value="Submit Flag" />
  </div>
</form>

{% if result %}
  <div class="result">{{ result|safe }}</div>
{% endif %}
</div>
</body>
</html>
'''

VOTE_CONSOLE_PAGE = '''
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Vote Console</title>
<style>
body { background: #0f0f0f; color:#ffd7b5; font-family: Arial, sans-serif; display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
.panel{background:#1c0b0b;padding:20px;border-radius:10px;width:760px;box-shadow:0 8px 24px rgba(0,0,0,0.7)}
h2{margin:0 0 8px 0;color:#ff9f43;text-align:center}
textarea{width:100%;height:100px;background:#2b0000;color:#ffd7b5;border-radius:8px;padding:10px;border:none;resize:vertical;text-align:left}
input[type=submit], a.button{background:#cc6600;color:#1a1a1a;padding:10px 12px;border-radius:8px;border:none;cursor:pointer;text-decoration:none}
.result{background:#2e0000;padding:10px;border-radius:8px;margin-top:12px;color:#ffd7b5;white-space:pre-wrap}
.center{display:flex;justify-content:center;margin-top:8px;gap:8px}
table { width:100%; border-collapse: collapse; margin-top:8px; }
th, td { padding:6px 8px; border:1px solid #3a0000; text-align:left; }
</style>
</head>
<body>
<div class="panel">
<h2>Vote Console</h2>
<form method="post" action="{{ url_for('vote_console') }}">
<textarea name="clause" placeholder="e.g. SELECT trick from tricks; --"></textarea>
<div class="center">
<input type="submit" value="Run" />
<a class="button" href="{{ url_for('challenge') }}" style="margin-left:8px;">Back to Vote</a>
</div>
</form>

{% if result %}
<div class="result">{{ result|safe }}</div>
{% endif %}

{% if table_html %}
<div style="margin-top:12px;">
<strong>votes</strong>
{{ table_html|safe }}
</div>
{% endif %}
</div>
</body>
</html>
'''

# --- DB helpers ---
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(APP_DB)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_conn(exc):
    db = getattr(g, "_database", None)
    if db:
        db.close()

def init_db():
    db = sqlite3.connect(APP_DB)
    cur = db.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS votes (choice TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0);')
    cur.execute("INSERT OR IGNORE INTO votes (choice, count) VALUES ('trick', 0)")
    cur.execute("INSERT OR IGNORE INTO votes (choice, count) VALUES ('treat', 0)")
    db.commit()
    db.close()

def reset_votes():
    db = get_db()
    db.execute("UPDATE votes SET count = 0")
    db.commit()

def get_votes():
    db = get_db()
    cur = db.execute("SELECT choice, count FROM votes")
    rows = cur.fetchall()
    return {r['choice']: r['count'] for r in rows}

# --- Routes ---
@app.route('/', methods=['GET', 'POST'])
def challenge():
    # New participant: reset votes and session
    if 'participant_started' not in session:
        session['participant_started'] = True
        session['points'] = STARTING_POINTS
        reset_votes()

    result_message = None
    trickery_message = None
    submitted_flag = request.form.get('flag', '').strip()
    choice = request.form.get('choice', '').strip()

    if submitted_flag:
        if submitted_flag == "ritctf{you_have_made_trick_win}":
            result_message = f"🎉 Correct flag! You earned {session.get('points', STARTING_POINTS)} points! 🎃"
        else:
            result_message = "❌ Wrong flag. Try again!"

    elif choice:
        db = get_db()
        try:
            db.executescript(f"UPDATE votes SET count = count + 1 WHERE choice = '{choice}';")
            db.commit()
        except Exception as e:
            result_message = f"❌ SQL error during vote: {e}"

    totals = get_votes()
    if totals['trick'] >= TARGET_TRICK_VOTES:
        trickery_message = f"🎉 MAXIMUM TRICKERY ACHIEVED!!! 🎉<br>Goal reached: Trick = {totals['trick']}"

    return render_template_string(CHALLENGE_PAGE, result=result_message,
                                  trickery_message=trickery_message,
                                  points=session.get('points', STARTING_POINTS))

@app.route('/vote_console', methods=['GET', 'POST'])
def vote_console():
    result_text = None
    table_html = None
    db = get_db()

    if request.method == 'POST':
        clause = request.form.get('clause', '').strip()
        if clause:
            try:
                db.executescript(clause)
                db.commit()
                result_text = "Statements executed."
            except Exception as e:
                result_text = f"SQL error: {e}"

    rows = db.execute("SELECT choice, count FROM votes").fetchall()
    table_html = '<table><tr><th>Choice</th><th>Count</th></tr>' + ''.join(f"<tr><td>{r['choice']}</td><td>{r['count']}</td></tr>" for r in rows) + '</table>'

    return render_template_string(VOTE_CONSOLE_PAGE, result=result_text, table_html=table_html)

@app.route('/you_lose')
def you_lose():
    return f'''
<html>
<head>
<title>You Lose</title>
<style>
body {{
  background: linear-gradient(135deg,#1a1a1a,#4b0000);
  display:flex;
  justify-content:center;
  align-items:center;
  height:100vh;
  margin:0;
}}
</style>
</head>
<body>
<!-- ritctf{{you_have_made_trick_win}} -->
<img src="/static/{FLAG_IMAGE}" width="500" height="500">
</body>
</html>
'''

if __name__ == '__main__':
    if not os.path.exists(APP_DB):
        init_db()
    if not os.path.exists(os.path.join('static', FLAG_IMAGE)):
        os.makedirs('static', exist_ok=True)
        print(f"Place '{FLAG_IMAGE}' inside 'static' folder before running.")
    app.run(port=5000, debug=True)
