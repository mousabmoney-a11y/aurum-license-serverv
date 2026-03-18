from flask import Flask, request, jsonify, send_from_directory
import json, os, random, string
from datetime import datetime, timedelta

app = Flask(__name__)

DB_FILE = "licenses.json"
DELETED_FILE = "deleted.json"

# ================= UTILS =================

def load(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def gen_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

def now():
    return datetime.utcnow()

def parse_date(d):
    return datetime.strptime(d, "%Y-%m-%d")

# ================= LOGIN =================

ADMIN_USER = "admin"
ADMIN_PASS = "1234"

@app.route("/login", methods=["POST"])
def login():
    u = request.json.get("username")
    p = request.json.get("password")

    if u == ADMIN_USER and p == ADMIN_PASS:
        return jsonify({"status":"ok"})
    return jsonify({"status":"fail"})

# ================= CREATE =================

@app.route("/create", methods=["POST"])
def create():
    db = load(DB_FILE)

    username = request.json.get("username")
    period = request.json.get("period")

    expiry = None

    if period == "1m":
        expiry = now() + timedelta(days=30)
    elif period == "2m":
        expiry = now() + timedelta(days=60)
    elif period == "3m":
        expiry = now() + timedelta(days=90)
    elif period == "1y":
        expiry = now() + timedelta(days=365)
    elif period == "2y":
        expiry = now() + timedelta(days=730)
    elif period == "lifetime":
        expiry = None
    elif period == "custom":
        start = parse_date(request.json.get("from"))
        end = parse_date(request.json.get("to"))
        expiry = end

    key = gen_key()

    db[key] = {
        "username": username,
        "accounts": [],
        "hwid": "",
        "status": "active",
        "expiry": expiry.strftime("%Y-%m-%d") if expiry else "lifetime"
    }

    save(DB_FILE, db)

    return jsonify({"license": key})

# ================= VERIFY =================

@app.route("/", methods=["POST"])
def verify():
    db = load(DB_FILE)

    data = request.json
    key = data.get("license")
    account = str(data.get("account"))
    hwid = data.get("hwid")

    if key not in db:
        return "invalid"

    lic = db[key]

    # STATUS
    if lic["status"] == "paused":
        return "paused"

    # EXPIRY
    if lic["expiry"] != "lifetime":
        if now() > parse_date(lic["expiry"]):
            lic["status"] = "expired"
            save(DB_FILE, db)
            return "expired"

    # HWID LOCK
    if lic["hwid"] == "":
        lic["hwid"] = hwid
    elif lic["hwid"] != hwid:
        return "device_mismatch"

    # ACCOUNT LIMIT
    if account not in lic["accounts"]:
        if len(lic["accounts"]) >= 5:
            return "account_limit"
        lic["accounts"].append(account)

    save(DB_FILE, db)

    return jsonify({
        "status":"valid",
        "expiry": lic["expiry"]
    })

# ================= ALL =================

@app.route("/all")
def all():
    return jsonify(load(DB_FILE))

# ================= SEARCH =================

@app.route("/search", methods=["POST"])
def search():
    db = load(DB_FILE)
    username = request.json.get("username")

    results = {}

    for k, v in db.items():
        if v["username"].lower() == username.lower():
            results[k] = v

    return jsonify(results)

# ================= PAUSE =================

@app.route("/pause", methods=["POST"])
def pause():
    db = load(DB_FILE)
    key = request.json.get("license")

    if key in db:
        db[key]["status"] = "paused"

    save(DB_FILE, db)
    return jsonify({"status":"ok"})

# ================= DELETE =================

@app.route("/delete", methods=["POST"])
def delete():
    db = load(DB_FILE)
    deleted = load(DELETED_FILE)

    key = request.json.get("license")

    if key in db:
        deleted[key] = db[key]
        del db[key]

    save(DB_FILE, db)
    save(DELETED_FILE, deleted)

    return jsonify({"status":"deleted"})

# ================= RENEW =================

@app.route("/renew", methods=["POST"])
def renew():
    db = load(DB_FILE)

    key = request.json.get("license")
    period = request.json.get("period")

    if key not in db:
        return jsonify({"status":"error"})

    lic = db[key]

    if lic["expiry"] == "lifetime":
        return jsonify({"status":"lifetime"})

    base = parse_date(lic["expiry"])

    if period == "1m":
        base += timedelta(days=30)
    elif period == "2m":
        base += timedelta(days=60)
    elif period == "3m":
        base += timedelta(days=90)
    elif period == "1y":
        base += timedelta(days=365)
    elif period == "custom":
        base = parse_date(request.json.get("to"))

    lic["expiry"] = base.strftime("%Y-%m-%d")
    lic["status"] = "active"

    save(DB_FILE, db)

    return jsonify({"status":"renewed"})

# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():
    return send_from_directory(".", "index.html")

# ================= HOME =================

@app.route("/status")
def status():
    return "Aurum License Server Running ✅"

# ================= START =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
