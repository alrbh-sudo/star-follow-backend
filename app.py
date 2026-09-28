import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
# تفعيل CORS للتواصل بين تطبيق الجوال والسيرفر
CORS(app)

# ==========================================
# 1. البيانات السرية ومفاتيح الربط
# ==========================================
SMM_API_URL = "https://smmcost.com/api/v2"
API_KEY = "6a8f91b0634acdddbea5b0e3e63cc90d"
SERVICE_ID = "1"  # رقم خدمة المتابعين داخل SMMCOST

# كلمة سر لوحة التحكم للأدمن
ADMIN_PASSWORD = "ADMIN1234"

# ==========================================
# 2. قاعدة البيانات المحفوظة بالسيرفر
# ==========================================
users_db = {}         # Structure: { username: { password, uuid } }
device_wallets = {}   # Structure: { uuid: { coins: 100000, diamonds: 0, daily_sent: 0 } }
promo_codes = {
    "STAR100": 10000,
    "BONUS50": 50000
}

# ==========================================
# 3. المسارات البرمجية (API Routes)
# ==========================================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "online",
        "app": "Star Follow Backend Server",
        "message": "السيرفر يعمل بنجاح وبسرعة عالية!"
    }), 200


# ----- أ) تسجيل الدخول وإنشاء الحساب -----
@app.route('/api/auth', methods=['POST'])
def auth():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    device_uuid = data.get('device_uuid', '').strip()
    is_signup = data.get('is_signup', False)

    if not username or not password or not device_uuid:
        return jsonify({"success": False, "message": "جميع الحقول مطلوبة!"}), 400

    # ربط المحفظة بـ UUID الجهاز لضمان توحيد الرصيد مهما تغير الحساب على نفس الجهاز
    if device_uuid not in device_wallets:
        device_wallets[device_uuid] = {
            "coins": 100000,
            "diamonds": 0,
            "daily_sent": 0
        }

    if is_signup:
        if username in users_db:
            return jsonify({"success": False, "message": "اسم المستخدم مسجل مسبقاً!"}), 400
        
        users_db[username] = {
            "password": password,
            "uuid": device_uuid
        }
        return jsonify({
            "success": True,
            "message": "تم إنشاء الحساب بنجاح!",
            "wallet": device_wallets[device_uuid]
        }), 201
    else:
        user = users_db.get(username)
        if not user or user["password"] != password:
            return jsonify({"success": False, "message": "اسم المستخدم أو كلمة المرور غير صحيحة!"}), 401

        return jsonify({
            "success": True,
            "message": "تم تسجيل الدخول بنجاح!",
            "wallet": device_wallets[device_uuid]
        }), 200


# ----- ب) إرسال طلب الرشق الفعلي إلى SMMCOST -----
@app.route('/api/order', methods=['POST'])
def place_order():
    data = request.json or {}
    username = data.get('username', '').strip().replace('@', '')
    followers = data.get('followers', 0)
    coins_cost = data.get('coins_cost', 0)
    device_uuid = data.get('device_uuid', '').strip()

    if not username or not followers or not device_uuid:
        return jsonify({"success": False, "message": "بيانات الطلب غير مكتملة!"}), 400

    wallet = device_wallets.get(device_uuid)
    if not wallet:
        return jsonify({"success": False, "message": "المحفظة غير موجودة!"}), 404

    # 1. التحقق من رصيد العملات
    if wallet["coins"] < coins_cost:
        return jsonify({"success": False, "message": "رصيد العملات غير كافٍ!"}), 400

    # 2. التحقق من الحد اليومي (1000 متابع)
    if wallet["daily_sent"] + followers > 1000:
        return jsonify({
            "success": False,
            "message": "تنبيه: تم تجاوز الحد اليومي المسموح به (1000 متابع يومياً)!"
        }), 400

    # 3. بناء رابط الانستغرام
    instagram_link = f"https://instagram.com/{username}"

    # 4. إرسال الطلب إلى المزود الرئيسي عبر المفتاح السري
    payload = {
        'key': API_KEY,
        'action': 'add',
        'service': SERVICE_ID,
        'link': instagram_link,
        'quantity': followers
    }

    try:
        response = requests.post(SMM_API_URL, data=payload, timeout=12)
        res_data = response.json()

        if 'order' in res_data:
            wallet["coins"] -= coins_cost
            wallet["daily_sent"] += followers

            return jsonify({
                "success": True,
                "message": f"تم إرسال {followers} متابع بنجاح لحساب: {instagram_link}",
                "order_id": res_data['order'],
                "remaining_coins": wallet["coins"]
            }), 200
        else:
            err_msg = res_data.get('error', 'حدث خطأ من مزود الخدمة')
            return jsonify({"success": False, "message": f"خطأ المزود: {err_msg}"}), 500

    except Exception as e:
        return jsonify({"success": False, "message": f"فشل الاتصال بالمزود: {str(e)}"}), 500


# ----- ج) تفعيل كود الهدية (Promo Code) -----
@app.route('/api/redeem', methods=['POST'])
def redeem_code():
    data = request.json or {}
    code = data.get('code', '').strip().upper()
    device_uuid = data.get('device_uuid', '').strip()

    if code in promo_codes:
        bonus = promo_codes[code]
        wallet = device_wallets.get(device_uuid)
        if wallet:
            wallet["coins"] += bonus
            return jsonify({
                "success": True,
                "message": f"مبروك! تم تفعيل الكود وشحن {bonus} عملة بنجاح!",
                "coins": wallet["coins"]
            }), 200
    
    return jsonify({"success": False, "message": "كود الهدية غير صالح أو غير موجود!"}), 400


# ----- د) لوحة تحكم الأدمن (شحن وإنشاء الأكواد) -----
@app.route('/api/admin/recharge', methods=['POST'])
def admin_recharge():
    data = request.json or {}
    admin_pass = data.get('admin_password', '').strip()
    target_uuid = data.get('target_uuid', '').strip()
    coins_to_add = data.get('coins', 0)

    if admin_pass != ADMIN_PASSWORD:
        return jsonify({"success": False, "message": "كلمة سر الأدمن غير صحيحة!"}), 403

    if target_uuid in device_wallets:
        device_wallets[target_uuid]["coins"] += coins_to_add
        return jsonify({
            "success": True,
            "message": f"تم شحن {coins_to_add} عملة للـ ID: {target_uuid} بنجاح!"
        }), 200
    else:
        return jsonify({"success": False, "message": "معرف الجهاز (User ID) غير موجود!"}), 404


@app.route('/api/admin/create-code', methods=['POST'])
def admin_create_code():
    data = request.json or {}
    admin_pass = data.get('admin_password', '').strip()
    new_code = data.get('code', '').strip().upper()
    coins_value = data.get('value', 0)

    if admin_pass != ADMIN_PASSWORD:
        return jsonify({"success": False, "message": "كلمة سر الأدمن غير صحيحة!"}), 403

    if not new_code or coins_value <= 0:
        return jsonify({"success": False, "message": "بيانات الكود غير صالحة!"}), 400

    promo_codes[new_code] = coins_value
    return jsonify({
        "success": True,
        "message": f"تم إنشاء كود الهدية ({new_code}) بقيمة {coins_value} عملة بنجاح!"
    }), 200


# ==========================================
# 4. تشغيل السيرفر
# ==========================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
