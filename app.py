from flask import Flask, request, jsonify, send_from_directory
import json, os, random, string
from datetime import datetime, timedelta

app = Flask(__name__)

# ================= FILES =================
DB_FILE = "licenses.json"
ADMINS_FILE = "admins.json"
LOG_FILE = "logs.json"
DELETED_FILE = "deleted.json"

# ================= UTILS =================

def load(f):
    if not os.path.exists(f):
        return {}
    with open(f, "r") as file:
        return json.load(file)

def save(f, data):
    with open(f, "w") as file:
        json.dump(data, file, indent=4)

def now():
    return datetime.utcnow()

def gen_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

def log(action, user):
    logs = load(LOG_FILE)
    t = str(now())
    logs[t] = {"action": action, "by": user}
    save(LOG_FILE, logs)

# ================= ROOT =================

@app.route("/")
def home():
    return send_from_directory(".", "login.html")

@app.route("/dashboard")
def dashboard():
    return send_from_directory(".", "index.html")

# ================= LOGIN =================

@app.route("/login", methods=["POST"])
def login():
    admins = load(ADMINS_FILE)
    data = request.json

    email = data.get("email")
    password = data.get("password")

    if email in admins and admins[email]["password"] == password:
        return jsonify({"status": "ok"})
    
    return jsonify({"status": "fail"})

# ================= CREATE ADMIN =================

@app.route("/add_admin", methods=["POST"])
def add_admin():
    admins = load(ADMINS_FILE)

    data = request.json
    email = data["email"]

    admins[email] = {
        "name": data["name"],
        "password": data["password"],
        "permissions": data.get("permissions", {}),
        "expiry": data.get("expiry")
    }

    save(ADMINS_FILE, admins)
    return jsonify({"status": "admin_added"})

# ================= ALL ADMINS =================

@app.route("/admins")
def get_admins():
    return jsonify(load(ADMINS_FILE))

# ================= CREATE LICENSE =================

@app.route("/create", methods=["POST"])
def create():
    db = load(DB_FILE)

    data = request.json

    key = gen_key()

    expiry = None

    if data["period"] == "1m":
        expiry = now() + timedelta(days=30)
    elif data["period"] == "custom":
        expiry = datetime.strptime(data["to"], "%Y-%m-%d")

    db[key] = {
        "username": data["username"],
        "accounts": [],
        "hwid": "",
        "status": "active",
        "expiry": expiry.strftime("%Y-%m-%d") if expiry else "lifetime"
    }

    save(DB_FILE, db)
    log("CREATE_LICENSE", data["username"])

    return jsonify({"license": key})

# ================= VERIFY (EA) =================

@app.route("/verify", methods=["POST"])
def verify():
    db = load(DB_FILE)

    data = request.json

    key = data["license"]
    acc = str(data["account"])
    hwid = data["hwid"]

    if key not in db:
        return "invalid"

    lic = db[key]

    if lic["status"] == "paused":
        return "paused"

    if lic["expiry"] != "lifetime":
        if now() > datetime.strptime(lic["expiry"], "%Y-%m-%d"):
            return "expired"

    # HWID
    if lic["hwid"] == "":
        lic["hwid"] = hwid
    elif lic["hwid"] != hwid:
        return "device_mismatch"

    # accounts max 5
    if acc not in lic["accounts"]:
        if len(lic["accounts"]) >= 5:
            lic["status"] = "blocked"
            return "blocked"
        lic["accounts"].append(acc)

    save(DB_FILE, db)

    return jsonify({"status": "valid"})

# ================= GET ALL =================

@app.route("/all")
def all():
    return jsonify(load(DB_FILE))

# ================= PAUSE =================

@app.route("/pause", methods=["POST"])
def pause():
    db = load(DB_FILE)
    k = request.json["license"]

    if k in db:
        db[k]["status"] = "paused"

    save(DB_FILE, db)
    return jsonify({"ok": True})

# ================= DELETE =================

@app.route("/delete", methods=["POST"])
def delete():
    db = load(DB_FILE)
    deleted = load(DELETED_FILE)

    k = request.json["license"]

    if k in db:
        deleted[k] = db[k]
        del db[k]

    save(DB_FILE, db)
    save(DELETED_FILE, deleted)

    return jsonify({"deleted": True})

# ================= RENEW =================

@app.route("/renew", methods=["POST"])
def renew():
    db = load(DB_FILE)

    k = request.json["license"]

    if k not in db:
        return jsonify({"error": True})

    lic = db[k]

    new_date = datetime.strptime(lic["expiry"], "%Y-%m-%d") + timedelta(days=30)

    lic["expiry"] = new_date.strftime("%Y-%m-%d")
    lic["status"] = "active"

    save(DB_FILE, db)

    return jsonify({"renewed": True})

# ================= START =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
