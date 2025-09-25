from flask import Flask, request, render_template_string, session, g, redirect, url_for
import sqlite3, os

APP_DB = 'challenge.db'
STARTING_POINTS = 50
TARGET_TRICK_VOTES = 30
FLAG_IMAGE = 'you_have_been_tricked.jpg'  # Place this in static folder

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev_secret_replace_me')

# --- HTML Templates ---
UNIFIED_PAGE = '''
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>30th Halloween Party</title>
<style>
body { background: linear-gradient(135deg,#1a1a1a,#4b0000); font-family: Arial, sans-serif; color:#ffb86b;
       display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px;}
.container{background:rgba(0,0,0,0.6);padding:24px;border-radius:12px;box-shadow:0 8px 20px rgba(0,0,0,0.6);width:800px;max-width:90vw;}
h1{margin:0 0 8px 0;color:#ff9f43;text-align:center}
h2{margin:20px 0 8px 0;color:#ff9f43;text-align:center;font-size:1.2rem}
input[type=text]{width:100%;padding:10px;margin:8px 0;border-radius:8px;border:none;background:#2b0000;color:#ffcc99;text-align:center}
textarea{width:100%;height:80px;background:#2b0000;color:#ffd7b5;border-radius:8px;padding:10px;border:none;resize:vertical;text-align:left}
input[type=submit], .btn {background:#cc6600;color:#1a1a1a;padding:10px 12px;border-radius:8px;border:none;cursor:pointer;margin:4px;}
input[type=submit]:hover, .btn:hover {background:#e67300;}
.row{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;}
.center{display:flex;justify-content:center;margin-top:12px;flex-wrap:wrap;}
.result{background:#2e0000;padding:10px;border-radius:8px;margin:8px 0;color:#ffd7b5;word-wrap:break-word;text-align:center}
.sql-result{background:#1a3a1a;padding:10px;border-radius:8px;margin:8px 0;color:#90ee90;white-space:pre-wrap}
.error{background:#3a1a1a;padding:10px;border-radius:8px;margin:8px 0;color:#ff9999;}
.small{font-size:0.9rem;color:#ffdfba;margin:6px 0;text-align:center}
.section{margin:20px 0;padding:15px;background:rgba(255,255,255,0.03);border-radius:8px;}
table { width:100%; border-collapse: collapse; margin:8px 0; }
th, td { padding:6px 8px; border:1px solid #3a0000; text-align:left; }
a.btn { display:inline-block; text-decoration:none; line-height:28px; }
.victory{background:#2a5a2a;color:#90ee90;padding:15px;border-radius:8px;margin:15px 0;text-align:center;border:2px solid #4a8a4a;}
.flag-section{margin-top:20px;text-align:center;}
.flag-image{max-width:400px;max-height:400px;border-radius:8px;}
.toggle-btn{background:#666600;color:#fff;padding:10px 12px;border-radius:8px;border:none;cursor:pointer;margin:4px;display:block;width:100%;}
.toggle-btn:hover{background:#777700;}
.collapsible{display:none;margin-top:10px;}
.collapsible.show{display:block;}
</style>
<script>
function toggleSection(sectionId, btnId) {
    var section = document.getElementById(sectionId);
    var btn = document.getElementById(btnId);
    
    if (section.classList.contains('show')) {
        section.classList.remove('show');
        btn.textContent = btn.textContent.replace('Hide', 'Show');
    } else {
        section.classList.add('show');
        btn.textContent = btn.textContent.replace('Show', 'Hide');
    }
}
</script>
</head>
<body>
<div class="container">
<h1>🎃 30th Halloween Party 🎃</h1>
<div class="small" style="color:#ff6b6b;font-weight:bold;">Goal: Make 'trick' win!!</div>

<!-- Vote Section -->
<div class="section">
<h2>🗳️ Voting</h2>
<form method="post" action="/">
  <input type="hidden" name="action" value="vote">
  <input type="text" name="choice" placeholder="Type Trick or Treat (or try payloads)" autocomplete="off" />
  <div class="center">
    <input type="submit" value="Submit Vote" />
  </div>
</form>
{% if vote_error %}
  <div class="error">{{ vote_error|safe }}</div>
{% endif %}
</div>

<!-- SQL Console Section -->
<div class="section">
<button class="toggle-btn" id="consoleBtn" onclick="toggleSection('consoleSection', 'consoleBtn')">Show Vote Console</button>
<div id="consoleSection" class="collapsible">
<form method="post" action="/">
<input type="hidden" name="action" value="sql">
<textarea name="clause" placeholder="e.g. SELECT choice, count FROM votes;"></textarea>
<div class="center">
<input type="submit" value="Run SQL" />
</div>
</form>
{% if sql_result %}
  <div class="sql-result">{{ sql_result|safe }}</div>
{% endif %}
{% if sql_error %}
  <div class="error">{{ sql_error|safe }}</div>
{% endif %}
</div>
</div>

<!-- Current Votes Table -->
<div class="section">
<button class="toggle-btn" id="votesBtn" onclick="toggleSection('votesSection', 'votesBtn')">Votes</button>
<div id="votesSection" class="collapsible">
{{ table_html|safe }}
</div>
</div>

<!-- Victory Section -->
{% if trickery_message %}
<div class="victory">
  <div class="result">{{ trickery_message|safe }}</div>
  <div class="flag-section">
    <!-- ritctf{you_have_made_trick_win} -->
    <img src="/static/{{ flag_image }}" class="flag-image" alt="You have been tricked!" />
  </div>
</div>
{% endif %}

<!-- New Challenge Section -->
<div class="section">
<div class="center">
<form method="post" action="/">
<input type="hidden" name="action" value="reset">
<input type="submit" value="🔄 Start New Challenge" style="background:#8b0000;color:#fff;">
</form>
</div>
</div>

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
    # Session-based reset logic
    if 'challenger_started' not in session:
        session['challenger_started'] = True
        reset_votes()
    
    # Initialize variables
    vote_error = None
    sql_result = None
    sql_error = None
    trickery_message = None
    
    # Handle different actions
    action = request.form.get('action', '')
    
    if action == 'vote':
        choice = request.form.get('choice', '').strip()
        if choice:
            db = get_db()
            try:
                db.executescript(f"UPDATE votes SET count = count + 1 WHERE choice = '{choice}';")
                db.commit()
            except Exception as e:
                vote_error = f"❌ SQL error during vote: {e}"
    
    elif action == 'sql':
        clause = request.form.get('clause', '').strip()
        if clause:
            db = get_db()
            try:
                db.executescript(clause)
                db.commit()
                sql_result = "✅ SQL statements executed successfully."
            except Exception as e:
                sql_error = f"❌ SQL error: {e}"
    
    elif action == 'reset':
        # Clear session and reset votes for new challenger
        session.clear()
        session['challenger_started'] = True
        reset_votes()
        sql_result = "🔄 Challenge reset! Starting fresh..."
    
    # Get current vote counts and generate table
    totals = get_votes()
    rows = get_db().execute("SELECT choice, count FROM votes").fetchall()
    table_html = '<table><tr><th>Choice</th><th>Count</th></tr>' + ''.join(f"<tr><td>{r['choice']}</td><td>{r['count']}</td></tr>" for r in rows) + '</table>'
    
    # Check for victory condition
    if totals['trick'] >= TARGET_TRICK_VOTES:
        trickery_message = f"🎉 MAXIMUM TRICKERY ACHIEVED!!! 🎉<br>Goal reached: Trick = {totals['trick']}"
    
    return render_template_string(UNIFIED_PAGE, 
                                  vote_error=vote_error,
                                  sql_result=sql_result,
                                  sql_error=sql_error,
                                  trickery_message=trickery_message,
                                  table_html=table_html,
                                  flag_image=FLAG_IMAGE)

# Legacy route redirect
@app.route('/vote_console')
def vote_console():
    return redirect(url_for('challenge'))

# Legacy route redirect
@app.route('/you_lose')
def you_lose():
    return redirect(url_for('challenge'))

if __name__ == '__main__':
    if not os.path.exists(APP_DB):
        init_db()
    if not os.path.exists(os.path.join('static', FLAG_IMAGE)):
        os.makedirs('static', exist_ok=True)
        print(f"Place '{FLAG_IMAGE}' inside 'static' folder before running.")
    app.run(host='0.0.0.0', port=5000, debug=True)