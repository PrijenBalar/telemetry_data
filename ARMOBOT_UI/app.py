from flask import Flask, request, render_template, redirect, url_for, session, render_template_string, jsonify, flash
import sqlite3
from sqlite3 import Error
import requests as req

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_armobot'  # Change this in production

# ==========================================
# Real Arm Server Configuration
# ==========================================
ARM_SERVER_URL = 'http://192.168.4.1'  # ESP32 / Arm Server IP
ARM_TIMEOUT = 5  # seconds

def arm_get(path, params=None):
    """Forward a GET request to the arm server and return its response."""
    try:
        r = req.get(f"{ARM_SERVER_URL}{path}", params=params, timeout=ARM_TIMEOUT)
        return r.text, r.status_code
    except req.exceptions.ConnectionError:
        print(f"[ERROR] Cannot reach arm server at {ARM_SERVER_URL}")
        return "Arm server not reachable", 503
    except req.exceptions.Timeout:
        print(f"[ERROR] Arm server timed out ({ARM_TIMEOUT}s)")
        return "Arm server timed out", 504

# Database configuration for local SQLite
DB_FILE = 'armobot_db.sqlite'

def get_db_connection():
    try:
        connection = sqlite3.connect(DB_FILE)
        connection.row_factory = sqlite3.Row  # to return dictionary-like rows
        return connection
    except Error as e:
        print(f"Error while connecting to SQLite: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if conn:
        with conn:
            # Separate table for regular users
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    company  TEXT DEFAULT '',
                    address  TEXT DEFAULT '',
                    city     TEXT DEFAULT '',
                    country  TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Add new columns to existing DB (safe – ignored if column already exists)
            for col in ['company TEXT DEFAULT ""',
                        'address TEXT DEFAULT ""',
                        'city    TEXT DEFAULT ""',
                        'country TEXT DEFAULT ""']:
                try:
                    conn.execute(f'ALTER TABLE users ADD COLUMN {col}')
                except Exception:
                    pass  # column already exists
            # Separate table for admins
            conn.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Default admin account (stored in admins table only)
            try:
                conn.execute("INSERT INTO admins (username, password) VALUES ('admin', 'admin123')")
            except sqlite3.IntegrityError:
                pass
            # Remove admin from users table if it was inserted by old code
            try:
                conn.execute("DELETE FROM users WHERE username = 'admin'")
            except Exception:
                pass
        conn.close()

init_db()

# ==========================================
# Armobot UI Template String
# ==========================================
ARMOBOT_UI_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Robotic Arm Control</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html{background-color:#0f2027;overscroll-behavior:none;font-size:80%}
body{font-family:-apple-system,sans-serif;background:linear-gradient(135deg,#0f2027 0%,#203a43 50%,#2c5364 100%);background-attachment:fixed;color:#fff;min-height:100vh;display:flex;flex-direction:column}
.banner{width:100%;background:#000;overflow:hidden;box-shadow:0 4px 15px rgba(0,0,0,0.5);position:relative;flex-shrink:0}
.banner img{position:absolute;top:50%;transform:translateY(-50%);left:20px;height:auto;max-height:48px;width:auto;display:block;z-index:10;border-radius:4px;box-shadow:0 0 8px rgba(0,217,255,0.3)}
.banner-text{background:linear-gradient(to bottom,rgba(15,32,39,0.95),rgba(15,32,39,1));padding:10px 15px;text-align:center;border-bottom:2px solid rgba(0,217,255,0.3);position:relative}
.banner-title{font-size:1.6em;color:#00d9ff;text-shadow:0 0 12px rgba(0,217,255,0.6);font-weight:700;letter-spacing:1px;margin-bottom:2px}
.banner-subtitle{font-size:0.85em;color:rgba(255,255,255,0.7);margin-top:0}
.btn-logout {
    position: absolute; top: 50%; transform: translateY(-50%); right: 20px; background: rgba(255, 71, 87, 0.2);
    border: 1px solid #ff4757; color: #ff4757; padding: 8px 18px; border-radius: 6px;
    font-weight: bold; cursor: pointer; text-decoration: none; font-size: 0.95em; z-index: 20;
}
.btn-logout:hover { background: #ff4757; color: #fff; }
.container{max-width:100%;margin:0 auto;padding:15px 2%;flex:1;display:flex;flex-direction:column;justify-content:flex-start;width:100%;box-sizing:border-box}

.status{display:inline-block;padding:4px 12px;background:rgba(0,255,127,0.15);border:2px solid #00ff7f;border-radius:20px;color:#00ff7f;font-size:0.8em;font-weight:600;margin:5px 0 15px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:15px;margin-bottom:20px}
.card{background:rgba(255,255,255,0.06);border:1px solid rgba(0,217,255,0.25);border-radius:12px;padding:20px;box-shadow:0 4px 15px rgba(0,0,0,0.3)}
.card-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
.card-title{font-size:1.2em;color:#00d9ff;font-weight:600}
.value{font-size:1.5em;color:#00d9ff;font-weight:700}
.input-box{display:flex;gap:10px;margin-bottom:20px}
.txt-input{flex:1;background:rgba(255,255,255,0.08);border:1px solid rgba(0,217,255,0.3);border-radius:6px;padding:12px 15px;color:#fff;font-size:1em}
.txt-input:focus{outline:none;border-color:#00d9ff;background:rgba(0,217,255,0.12)}
.apply{background:#00d9ff;border:none;border-radius:6px;padding:12px 25px;color:#0f2027;font-weight:700;cursor:pointer;font-size:0.95em}
.apply:active{transform:scale(0.96)}
input[type=range]{-webkit-appearance:none;width:100%;height:8px;border-radius:4px;background:rgba(0,217,255,0.2);outline:none;margin-bottom:15px}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:20px;height:20px;border-radius:50%;background:#00d9ff;cursor:pointer;box-shadow:0 0 8px rgba(0,217,255,0.6)}
input[type=range]::-moz-range-thumb{width:20px;height:20px;border-radius:50%;background:#00d9ff;cursor:pointer;border:none}
.info{font-size:0.85em;color:rgba(255,255,255,0.5);margin-top:10px}
.actions{background:rgba(255,255,255,0.06);border:1px solid rgba(0,217,255,0.25);border-radius:10px;padding:15px 20px;box-shadow:0 4px 15px rgba(0,0,0,0.3);margin-bottom:15px}
.sec-title{font-size:1.3em;color:#00d9ff;margin-bottom:20px;font-weight:600;text-align:center}
.btn-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin-bottom:10px}
.btn-center{display:flex;justify-content:center;margin-top:10px}
.btn-calibrate{padding:15px 40px;border-radius:10px;border:none;font-weight:700;font-size:1.1em;cursor:pointer;background:#ffa500;color:#fff;box-shadow:0 4px 15px rgba(255,165,0,0.4);transition:all 0.2s}
.btn-calibrate:hover{box-shadow:0 6px 20px rgba(255,165,0,0.6);transform:translateY(-2px)}
.btn-calibrate:active{transform:scale(0.96)}
button{padding:12px 15px;border-radius:9px;border:none;font-weight:600;font-size:1em;cursor:pointer;transition:transform 0.15s}
button:active{transform:scale(0.96)}
.btn-pri{background:#00d9ff;color:#0f2027}
.btn-suc{background:#00ff7f;color:#0f2027}
.btn-warn{background:#ffa500;color:#fff}
.btn-dng{background:#ff4757;color:#fff}
@media (max-width:768px){.banner-title{font-size:1.6em}.banner-subtitle{font-size:0.85em}.banner img{max-height:180px}.grid{grid-template-columns:1fr}.btn-calibrate{padding:10px 20px;font-size:0.95em}}
</style></head><body>
<div class="banner">
<a href="/logout" class="btn-logout">Logout</a>
<img src="/static/arnobot.png" alt="Robotic Arm">
<div class="banner-text">
<h1 class="banner-title">🤖 ROBOTIC ARM CONTROL</h1>
<p class="banner-subtitle">Advanced 3-Axis Manipulation System</p>
</div>
</div>
<div class="container">
<div style="text-align:center"><div class="status">● SYSTEM ONLINE ({{ session.get('username') }})</div></div>
<div class="grid">
<div class="card"><div class="card-head"><span class="card-title">⚙️ Axis 1 (Base)</span><span class="value" id="v1">{{ s1 }}°</span></div>
<div class="input-box"><input type="number" class="txt-input" id="i1" placeholder="-175 to 175" min="-175" max="175">
<button class="apply" onclick="apply(1)">Apply</button></div>
<input type="range" min="-175" max="175" value="{{ s1 }}" id="s1" oninput="document.getElementById('v1').innerText=this.value+'°'" onchange="send(1,this.value)">
<div class="info">Range: -175° to 175°</div></div>
<div class="card"><div class="card-head"><span class="card-title">⚙️ Axis 2 (Shoulder)</span><span class="value" id="v2">{{ s2 }}°</span></div>
<div class="input-box"><input type="number" class="txt-input" id="i2" placeholder="Enter angle" min="{{ min_s2 }}" max="{{ max_s2 }}">
<button class="apply" onclick="apply(2)">Apply</button></div>
<input type="range" min="{{ min_s2 }}" max="{{ max_s2 }}" value="{{ s2 }}" id="s2" oninput="document.getElementById('v2').innerText=this.value+'°'" onchange="send(2,this.value)">
<div class="info" id="r2">Range: {{ min_s2 }}° to {{ max_s2 }}°</div></div>
<div class="card"><div class="card-head"><span class="card-title">⚙️ Axis 3 (Elbow)</span><span class="value" id="v3">{{ s3 }}°</span></div>
<div class="input-box"><input type="number" class="txt-input" id="i3" placeholder="Enter angle" min="{{ min_s3 }}" max="{{ max_s3 }}">
<button class="apply" onclick="apply(3)">Apply</button></div>
<input type="range" min="{{ min_s3 }}" max="{{ max_s3 }}" value="{{ s3 }}" id="s3" oninput="document.getElementById('v3').innerText=this.value+'°'" onchange="send(3,this.value)">
<div class="info" id="r3">Range: {{ min_s3 }}° to {{ max_s3 }}°</div></div></div>
<div class="actions"><h2 class="sec-title">⚡ Gripper Control</h2>
<div class="btn-grid"><button class="btn-suc" onclick="fetch('/gripper?action=open')">🖐️ Open Gripper</button>
<button class="btn-suc" onclick="fetch('/gripper?action=close')">✊ Close Gripper</button></div></div>
<div class="actions"><h2 class="sec-title">🎯 Calibration</h2>
<div class="btn-center">
<button class="btn-calibrate" onclick="cal()">🎯 Start Calibration</button>
</div></div>
<div class="actions"><h2 class="sec-title">💾 Position Memory</h2><div class="btn-grid">
<button class="btn-pri" onclick="fetch('/save_movement1')">💾 Save Position 1</button>
<button class="btn-pri" onclick="fetch('/save_movement2')">💾 Save Position 2</button>
<button class="btn-pri" onclick="fetch('/run1')">▶️ Go to Position 1</button>
<button class="btn-pri" onclick="fetch('/run2')">▶️ Go to Position 2</button></div></div>
<div class="actions"><h2 class="sec-title">🔄 Automation – Continuous Pick & Place</h2>
<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap;justify-content:center">
  <label style="color:rgba(255,255,255,0.7);font-size:0.9em">Delay between positions (s):</label>
  <input type="number" id="pp-delay" value="3" min="1" max="60" step="0.5" style="width:80px;background:rgba(255,255,255,0.08);border:1px solid rgba(0,217,255,0.3);border-radius:6px;padding:8px 10px;color:#fff;font-size:1em;text-align:center">
</div>
<div id="pp-status" style="text-align:center;margin-bottom:12px;font-size:0.9em;color:rgba(255,255,255,0.5);min-height:1.2em"></div>
<div class="btn-grid">
  <button id="pp-btn" class="btn-dng" onclick="togglePickPlace()" style="grid-column:1/-1;font-size:1.1em">▶️ Start Continuous Pick & Place</button>
</div></div></div>
<script>
function send(n,v){fetch('/stepper?num='+n+'&angle='+v).then(r=>r.text()).then(()=>{
if(n==2){fetch('/get_range3').then(r=>r.json()).then(rng=>{updateRange('s3','r3',rng,'v3','i3')})}
else if(n==3){fetch('/get_range2').then(r=>r.json()).then(rng=>{updateRange('s2','r2',rng,'v2','i2')})}
});document.getElementById('v'+n).innerText=v+'°'}
function updateRange(sid,rid,rng,vid,iid){var slider=document.getElementById(sid);var input=document.getElementById(iid);
slider.min=rng.min;slider.max=rng.max;input.min=rng.min;input.max=rng.max;
var val=parseInt(slider.value);if(val<rng.min){slider.value=rng.min;document.getElementById(vid).innerText=rng.min+'°'}
else if(val>rng.max){slider.value=rng.max;document.getElementById(vid).innerText=rng.max+'°'}
document.getElementById(rid).innerText='Range: '+rng.min+'° to '+rng.max+'°'}
function apply(n){var input=document.getElementById('i'+n);var val=parseFloat(input.value);var slider=document.getElementById('s'+n);
var min=parseFloat(slider.min);var max=parseFloat(slider.max);if(isNaN(val)){alert('Enter valid number');return}
if(val<min||val>max){alert('Value must be between '+min+' and '+max);return}
slider.value=val;send(n,val);input.value=''}
function cal(){if(confirm('Start calibration? Arm will move to home position.')){fetch('/calibrate').then(()=>{
alert('Calibration complete! All axes are reset to 0°.');
for(let i=1;i<=3;i++){
  var slider=document.getElementById('s'+i);
  var valText=document.getElementById('v'+i);
  if(slider) slider.value=0;
  if(valText) valText.innerText='0°';
}
})}}

// ---- Continuous Pick & Place Loop ----
var ppRunning=false;
var ppCycle=0;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function togglePickPlace(){
  if(ppRunning){stopPickPlace();return;}
  if(!confirm('Start continuous Pick & Place? Arm will loop: Open Gripper → Pos 1 → Close Gripper → Pos 2 → Open Gripper.')){return;}
  ppRunning=true;
  ppCycle=0;
  var btn=document.getElementById('pp-btn');
  btn.textContent='⏹️ Stop Pick & Place';
  btn.style.background='#ff4757';
  runPickPlaceCycle();
}

function stopPickPlace(){
  ppRunning=false;
  var btn=document.getElementById('pp-btn');
  btn.textContent='▶️ Start Continuous Pick & Place';
  btn.style.background='';
  setStatus('⏹️ Stopped after '+ppCycle+' cycle(s).','rgba(255,255,255,0.5)');
}

function setStatus(msg,color){
  var el=document.getElementById('pp-status');
  el.textContent=msg;
  el.style.color=color||'#00d9ff';
}

function getDelay(){
  var d=parseFloat(document.getElementById('pp-delay').value);
  return isNaN(d)||d<0.5?3:d;
}

async function runPickPlaceCycle(){
  while(ppRunning){
    var delay=getDelay()*1000;
    var gripDelay=1000; // 1 second for gripper actions
    
    // Step 1: Open Gripper
    setStatus('🖐️ Opening Gripper...','#00d9ff');
    await fetch('/gripper?action=open');
    await sleep(gripDelay);
    if(!ppRunning) break;
    
    // Step 2: Move to Position 1
    setStatus('🔵 Moving to Position 1...','#00d9ff');
    await fetch('/run1');
    await sleep(delay);
    if(!ppRunning) break;
    
    // Step 3: Close Gripper (Pick)
    setStatus('✊ Closing Gripper (Picking)...','#00ff7f');
    await fetch('/gripper?action=close');
    await sleep(gripDelay);
    if(!ppRunning) break;
    
    // Step 4: Move to Position 2
    setStatus('🟢 Moving to Position 2...','#00ff7f');
    await fetch('/run2');
    await sleep(delay);
    if(!ppRunning) break;
    
    // Step 5: Open Gripper (Place)
    setStatus('🖐️ Opening Gripper (Placing)...','#ffa500');
    await fetch('/gripper?action=open');
    await sleep(gripDelay);
    if(!ppRunning) break;
    
    ppCycle++;
    setStatus('✅ Cycle '+ppCycle+' complete!','#ffa500');
    await sleep(500); // Short pause before next cycle
  }
}
document.addEventListener('DOMContentLoaded',function(){for(let i=1;i<=3;i++){
document.getElementById('i'+i).addEventListener('keypress',e=>{if(e.key==='Enter')apply(i)})}});
</script></body></html>"""

# ==========================================
# Routes
# ==========================================

@app.route('/')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    # Provide default template values matching the original code format string requirements.
    # Note: using render_template_string so we pass context like Jinja variables.
    return render_template_string(
        ARMOBOT_UI_TEMPLATE,
        s1=0, s2=0, s3=0,
        min_s2=-90, max_s2=180,
        min_s3=-90, max_s3=180
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            session['error'] = "Database connection error."
            return redirect(url_for('login'))
        
        try:
            cursor = conn.cursor()
            # Check admins table first
            cursor.execute("SELECT * FROM admins WHERE username = ? AND password = ?", (username, password))
            admin = cursor.fetchone()
            if admin:
                session['logged_in'] = True
                session['username'] = username
                session['is_admin'] = True
                return redirect(url_for('admin_dashboard'))

            # Check regular users table
            cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            user = cursor.fetchone()
            
            if user:
                session['logged_in'] = True
                session['username'] = username
                session['is_admin'] = False
                return redirect(url_for('dashboard'))
            else:
                session['error'] = "Invalid credentials. Access Denied."
        except Error as e:
            session['error'] = f"Database query failed: {e}"
        finally:
            conn.close()
        
        return redirect(url_for('login'))

    error = session.pop('error', None)
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# Admin Routes
# ==========================================

@app.route('/admin')
def admin_dashboard():
    if 'logged_in' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    active_tab = request.args.get('tab', 'users')
        
    conn = get_db_connection()
    users = []
    if conn:
        try:
            cursor = conn.cursor()
            # Only fetch from users table — admins are in a separate table
            cursor.execute("""
                SELECT id, username, company, address, city, country, created_at
                FROM users ORDER BY id ASC
            """)
            users = cursor.fetchall()
        except Error as e:
            flash(f"Database query failed: {e}", 'error')
        finally:
            conn.close()
    
    return render_template('admin.html', users=users, active_tab=active_tab)

@app.route('/admin/add_user', methods=['POST'])
def add_user():
    if 'logged_in' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
        
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    company  = request.form.get('company',  '').strip()
    address  = request.form.get('address',  '').strip()
    city     = request.form.get('city',     '').strip()
    country  = request.form.get('country',  '').strip()
    
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (username, password, company, address, city, country)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, password, company, address, city, country))
            conn.commit()
            flash(f"User '{username}' registered successfully.", "success")
        except Error as e:
            flash(f"Failed to add user: {e}", "error")
        finally:
            conn.close()

    return redirect(url_for('admin_dashboard', tab='register'))

@app.route('/admin/update_user/<int:user_id>', methods=['POST'])
def update_user(user_id):
    if 'logged_in' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
        
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    company  = request.form.get('company',  '').strip()
    address  = request.form.get('address',  '').strip()
    city     = request.form.get('city',     '').strip()
    country  = request.form.get('country',  '').strip()
    
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            if password:
                cursor.execute("""
                    UPDATE users SET username=?, password=?, company=?, address=?, city=?, country=?
                    WHERE id=?
                """, (username, password, company, address, city, country, user_id))
            else:
                cursor.execute("""
                    UPDATE users SET username=?, company=?, address=?, city=?, country=?
                    WHERE id=?
                """, (username, company, address, city, country, user_id))
            conn.commit()
            flash("User updated successfully.", "success")
        except Error as e:
            flash(f"Failed to update user: {e}", "error")
        finally:
            conn.close()
                
    return redirect(url_for('admin_dashboard', tab='update'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'logged_in' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            flash("User deleted successfully.", "success")
        except Error as e:
            flash(f"Failed to delete user: {e}", "error")
        finally:
            conn.close()
                
    return redirect(url_for('admin_dashboard', tab='update'))

# ==========================================
# Arm Control Endpoints — Forward to Real Arm Server (192.168.4.1)
# ==========================================

@app.route('/stepper')
def stepper():
    num   = request.args.get('num', '0')
    angle = request.args.get('angle', '0')
    print(f"--> [CMD] Moving Axis {num} to {angle} degrees -> forwarding to arm")
    return arm_get('/stepper', params={'num': num, 'angle': angle})

@app.route('/get_range2')
def get_range2():
    body, status = arm_get('/get_range2')
    if status == 200:
        try:
            import json
            return jsonify(json.loads(body)), 200
        except Exception:
            pass
    # Fallback defaults
    return jsonify({"min": -90, "max": 180})

@app.route('/get_range3')
def get_range3():
    body, status = arm_get('/get_range3')
    if status == 200:
        try:
            import json
            return jsonify(json.loads(body)), 200
        except Exception:
            pass
    # Fallback defaults
    return jsonify({"min": -90, "max": 180})

@app.route('/gripper')
def gripper():
    action = request.args.get('action', 'unknown')
    print(f"--> [CMD] Gripper: {action.upper()} -> forwarding to arm")
    return arm_get('/gripper', params={'action': action})

@app.route('/calibrate')
def calibrate():
    print("--> [CMD] Calibration -> forwarding to arm")
    return arm_get('/calibrate')

@app.route('/save_movement1')
def save_movement1():
    print("--> [CMD] Save Position 1 -> forwarding to arm")
    return arm_get('/save_movement1')

@app.route('/save_movement2')
def save_movement2():
    print("--> [CMD] Save Position 2 -> forwarding to arm")
    return arm_get('/save_movement2')

@app.route('/run1')
def run1():
    print("--> [CMD] Go To Position 1 -> forwarding to arm")
    return arm_get('/run1')

@app.route('/run2')
def run2():
    print("--> [CMD] Go To Position 2 -> forwarding to arm")
    return arm_get('/run2')

@app.route('/pickplace')
def pickplace():
    print("--> [CMD] Pick & Place -> forwarding to arm")
    return arm_get('/pickplace')

if __name__ == '__main__':
    print("="*50)
    print("ARMOBOT LOCAL TESTING SERVER STARTED")
    print("="*50)
    app.run(debug=True, host='0.0.0.0', port=5000)
