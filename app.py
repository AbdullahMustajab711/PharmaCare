from flask import Flask, render_template, request, jsonify, session, redirect, url_for # pyright: ignore[reportMissingImports]
from pymongo import MongoClient # pyright: ignore[reportMissingImports]
from bson.objectid import ObjectId # pyright: ignore[reportMissingImports]
from datetime import datetime, timedelta
import bcrypt # pyright: ignore[reportMissingImports]

app = Flask(__name__)
app.secret_key = "my_super_secret_key_1234567890"

# Database Connection
client = MongoClient("mongodb://localhost:27017/")
db = client["pharmacy_db"]
users = db["users"]
admins = db["admins"]
medicines = db["medicines"]
payments = db["payments"]
orders = db["orders"]
carousel = db["carousel"]
deals = db["deals"]
messages = db["messages"]
brands = db["brands"] 

# ----------------- CREATE DEFAULT ADMIN -----------------
if not admins.find_one({"email": "admin@example.com"}):
    password = bcrypt.hashpw("admin123".encode("utf-8"), bcrypt.gensalt())
    admins.insert_one({
        "owner_name": "Admin",
        "email": "admin@example.com",
        "password": password
    })

# ----------------- PUBLIC LANDING PAGE -----------------
@app.route("/")
def landing_page():
    all_medicines = list(medicines.find())
    all_deals = list(deals.find())
    return render_template("landing_page.html", medicines=all_medicines, deals=all_deals)

# ------------------- REGISTER -------------------
@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    if users.find_one({"email": data["email"]}):
        return jsonify({"message": "Email already exists"}), 400
    hashed_password = bcrypt.hashpw(data["password"].encode("utf-8"), bcrypt.gensalt())
    users.insert_one({
        "owner_name": data["owner_name"],
        "email": data["email"],
        "phone": data["phone"],
        "password": hashed_password,
        "role": "user"
    })
    return jsonify({"message": "Registered successfully"})

# ------------------- LOGIN -------------------
@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user = users.find_one({"email": data["email"]})
    admin = admins.find_one({"email": data["email"]})

    if admin:
        if bcrypt.checkpw(data["password"].encode("utf-8"), admin["password"]):
            session['admin'] = {"name": admin['owner_name'], "email": admin['email']}
            return jsonify({"message": f"Welcome Admin {admin['owner_name']}!", "role": "admin"})
        else:
            return jsonify({"message": "Incorrect password"}), 400

    if user:
        if bcrypt.checkpw(data["password"].encode("utf-8"), user["password"]):
            session['user'] = {"name": user['owner_name'], "email": user['email']}
            session['cart'] = []
            session['wishlist'] = []
            return jsonify({"message": f"Welcome {user['owner_name']}!", "role": "user"})
        else:
            return jsonify({"message": "Incorrect password"}), 400

    return jsonify({"message": "Email not registered"}), 400

# ------------------- USER HOME -------------------
@app.route("/home")
def user_home():
    if 'user' not in session:
        return redirect(url_for('login_page'))
    
    # Fetch all medicines
    all_medicines = list(medicines.find())
    
    # Fetch Top Selling
    top_medicines = list(medicines.find().sort("sold", -1).limit(8))
    for m in top_medicines:
        m['_id'] = str(m['_id'])
    
    # Fetch Carousel Banners
    carousel_banners = list(carousel.find())
    for b in carousel_banners:
        b['_id'] = str(b['_id'])

    # Fetch Active Deals
    all_deals = list(deals.find())
    
    # --- FETCH BRANDS ---
    all_brands = list(brands.find())
    for brand in all_brands:
        brand['_id'] = str(brand['_id'])
    
    # --- LOGIC: Filter medicines that have deals ---
    deal_categories = [deal['category'] for deal in all_deals]
    medicines_with_deals = []
    for med in all_medicines:
        if "All" in deal_categories or med['category'] in deal_categories:
            med['_id'] = str(med['_id'])
            medicines_with_deals.append(med)
    
    if 'wishlist' not in session:
        session['wishlist'] = []
    
    return render_template("user_index.html", 
                         user=session['user'], 
                         medicines=medicines_with_deals, 
                         top_medicines=top_medicines,
                         carousel_banners=carousel_banners,
                         brands=all_brands, 
                         cart=session.get('cart', []), 
                         wishlist=session.get('wishlist', []),
                         deals=all_deals)

# ------------------- MEDICINES PAGE -------------------
@app.route("/medicines")
def medicines_page():
    if 'user' not in session:
        return redirect(url_for('login_page'))
    
    all_medicines = list(medicines.find())
    
    # Convert IDs to string for template compatibility
    for med in all_medicines:
        med['_id'] = str(med['_id'])
        
    # Get distinct categories and sort them
    categories = sorted(list(medicines.distinct("category")))
    
    all_deals = list(deals.find())
    
    if 'wishlist' not in session:
        session['wishlist'] = []

    return render_template("medicines.html", 
                         user=session['user'], 
                         medicines=all_medicines, 
                         cart=session.get('cart', []), 
                         wishlist=session.get('wishlist', []),
                         deals=all_deals,
                         categories=categories)

# ------------------- CART -------------------
@app.route("/user/add_to_cart", methods=["POST"])
def add_to_cart():
    if 'user' not in session:
        return jsonify({"message":"Login first"}), 401
    data = request.json
    med = medicines.find_one({"_id": ObjectId(data["med_id"])})
    if not med: return jsonify({"message":"Medicine not found"}), 404
    if med["quantity"] <= 0: return jsonify({"message":"Medicine out of stock"}), 400

    cart_item = {
        "id": str(med["_id"]), 
        "name": med["name"], 
        "price": med["price"],
        "category": med["category"], 
        "image": med.get("image", "/static/images/default.png")
    }
    session['cart'].append(cart_item)
    session.modified = True
    return jsonify({"message":"Added to cart", "cart": session['cart']})

@app.route("/user/remove_from_cart", methods=["POST"])
def remove_from_cart():
    if 'user' not in session:
        return jsonify({"message":"Login first"}), 401
    data = request.json
    cart = session.get('cart', [])
    new_cart = [item for item in cart if item["id"] != data["med_id"]]
    session['cart'] = new_cart
    session.modified = True
    return jsonify({"message":"Removed from cart", "cart": session['cart']})

# ------------------- WISHLIST -------------------
@app.route("/user/add_to_wishlist", methods=["POST"])
def add_to_wishlist():
    if 'user' not in session:
        return jsonify({"message":"Login first"}), 401
    data = request.json
    med = medicines.find_one({"_id": ObjectId(data["med_id"])})
    if not med: return jsonify({"message":"Medicine not found"}), 404

    wishlist = session.get('wishlist', [])
    if not any(item['id'] == str(med["_id"]) for item in wishlist):
        wishlist_item = {
            "id": str(med["_id"]), 
            "name": med["name"], 
            "price": med["price"],
            "category": med["category"], 
            "image": med.get("image", "/static/images/default.png")
        }
        wishlist.append(wishlist_item)
        session['wishlist'] = wishlist
        session.modified = True
        return jsonify({"message":"Added to wishlist", "wishlist": session['wishlist'], "action": "added"})
    
    return jsonify({"message":"Already in wishlist", "wishlist": session['wishlist'], "action": "exists"})

@app.route("/user/remove_from_wishlist", methods=["POST"])
def remove_from_wishlist():
    if 'user' not in session:
        return jsonify({"message":"Login first"}), 401
    data = request.json
    wishlist = session.get('wishlist', [])
    new_wishlist = [item for item in wishlist if item["id"] != data["med_id"]]
    session['wishlist'] = new_wishlist
    session.modified = True
    return jsonify({"message":"Removed from wishlist", "wishlist": session['wishlist']})

# ------------------- ADMIN DASHBOARD -------------------
@app.route("/dashboard")
def dashboard():
    if 'admin' not in session:
        return redirect(url_for('login_page'))

    all_medicines = list(medicines.find())
    all_deals = list(deals.find())
    all_banners = list(carousel.find())
    all_brands = list(brands.find())

    for med in all_medicines: med['_id'] = str(med['_id'])
    for deal in all_deals: deal['_id'] = str(deal['_id'])
    for b in all_banners: b['_id'] = str(b['_id'])
    for brand in all_brands: brand['_id'] = str(brand['_id'])

    total_medicines = len(all_medicines)
    low_stock = sum(1 for m in all_medicines if m.get("quantity", 0) < 10 and m.get("quantity", 0) > 0)
    out_of_stock = sum(1 for m in all_medicines if m.get("quantity", 0) == 0)
    total_sales_count = sum(m.get("sold", 0) for m in all_medicines)
    total_users_count = users.count_documents({})
    total_revenue = sum(order.get("total", 0) for order in orders.find())

    return render_template(
        "dashboard.html",
        admin=session['admin'],
        medicines=all_medicines,
        deals=all_deals,
        banners=all_banners,
        brands=all_brands, 
        total_medicines=total_medicines,
        low_stock=low_stock,
        out_of_stock=out_of_stock,
        total_sales=total_sales_count,
        total_users=total_users_count,
        total_revenue=total_revenue
    )

@app.route("/admin/dashboard_data")
def dashboard_data():
    if 'admin' not in session:
        return jsonify({"error":"Unauthorized"}), 401
    today = datetime.today()
    
    sales_over_time = {"dates": [], "amounts": []}
    for i in range(7):
        day = today - timedelta(days=6-i)
        start = datetime(day.year, day.month, day.day)
        end = start + timedelta(days=1)
        daily_orders = list(orders.find({"date": {"$gte": start, "$lt": end}}))
        total_amount = sum(order.get("total", 0) for order in daily_orders)
        sales_over_time["dates"].append(day.strftime("%d %b"))
        sales_over_time["amounts"].append(total_amount)

    top_meds_cursor = medicines.find().sort("sold", -1).limit(5)
    top_meds = {"names": [], "sold": []}
    for med in top_meds_cursor:
        top_meds["names"].append(med["name"])
        top_meds["sold"].append(med.get("sold",0))

    in_stock = medicines.count_documents({"quantity": {"$gte": 10}})
    low_stock_count = medicines.count_documents({"quantity": {"$gt": 0, "$lt": 10}})
    out_of_stock_count = medicines.count_documents({"quantity": 0})
    stock_status = {"in_stock": in_stock, "low_stock": low_stock_count, "out_of_stock": out_of_stock_count}

    top_users_pipeline = [
        {"$group": {"_id": "$user_email", "total_spent": {"$sum": "$total"}, "order_count": {"$sum": 1}}},
        {"$sort": {"total_spent": -1}},
        {"$limit": 5}
    ]
    
    top_users_cursor = orders.aggregate(top_users_pipeline)
    top_users_list = []
    for u in top_users_cursor:
        user_info = users.find_one({"email": u["_id"]})
        name = user_info['owner_name'] if user_info else "Unknown User"
        top_users_list.append({
            "name": name,
            "email": u["_id"],
            "spent": round(u["total_spent"], 2),
            "orders": u["order_count"]
        })

    return jsonify({
        "sales_over_time": sales_over_time,
        "top_medicines": top_meds,
        "stock_status": stock_status,
        "top_users": top_users_list
    })

@app.route("/admin/add_banner", methods=["POST"])
def add_banner():
    if 'admin' not in session:
        return jsonify({"message":"Unauthorized"}), 401
    data = request.json
    try:
        carousel.insert_one({
            "title": data.get('title', 'New Offer'),
            "description": data.get('description', ''),
            "image": data.get('image', 'https://via.placeholder.com/800x400'),
            "link": data.get('link', '/shop')
        })
        return jsonify({"message":"Banner added successfully"})
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/admin/delete_banner", methods=["POST"])
def delete_banner():
    if 'admin' not in session:
        return jsonify({"message":"Unauthorized"}), 401
    data = request.json
    try:
        carousel.delete_one({"_id": ObjectId(data['id'])})
        return jsonify({"message":"Banner deleted successfully"})
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}, 500)

@app.route("/admin/add_deal", methods=["POST"])
def add_deal():
    if 'admin' not in session:
        return jsonify({"message":"Unauthorized"}), 401
    data = request.json
    deals.insert_one({
        "title": data['title'],
        "description": data.get('description', ""),
        "discount": data.get('discount', "0%"),
        "code": data.get('code', "OFFER"),
        "category": data.get('category', "All")
    })
    return jsonify({"message":"Deal added successfully"})

@app.route("/admin/delete_deal", methods=["POST"])
def delete_deal():
    if 'admin' not in session:
        return jsonify({"message":"Unauthorized"}), 401
    data = request.json
    try:
        deals.delete_one({"_id": ObjectId(data['id'])})
        return jsonify({"message":"Deal deleted successfully"})
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}, 500)

@app.route("/admin/add_medicine", methods=["POST"])
def add_medicine():
    if 'admin' not in session:
        return jsonify({"message":"Unauthorized"}), 401
    data = request.json
    try:
        medicines.insert_one({
            "name": data['name'],
            "category": data.get('category', "General"),
            "price": float(data['price']),
            "quantity": int(data['quantity']),
            "sold": 0,
            "image": data.get('image', "/static/images/default.png")
        })
        return jsonify({"message":"Medicine added successfully"})
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/admin/delete_medicine", methods=["POST"])
def delete_medicine():
    if 'admin' not in session:
        return jsonify({"message":"Unauthorized"}), 401
    data = request.json
    medicines.delete_one({"_id": ObjectId(data['id'])})
    return jsonify({"message":"Medicine deleted successfully"})

@app.route("/admin/edit_medicine", methods=["POST"])
def edit_medicine():
    if 'admin' not in session:
        return jsonify({"message":"Unauthorized"}), 401
    data = request.json
    medicines.update_one(
        {"_id": ObjectId(data['id'])},
        {"$set": {
            "name": data['name'],
            "category": data.get('category', "General"),
            "price": float(data['price']),
            "quantity": int(data['quantity']),
            "image": data.get('image', "/static/images/default.png")
        }}
    )
    return jsonify({"message":"Medicine updated successfully"})

@app.route("/admin/add_brand", methods=["POST"])
def add_brand():
    if 'admin' not in session:
        return jsonify({"message":"Unauthorized"}), 401
    data = request.json
    try:
        brands.insert_one({
            "name": data['name'],
            "image": data.get('image', "https://via.placeholder.com/100")
        })
        return jsonify({"message":"Brand added successfully"})
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/admin/delete_brand", methods=["POST"])
def delete_brand():
    if 'admin' not in session:
        return jsonify({"message":"Unauthorized"}), 401
    data = request.json
    try:
        brands.delete_one({"_id": ObjectId(data['id'])})
        return jsonify({"message":"Brand deleted successfully"})
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}, 500)

@app.route("/checkout")
def checkout():
    if 'user' not in session: return redirect(url_for('login_page'))
    
    raw_cart = session.get('cart', [])
    user = session['user']
    if not raw_cart: return redirect(url_for('user_home'))
    
    active_deals = list(deals.find())
    processed_cart = []
    subtotal = 0.0
    total_savings = 0.0
    
    for item in raw_cart:
        item_discount_percent = 0
        applied_deal = None
        for deal in active_deals:
            if deal.get('category') == item.get('category') or deal.get('category') == 'All':
                discount_str = deal.get('discount', '0%').replace('%', '')
                try:
                    item_discount_percent = float(discount_str)
                    applied_deal = deal
                except: pass
        
        original_price = float(item['price'])
        if item_discount_percent > 0:
            discount_value = original_price * (item_discount_percent / 100)
            final_price = original_price - discount_value
            total_savings += discount_value
        else:
            final_price = original_price
        subtotal += final_price
        
        processed_cart.append({
            "id": item['id'], "name": item['name'], "image": item['image'],
            "original_price": original_price, "final_price": final_price,
            "discount_percent": item_discount_percent, "applied_deal": applied_deal
        })

    return render_template("checkout.html", cart=processed_cart, user=user, subtotal=round(subtotal, 2), total_savings=round(total_savings, 2))

@app.route("/complete_payment", methods=["POST"])
def complete_payment():
    if 'user' not in session: return jsonify({"message":"Login first"}), 401
    data = request.json
    raw_cart = session.get('cart', [])
    if not raw_cart: return jsonify({"message":"Cart is empty"}), 400
    
    active_deals = list(deals.find())
    total_amount = 0.0
    
    # Calculate total
    for item in raw_cart:
        price = float(item['price'])
        discount = 0
        for deal in active_deals:
            if deal.get('category') == item.get('category') or deal.get('category') == 'All':
                try: discount = float(deal.get('discount', '0%').replace('%', ''))
                except: pass
                break
        final = price * (1 - (discount/100))
        total_amount += final

    # UPDATE STOCK AND SALES COUNT
    for item in raw_cart:
        medicines.update_one(
            {"_id": ObjectId(item['id'])}, 
            {"$inc": {"sold": 1, "quantity": -1}}  # <--- FIXED: Added "quantity": -1
        )
    
    order = {
        "user_email": session['user']['email'], "user_name": session['user']['name'],
        "cart": raw_cart, "total": round(total_amount, 2),
        "payment_info": {"card_last4": data.get("cardNumber", "")[-4:], "method": "Card"},
        "date": datetime.now()
    }
    order_id = orders.insert_one(order).inserted_id
    session['cart'] = []
    session.modified = True
    return jsonify({"message":"Payment successful", "redirect": f"/receipt/{order_id}"})

@app.route("/receipt/<order_id>")
def receipt(order_id):
    if 'user' not in session: return redirect(url_for('login_page'))
    order = orders.find_one({"_id": ObjectId(order_id)})
    if not order or order["user_email"] != session['user']['email']: return "Order not found", 404
    order['_id'] = str(order['_id'])
    all_orders = list(orders.find({"user_email": session['user']['email']}).sort("date", -1))
    for o in all_orders: o['_id'] = str(o['_id'])
    return render_template("receipt.html", order=order, all_orders=all_orders)

@app.route("/user/receipts")
def user_receipts():
    if 'user' not in session: return redirect(url_for('login_page'))
    all_orders = list(orders.find({"user_email": session['user']['email']}).sort("date", -1))
    for o in all_orders: o['_id'] = str(o['_id'])
    return render_template("user_receipts.html", all_orders=all_orders, user=session['user'])

@app.route("/user/update_profile", methods=["POST"])
def update_profile():
    if 'user' not in session: return jsonify({"success":False, "message":"Login first"}), 401
    data = request.json
    users.update_one({"email": session['user']['email']}, {"$set": {"owner_name": data['name'], "phone": data['phone']}})
    session['user']['name'] = data['name']
    session.modified = True
    return jsonify({"success": True, "message":"Profile updated"})

@app.route("/logout")
def logout():
    session.pop('user', None)
    session.pop('admin', None)
    return redirect(url_for('landing_page'))

if __name__ == "__main__":
    app.run(debug=True)