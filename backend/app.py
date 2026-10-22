
import calendar
import math
import os
from datetime import date, datetime, timedelta
from functools import wraps
from io import BytesIO
from pathlib import Path
import numpy as np

from flask import (
    Flask,
    jsonify,
    redirect,
    request,
    send_file,
    send_from_directory,
    session,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
    create_user,
    delete_reading,
    get_db_connection,
    get_latest_reading,
    get_latest_reading_before,
    get_reading_by_date,
    get_reading_by_id,
    get_readings,
    get_tariff_settings,
    get_user_by_email,
    get_user_by_google_sub,
    get_user_by_id,
    init_db,
    link_google_account,
    save_or_update_reading,
    save_tariff_settings,
    DEFAULT_TARIFF_SLABS,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "energy-consumption-system-change-this-secret-key",
)

GOOGLE_CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    "363162487877-57o9frbktb36nasdu56kikejkkvlsjk8.apps.googleusercontent.com",
)

# Change this one value if your electricity tariff is different.

# Change this one value if your electricity tariff is different.
RATE_PER_KWH = float(os.environ.get("TARIFF_RATE_PER_KWH", "6.0"))


def safe_float(value, field_name):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid number.")

    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be a finite number.")

    return number


def user_dict(user):
    if not user:
        return None
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "google_linked": bool(user["google_sub"]),
    }


def row_dict(row):
    if not row:
        return None

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "date": row["reading_date"],
        "reading_date": row["reading_date"],
        "appliance": row["appliance"] or "Whole House",
        "previous_reading": row["previous_reading"],
        "current_reading": row["current_reading"],
        "kwh": round(float(row["kwh"] or 0), 3),
        "units": round(float(row["kwh"] or 0), 3),
        "cost": round(float(row["cost"] or 0), 2),
        "rate_per_kwh": RATE_PER_KWH,
        "created_at": row["created_at"],
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "message": "Login required."}), 401
        return view(*args, **kwargs)
    return wrapped


def get_logged_in_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


@app.get("/")
def home():
    return redirect("/login")


@app.get("/login")
def login_page():
    return send_from_directory(FRONTEND_DIR, "login.html")


@app.get("/dashboard")
def dashboard_page():
    if not session.get("user_id"):
        return redirect("/login")
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/frontend/<path:filename>")
def frontend_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@app.get("/health")
def health():
    return jsonify({
        "success": True,
        "status": "online",
        "service": "Energy Consumption and Prediction Analysis System",
    })


# ---------------- AUTHENTICATION ----------------

@app.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if len(name) < 2:
        return jsonify({"success": False, "message": "Enter a valid name."}), 400

    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"success": False, "message": "Enter a valid email."}), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must contain at least 6 characters."
        }), 400

    if get_user_by_email(email):
        return jsonify({
            "success": False,
            "message": "An account with this email already exists."
        }), 409

    user = create_user(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
    )

    session["user_id"] = user["id"]
    session.permanent = True

    return jsonify({
        "success": True,
        "message": "Account created successfully.",
        "user": user_dict(user),
    }), 201


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    user = get_user_by_email(email)

    if not user or not user["password_hash"]:
        return jsonify({
            "success": False,
            "message": "Invalid email or password."
        }), 401

    if not check_password_hash(user["password_hash"], password):
        return jsonify({
            "success": False,
            "message": "Invalid email or password."
        }), 401

    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "user": user_dict(user),
    })


@app.post("/api/auth/google")
def google_login():
    data = request.get_json(silent=True) or {}
    credential = data.get("credential")

    if not credential:
        return jsonify({
            "success": False,
            "message": "Google credential was not received."
        }), 400

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )

        google_sub = info.get("sub")
        email = str(info.get("email", "")).strip().lower()
        name = str(info.get("name") or email.split("@")[0]).strip()

        if not google_sub or not email:
            raise ValueError("Google account information is incomplete.")

        user = get_user_by_google_sub(google_sub)

        if not user:
            user = get_user_by_email(email)

        if user:
            if not user["google_sub"]:
                link_google_account(user["id"], google_sub)
                user = get_user_by_id(user["id"])
        else:
            user = create_user(
                name=name,
                email=email,
                password_hash=None,
                google_sub=google_sub,
            )

        session.clear()
        session["user_id"] = user["id"]
        session.permanent = True

        return jsonify({
            "success": True,
            "message": "Google login successful.",
            "user": user_dict(user),
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "message": f"Google authentication failed: {exc}"
        }), 401


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})


@app.get("/api/me")
def current_user():
    user = get_logged_in_user()

    if not user:
        return jsonify({"success": False, "user": None}), 401

    return jsonify({
        "success": True,
        "user": user_dict(user),
    })


# ---------------- ENERGY READINGS ----------------

@app.get("/api/readings")
@login_required
def readings():
    user_id = session["user_id"]

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    days_arg = request.args.get("days")
    if days_arg:
        try:
            days_count = int(days_arg)
            start_date = (date.today() - timedelta(days=days_count)).isoformat()
        except ValueError:
            pass

    try:
        limit = int(request.args.get("limit", 500))
    except ValueError:
        limit = 500

    limit = max(1, min(limit, 1000))

    rows = get_readings(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    return jsonify({
        "success": True,
        "rate_per_kwh": RATE_PER_KWH,
        "readings": [row_dict(row) for row in rows],
    })


@app.post("/api/readings")
@login_required
def add_reading():
    data = request.get_json(silent=True) or {}
    user_id = session["user_id"]

    reading_date = str(
        data.get("date") or data.get("reading_date") or date.today().isoformat()
    ).strip()

    try:
        selected_date = date.fromisoformat(reading_date)
    except ValueError:
        return jsonify({
            "success": False,
            "message": "Date must be in YYYY-MM-DD format.",
            "error": "Date must be in YYYY-MM-DD format."
        }), 400

    if selected_date > date.today():
        return jsonify({
            "success": False,
            "message": "A future date cannot be recorded.",
            "error": "A future date cannot be recorded."
        }), 400

    appliance = str(data.get("appliance") or "Main Household Meter").strip()[:80]

    previous_raw = data.get("previous_reading")
    current_raw = data.get("current_reading")

    if previous_raw is None and current_raw is None:
        if data.get("kwh") is None and data.get("units") is None:
            return jsonify({
                "success": False,
                "message": "Enter previous and current meter readings.",
                "error": "Enter previous and current meter readings."
            }), 400

        try:
            kwh = safe_float(data.get("kwh", data.get("units")), "Energy usage")
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc), "error": str(exc)}), 400

        if kwh < 0:
            return jsonify({
                "success": False,
                "message": "Energy usage cannot be negative.",
                "error": "Energy usage cannot be negative."
            }), 400

        existing = get_reading_by_date(user_id, reading_date)
        if existing and existing["current_reading"] is not None:
            previous_reading = float(existing["previous_reading"] or 0)
            current_reading = float(existing["current_reading"])
        else:
            previous_reading = None
            current_reading = None
    else:
        try:
            previous_reading = safe_float(previous_raw, "Previous meter reading")
            current_reading = safe_float(current_raw, "Current meter reading")
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc), "error": str(exc)}), 400

        if previous_reading < 0 or current_reading < 0:
            return jsonify({
                "success": False,
                "message": "Meter readings cannot be negative.",
                "error": "Meter readings cannot be negative."
            }), 400

        if current_reading < previous_reading:
            return jsonify({
                "success": False,
                "message": "Current meter reading must be greater than or equal to previous meter reading.",
                "error": "Current meter reading must be greater than or equal to previous meter reading."
            }), 400

        kwh = round(current_reading - previous_reading, 2)

    if kwh > 100000:
        return jsonify({
            "success": False,
            "message": "The entered consumption is unusually high. Check meter readings.",
            "error": "The entered consumption is unusually high. Check meter readings."
        }), 400

    cost = round(kwh * RATE_PER_KWH, 2)

    row = save_or_update_reading(
        user_id=user_id,
        reading_date=reading_date,
        appliance=appliance,
        previous_reading=previous_reading,
        current_reading=current_reading,
        kwh=kwh,
        cost=cost,
    )

    return jsonify({
        "success": True,
        "message": "Daily meter reading saved successfully.",
        "reading": row_dict(row),
    })


@app.delete("/api/readings/<int:reading_id>")
@login_required
def remove_reading(reading_id):
    deleted = delete_reading(session["user_id"], reading_id)

    if not deleted:
        return jsonify({
            "success": False,
            "message": "Reading not found."
        }), 404

    return jsonify({
        "success": True,
        "message": "Reading deleted successfully."
    })


# ---------------- DASHBOARD / ANALYTICS ----------------

def average(values):
    return sum(values) / len(values) if values else 0.0


def compute_bill_breakdown(units, slabs=None, fixed_charge=50.0, tax_rate=5.0):
    if slabs is None:
        slabs = DEFAULT_TARIFF_SLABS
    remaining = max(0.0, float(units))
    breakdown = []
    energy_charges = 0.0

    prev_limit = 0.0
    for slab in slabs:
        limit = slab.get("limit")
        rate = float(slab.get("rate", 0.0))
        label = slab.get("label", "")

        if limit is None:
            tier_capacity = remaining
        else:
            tier_capacity = max(0.0, min(remaining, float(limit) - prev_limit))
            prev_limit = float(limit)

        tier_cost = tier_capacity * rate
        energy_charges += tier_cost
        remaining -= tier_capacity

        breakdown.append({
            "label": label,
            "units": round(tier_capacity, 2),
            "rate": rate,
            "cost": round(tier_cost, 2),
        })

    tax_amount = (energy_charges + fixed_charge) * (tax_rate / 100.0)
    total_bill = energy_charges + fixed_charge + tax_amount

    return {
        "breakdown": breakdown,
        "energy_charges": round(energy_charges, 2),
        "fixed_charge": round(fixed_charge, 2),
        "tax_amount": round(tax_amount, 2),
        "total_bill": round(total_bill, 2),
    }


def compute_ml_forecast(all_readings, tariff_settings=None):
    sorted_readings = sorted(all_readings, key=lambda r: r["reading_date"])

    if len(sorted_readings) < 2:
        return {
            "r2_score": 0.0,
            "formula": "y = mx + c (requires >= 2 readings)",
            "trend": "Log at least 2 daily readings to activate ML model",
            "month_forecast_kwh": 0.0,
            "predicted_bill": 0.0,
            "history_dates": [r["reading_date"] for r in sorted_readings],
            "history_values": [round(float(r["kwh"] or 0), 2) for r in sorted_readings],
            "regression_line": [round(float(r["kwh"] or 0), 2) for r in sorted_readings],
            "projected_dates": [],
            "projected_values": [],
        }

    recent = sorted_readings[-60:]
    dates = [r["reading_date"] for r in recent]
    y = np.array([float(r["kwh"] or 0) for r in recent], dtype=float)
    x = np.arange(len(y)).reshape(-1, 1)

    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import r2_score

        model = LinearRegression()
        model.fit(x, y)
        y_pred = model.predict(x)
        r2 = max(0.0, min(1.0, float(r2_score(y, y_pred))))
        slope = float(model.coef_[0])
        intercept = float(model.intercept_)

        future_x = np.arange(len(y), len(y) + 30).reshape(-1, 1)
        future_y = np.clip(model.predict(future_x), 0, None)

        last_date = datetime.strptime(dates[-1], "%Y-%m-%d").date()
        projected_dates = [(last_date + timedelta(days=i + 1)).strftime("%m/%d") for i in range(30)]
        projected_values = [round(float(val), 2) for val in future_y]

        total_predicted_kwh = float(np.sum(future_y))
        slabs = tariff_settings.get("slabs") if tariff_settings else None
        fixed_c = tariff_settings.get("fixed_charge", 50.0) if tariff_settings else 50.0
        tax_r = tariff_settings.get("tax_rate", 5.0) if tariff_settings else 5.0
        predicted_bill_info = compute_bill_breakdown(total_predicted_kwh, slabs, fixed_c, tax_r)

        trend_desc = "Increasing demand (+)" if slope > 0.02 else ("Decreasing demand (-)" if slope < -0.02 else "Stable consumption")
        sign = "+" if intercept >= 0 else "-"
        formula = f"y = {slope:.3f}x {sign} {abs(intercept):.2f}"

        return {
            "r2_score": round(r2, 4),
            "formula": formula,
            "trend": trend_desc,
            "month_forecast_kwh": round(total_predicted_kwh, 2),
            "predicted_bill": predicted_bill_info["total_bill"],
            "history_dates": dates,
            "history_values": [round(float(val), 2) for val in y],
            "regression_line": [round(max(0.0, float(val)), 2) for val in y_pred],
            "projected_dates": projected_dates,
            "projected_values": projected_values,
        }
    except Exception as exc:
        return {
            "r2_score": 0.0,
            "formula": "y = mx + c",
            "trend": str(exc),
            "month_forecast_kwh": 0.0,
            "predicted_bill": 0.0,
            "history_dates": dates,
            "history_values": [round(float(val), 2) for val in y],
            "regression_line": [],
            "projected_dates": [],
            "projected_values": [],
        }


def build_dashboard(user_id):
    today = date.today()
    tariff = get_tariff_settings(user_id)
    slabs = tariff.get("slabs", DEFAULT_TARIFF_SLABS)
    fixed_charge = tariff.get("fixed_charge", 50.0)
    tax_rate = tariff.get("tax_rate", 5.0)

    all_readings = get_readings(user_id, limit=500)
    latest_reading = get_latest_reading(user_id)
    suggested_prev = float(latest_reading["current_reading"]) if latest_reading and latest_reading["current_reading"] is not None else 0.0

    # Today's reading
    today_row = get_reading_by_date(user_id, today.isoformat())
    if today_row:
        today_kwh = round(float(today_row["kwh"] or 0), 2)
        today_cost = round(float(today_row["cost"] or 0), 2)
    elif latest_reading and latest_reading["reading_date"] == today.isoformat():
        today_kwh = round(float(latest_reading["kwh"] or 0), 2)
        today_cost = round(float(latest_reading["cost"] or 0), 2)
    else:
        today_kwh = 0.0
        today_cost = 0.0

    # Current month's readings
    month_start = today.replace(day=1).isoformat()
    month_rows = [r for r in all_readings if r["reading_date"] >= month_start and r["reading_date"] <= today.isoformat()]
    month_kwh = sum(float(r["kwh"] or 0) for r in month_rows)
    current_bill_breakdown = compute_bill_breakdown(month_kwh, slabs, fixed_charge, tax_rate)
    current_month_bill = current_bill_breakdown["total_bill"]

    # Daily average this month
    days_elapsed = max(today.day, 1)
    daily_average_kwh = round(month_kwh / days_elapsed, 2) if month_rows else 0.0

    # Peak day
    peak_reading = max(all_readings, key=lambda r: float(r["kwh"] or 0)) if all_readings else None
    peak_day = {
        "date": peak_reading["reading_date"],
        "kwh": round(float(peak_reading["kwh"] or 0), 2),
    } if peak_reading and float(peak_reading["kwh"] or 0) > 0 else None

    # Monthly comparison (group by YYYY-MM)
    by_month = {}
    for r in all_readings:
        ym = r["reading_date"][:7]
        by_month.setdefault(ym, []).append(float(r["kwh"] or 0))

    sorted_months = sorted(by_month.keys())[-6:]
    monthly_comparison = []
    prev_units = None
    for ym in sorted_months:
        tot_kwh = round(sum(by_month[ym]), 2)
        mbill = compute_bill_breakdown(tot_kwh, slabs, fixed_charge, tax_rate)["total_bill"]
        try:
            mdate = datetime.strptime(ym, "%Y-%m")
            mname = mdate.strftime("%b %Y")
        except Exception:
            mname = ym

        if prev_units is not None and prev_units > 0:
            pct_change = round(((tot_kwh - prev_units) / prev_units) * 100, 1)
        else:
            pct_change = 0.0
        prev_units = tot_kwh

        monthly_comparison.append({
            "month_key": ym,
            "month_name": mname,
            "total_kwh": tot_kwh,
            "bill": mbill,
            "pct_change": pct_change,
        })

    forecasting_data = compute_ml_forecast(all_readings, tariff)

    # 7-day chart data
    day_7_start = today - timedelta(days=6)
    last_7 = [r for r in all_readings if r["reading_date"] >= day_7_start.isoformat() and r["reading_date"] <= today.isoformat()]
    by_date = {r["reading_date"]: r for r in last_7}
    chart = []
    for offset in range(6, -1, -1):
        d = today - timedelta(days=offset)
        r = by_date.get(d.isoformat())
        chart.append({
            "date": d.isoformat(),
            "day": d.strftime("%a"),
            "kwh": round(float(r["kwh"] or 0), 2) if r else 0,
            "cost": round(float(r["cost"] or 0), 2) if r else 0,
        })

    last_30_start = today - timedelta(days=29)
    last_30 = [r for r in all_readings if r["reading_date"] >= last_30_start.isoformat() and r["reading_date"] <= today.isoformat()]
    values_7 = [float(r["kwh"] or 0) for r in last_7]
    values_30 = [float(r["kwh"] or 0) for r in last_30]
    total_7 = sum(values_7)
    total_30 = sum(values_30)
    avg_7 = average(values_7)
    avg_30 = average(values_30)

    analytics_data = {
        "today_kwh": today_kwh,
        "today_cost": today_cost,
        "current_month_kwh": round(month_kwh, 2),
        "current_month_bill": current_month_bill,
        "daily_average_kwh": daily_average_kwh,
        "peak_day": peak_day,
        "current_bill_breakdown": current_bill_breakdown,
        "monthly_comparison": monthly_comparison,
    }

    return {
        "success": True,
        "today_date": today.isoformat(),
        "suggested_prev_reading": suggested_prev,
        "user": user_dict(get_user_by_id(user_id)),
        "tariff": tariff,
        "analytics": analytics_data,
        "forecasting": forecasting_data,
        # Backward compatibility fields:
        "today": {
            "date": today.isoformat(),
            "reading": row_dict(today_row),
            "kwh": today_kwh,
            "cost": today_cost,
        },
        "last_7_days": {
            "total_kwh": round(total_7, 3),
            "total_cost": round(total_7 * RATE_PER_KWH, 2),
            "average_daily_kwh": round(avg_7, 3),
            "average_daily_cost": round(avg_7 * RATE_PER_KWH, 2),
        },
        "last_30_days": {
            "total_kwh": round(total_30, 3),
            "total_cost": round(total_30 * RATE_PER_KWH, 2),
            "average_daily_kwh": round(avg_30, 3),
            "average_daily_cost": round(avg_30 * RATE_PER_KWH, 2),
        },
        "comparison": {
            "previous_30_day_average_kwh": round(avg_30, 3),
            "change_percent": 0.0,
            "trend": forecasting_data["trend"],
        },
        "prediction": {
            "tomorrow_kwh": round((avg_7 * 0.6) + (avg_30 * 0.4), 3),
            "tomorrow_cost": round(((avg_7 * 0.6) + (avg_30 * 0.4)) * RATE_PER_KWH, 2),
            "monthly_units": forecasting_data["month_forecast_kwh"],
            "monthly_bill": forecasting_data["predicted_bill"],
            "method": "Scikit-Learn Linear Regression model",
        },
        "current_month": {
            "days_in_month": calendar.monthrange(today.year, today.month)[1],
            "days_elapsed": days_elapsed,
            "days_remaining": max(0, calendar.monthrange(today.year, today.month)[1] - days_elapsed),
            "actual_kwh": round(month_kwh, 3),
            "actual_cost": current_month_bill,
            "projected_kwh": forecasting_data["month_forecast_kwh"],
            "projected_cost": forecasting_data["predicted_bill"],
        },
        "chart": chart,
        "recent_history": [row_dict(r) for r in all_readings[:10]],
    }


@app.get("/api/dashboard")
@login_required
def dashboard_api():
    return jsonify(build_dashboard(session["user_id"]))


@app.post("/api/demo-data")
@login_required
def load_demo_data():
    user_id = session["user_id"]
    today = date.today()
    import random

    # Seed 60 days of consistent historical meter readings
    curr_cumulative = 12450.0
    random.seed(42)

    for i in range(59, -1, -1):
        r_date = (today - timedelta(days=i)).isoformat()
        daily_kwh = round(random.uniform(7.5, 14.2), 2)
        prev_cumulative = curr_cumulative
        curr_cumulative = round(prev_cumulative + daily_kwh, 2)
        daily_cost = round(daily_kwh * 2.25, 2)

        save_or_update_reading(
            user_id=user_id,
            reading_date=r_date,
            appliance="Main Household Meter",
            previous_reading=prev_cumulative,
            current_reading=curr_cumulative,
            kwh=daily_kwh,
            cost=daily_cost,
        )

    return jsonify({
        "success": True,
        "message": "60-Day demonstration dataset generated successfully!",
    })


# ---------------- PDF REPORT ----------------

@app.get("/api/report")
@login_required
def report():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
        from reportlab.lib import colors
    except ImportError:
        return jsonify({
            "success": False,
            "message": "ReportLab is not installed. Run: pip install reportlab"
        }), 500

    dashboard = build_dashboard(session["user_id"])
    user = dashboard["user"]
    today = dashboard["today"]

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(
        "Energy Consumption & Prediction Report",
        styles["Title"],
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"Customer: {user['name']} ({user['email']})",
        styles["Normal"],
    ))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 12))

    summary = [
        ["Metric", "Value"],
        ["Tariff", f"₹{RATE_PER_KWH:.2f} / kWh"],
        ["Today's usage", f"{today['kwh']:.2f} kWh"],
        ["Today's cost", f"₹{today['cost']:.2f}"],
        [
            "Last 7 days",
            f"{dashboard['last_7_days']['total_kwh']:.2f} kWh",
        ],
        [
            "Last 30 days",
            f"{dashboard['last_30_days']['total_kwh']:.2f} kWh",
        ],
        [
            "Projected monthly usage",
            f"{dashboard['prediction']['monthly_units']:.2f} kWh",
        ],
        [
            "Projected monthly bill",
            f"₹{dashboard['prediction']['monthly_bill']:.2f}",
        ],
        [
            "Usage trend",
            dashboard["comparison"]["trend"].title(),
        ],
    ]

    table = Table(summary, colWidths=[80 * mm, 80 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#23483B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 14))

    story.append(Paragraph(
        "Recent daily readings",
        styles["Heading2"],
    ))

    history = [["Date", "Previous", "Current", "kWh", "Cost"]]
    for item in dashboard["recent_history"]:
        history.append([
            item["date"],
            "-" if item["previous_reading"] is None
            else f"{item['previous_reading']:.2f}",
            "-" if item["current_reading"] is None
            else f"{item['current_reading']:.2f}",
            f"{item['kwh']:.2f}",
            f"₹{item['cost']:.2f}",
        ])

    if len(history) == 1:
        history.append(["No readings", "-", "-", "-", "-"])

    history_table = Table(
        history,
        colWidths=[35 * mm, 30 * mm, 30 * mm, 25 * mm, 30 * mm],
    )
    history_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#23483B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(history_table)

    document.build(story)
    buffer.seek(0)

    filename = f"energy_report_{date.today().isoformat()}.pdf"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


# Initialize the database when the application starts.
init_db()


if __name__ == "__main__":
    print("=" * 60)
    print("Energy Consumption and Prediction Analysis System")
    print("Server: http://127.0.0.1:5000")
    print("Network: http://<YOUR-PC-IP>:5000")
    print("=" * 60)

    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )
