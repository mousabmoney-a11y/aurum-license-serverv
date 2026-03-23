from flask import Flask, request, jsonify, session, redirect
import json, random, string
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "aurum-secret"

DB_FILE = "db.json"
ADMINS_FILE = "admins.json"
LOGS_FILE = "logs.json"

# ================= HELPERS =================

def load(file):
    try:
        with open(file) as f:
            return json.load(f)
    except:
        return {}

def save(data, file):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def now():
    return datetime.utcnow()

def gen_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

def log_action(action, key="", admin="system"):
    logs = load(LOGS_FILE)
    logs[str(datetime.utcnow())] = {
        "action": action,
        "key": key,
        "admin": admin
    }
    save(logs, LOGS_FILE)

# ================= LOGIN =================

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    admins = load(ADMINS_FILE)

    email = data["email"]
    password = data["password"]

    if email in admins and admins[email]["password"] == password:
        session["admin"] = email
        return {"status":"ok"}

    return {"status":"fail"}

@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect("/")
    return open("index.html").read()

@app.route("/")
def home():
    return open("login.html").read()

# ================= CREATE LICENSE =================

@app.route("/create", methods=["POST"])
def create():
    db = load(DB_FILE)
    data = request.json

    key = gen_key()

    # expiry
    if data["period"] == "1m":
        expiry = now() + timedelta(days=30)
    elif data["period"] == "2m":
        expiry = now() + timedelta(days=60)
    else:
        expiry = datetime.fromisoformat(data["to"])

    db[key] = {
        "username": data["username"],
        "accounts": [data["account"]] if data.get("account") else [],
        "hwid": data.get("hwid", ""),
        "expiry": str(expiry),
        "status": "active",
        "accounts_used": [],
        "created": str(now())
    }

    save(db, DB_FILE)
    log_action("CREATE", key, session.get("admin","main"))

    return {"key": key}

# ================= VERIFY =================

@app.route("/verify", methods=["POST"])
def verify():
    db = load(DB_FILE)
    data = request.json

    key = data.get("license")
    account = data.get("account")
    hwid = data.get("hwid")

    if key not in db:
        return {"status":"invalid"}

    lic = db[key]

    # 🔴 PAUSED
    if lic["status"] == "paused":
        return {"status":"paused"}

    # 🔴 EXPIRED
    if datetime.fromisoformat(lic["expiry"]) < now():
        return {"status":"expired"}

    # 🔒 DEVICE LOCK
    if lic["hwid"] == "":
        lic["hwid"] = hwid
    elif lic["hwid"] != hwid:
        return {"status":"device_changed"}

    # 📊 ACCOUNT LIMIT = 5
    if account not in lic["accounts_used"]:
        if len(lic["accounts_used"]) >= 5:
            return {"status":"account_limit"}
        lic["accounts_used"].append(account)

    # SAVE ACCOUNT LIST
    if account not in lic["accounts"]:
        lic["accounts"].append(account)

    # 🔥 LIVE TRACKING
    lic["last_seen"] = str(now())

    db[key] = lic
    save(db, DB_FILE)

    log_action("VERIFY", key)

    return {"status":"valid"}

# ================= CONTROL =================

@app.route("/pause", methods=["POST"])
def pause():
    db = load(DB_FILE)
    key = request.json["license"]

    db[key]["status"] = "paused"
    save(db, DB_FILE)

    log_action("PAUSE", key, session.get("admin","main"))
    return {"ok":True}

@app.route("/delete", methods=["POST"])
def delete():
    db = load(DB_FILE)
    key = request.json["license"]

    if key in db:
        del db[key]

    save(db, DB_FILE)
    log_action("DELETE", key, session.get("admin","main"))

    return {"ok":True}

# ================= DATA =================

@app.route("/all")
def all_data():
    return jsonify(load(DB_FILE))

@app.route("/logs")
def logs():
    return jsonify(load(LOGS_FILE))

@app.route("/analytics")
def analytics():
    db = load(DB_FILE)

    total = len(db)
    active = len([k for k in db if db[k]["status"]=="active"])
    paused = len([k for k in db if db[k]["status"]=="paused"])

    return {
        "total": total,
        "active": active,
        "paused": paused
    }

# ================= ADMIN =================

@app.route("/add_admin", methods=["POST"])
def add_admin():
    admins = load(ADMINS_FILE)
    data = request.json

    admins[data["email"]] = {
        "name": data["name"],
        "password": data["password"],
        "expiry": data["expiry"]
    }

    save(admins, ADMINS_FILE)
    log_action("ADD_ADMIN", data["email"])

    return {"ok":True}

@app.route("/admins")
def admins():
    return jsonify(load(ADMINS_FILE))

# ================= START =================

app.run(host="0.0.0.0", port=10000)
