import calendar
import math
import os
from datetime import date, datetime, timedelta
from functools import wraps
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import (
    Flask,
    jsonify,
    redirect,
    request,
    send_file,
    send_from_directory,
    session
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)

from database import (
    delete_reading,
    get_db_connection,
    get_latest_reading_before,
    get_reading_by_date,
    get_reading_by_id,
    get_readings,
    get_user_by_email,
    get_user_by_google_sub,
    get_user_by_id,
    init_db,
    link_google_account,
    save_or_update_reading,
    create_user
)


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_DIR = BASE_DIR / "frontend"

DATABASE_DIR = BASE_DIR / "database"

DATABASE_PATH = DATABASE_DIR / "energy.db"

DATABASE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "development-key-change-this-before-deployment"
)


# ============================================================
# GOOGLE LOGIN
# ============================================================

GOOGLE_CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    "363162487877-57o9frbktb36nasdu56kikejkkvlsjk8.apps.googleusercontent.com"
)


# ============================================================
# ELECTRICITY TARIFF
# ============================================================

# This is a project-configurable rate.
#
# You can change it later without modifying the calculation
# logic by setting:
#
# TARIFF_RATE_PER_KWH
#
# Example:
#
# $env:TARIFF_RATE_PER_KWH="6"
#
# For now:
# 1 kWh = 1 unit
# 1 unit = Rs. 6.00
#

RATE_PER_KWH = float(
    os.environ.get(
        "TARIFF_RATE_PER_KWH",
        "6.0"
    )
)


# ============================================================
# INDIA TIMEZONE
# ============================================================

IST = ZoneInfo(
    "Asia/Kolkata"
)


# ============================================================
# TIME FUNCTIONS
# ============================================================

def now_ist():

    return datetime.now(
        IST
    )


def today_ist():

    return now_ist().date()


def iso_now():

    return now_ist().isoformat(
        timespec="seconds"
    )


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_email(value):

    return str(
        value or ""
    ).strip().lower()


def safe_float(
    value,
    field_name
):

    try:

        number = float(value)

    except (
        TypeError,
        ValueError
    ):

        raise ValueError(
            f"{field_name} must be a number."
        )

    if not math.isfinite(number):

        raise ValueError(
            f"{field_name} must be a valid number."
        )

    return number


def calculate_cost(kwh):

    return round(
        max(0, kwh) * RATE_PER_KWH,
        2
    )


def row_to_dict(row):

    return {
        "id": row["id"],

        "date": row["reading_date"],

        "reading_date": row["reading_date"],

        "appliance": row["appliance"],

        "previous_reading": (
            row["previous_reading"]
            if row["previous_reading"] is not None
            else None
        ),

        "current_reading": (
            row["current_reading"]
            if row["current_reading"] is not None
            else None
        ),

        "kwh": round(
            float(row["kwh"] or 0),
            2
        ),

        "units": round(
            float(row["kwh"] or 0),
            2
        ),

        "cost": round(
            float(row["cost"] or 0),
            2
        ),

        "created_at": row["created_at"]
    }


def sum_kwh(rows):

    return round(
        sum(
            float(row["kwh"] or 0)
            for row in rows
        ),
        2
    )


def average_kwh(rows):

    if not rows:

        return 0.0

    return round(
        sum_kwh(rows) / len(rows),
        2
    )


def percentage_change(
    current,
    previous
):

    if previous == 0:

        if current == 0:
            return 0.0

        return 100.0

    return round(
        (
            (current - previous)
            / previous
        ) * 100,
        2
    )


# ============================================================
# LOGIN PROTECTION
# ============================================================

def login_required(function):

    @wraps(function)
    def wrapper(
        *args,
        **kwargs
    ):

        user_id = session.get(
            "user_id"
        )

        if not user_id:

            if request.path.startswith(
                "/api/"
            ):

                return jsonify({
                    "error":
                    "Authentication required."
                }), 401

            return redirect(
                "/login"
            )

        user = get_user_by_id(
            user_id
        )

        if not user:

            session.clear()

            if request.path.startswith(
                "/api/"
            ):

                return jsonify({
                    "error":
                    "User session is no longer valid."
                }), 401

            return redirect(
                "/login"
            )

        return function(
            *args,
            **kwargs
        )

    return wrapper


# ============================================================
# FRONTEND ROUTES
# ============================================================

@app.route("/")
def home():

    if session.get("user_id"):

        return redirect(
            "/dashboard"
        )

    return redirect(
        "/login"
    )


@app.route("/login")
def login_page():

    if session.get("user_id"):

        return redirect(
            "/dashboard"
        )

    return send_from_directory(
        FRONTEND_DIR,
        "login.html"
    )


@app.route("/dashboard")
@login_required
def dashboard_page():

    return send_from_directory(
        FRONTEND_DIR,
        "index.html"
    )


@app.route(
    "/frontend/<path:filename>"
)
def frontend_files(filename):

    return send_from_directory(
        FRONTEND_DIR,
        filename
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    try:

        with get_db_connection() as connection:

            connection.execute(
                "SELECT 1"
            ).fetchone()

        database_status = "connected"

    except Exception:

        database_status = "error"

    return jsonify({

        "status": "ok",

        "service":
        "Energy Consumption and Prediction Analysis System",

        "time":
        iso_now(),

        "database":
        database_status,

        "rate_per_kwh":
        RATE_PER_KWH
    })


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/api/auth/register",
    methods=["POST"]
)
def register():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        name = str(
            data.get("name", "")
        ).strip()

        email = clean_email(
            data.get("email")
        )

        password = str(
            data.get("password", "")
        )


        if len(name) < 2:

            return jsonify({
                "error":
                "Please enter your name."
            }), 400


        if (
            "@" not in email
            or "." not in email.split("@")[-1]
        ):

            return jsonify({
                "error":
                "Please enter a valid email address."
            }), 400


        if len(password) < 6:

            return jsonify({
                "error":
                "Password must contain at least 6 characters."
            }), 400


        if get_user_by_email(email):

            return jsonify({
                "error":
                "An account with this email already exists."
            }), 409


        password_hash = generate_password_hash(
            password
        )

        user_id = create_user(
            name=name,
            email=email,
            password_hash=password_hash
        )


        session.clear()

        session["user_id"] = user_id


        return jsonify({

            "message":
            "Account created successfully.",

            "user": {

                "id":
                user_id,

                "name":
                name,

                "email":
                email
            }

        }), 201


    except Exception:

        app.logger.exception(
            "Registration failed"
        )

        return jsonify({
            "error":
            "Could not create the account."
        }), 500


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/api/auth/login",
    methods=["POST"]
)
def login():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        email = clean_email(
            data.get("email")
        )

        password = str(
            data.get("password", "")
        )


        user = get_user_by_email(
            email
        )


        if (
            not user
            or not user["password_hash"]
        ):

            return jsonify({
                "error":
                "Invalid email or password."
            }), 401


        if not check_password_hash(
            user["password_hash"],
            password
        ):

            return jsonify({
                "error":
                "Invalid email or password."
            }), 401


        session.clear()

        session["user_id"] = user["id"]


        return jsonify({

            "message":
            "Login successful.",

            "user": {

                "id":
                user["id"],

                "name":
                user["name"],

                "email":
                user["email"]
            }

        })


    except Exception:

        app.logger.exception(
            "Login failed"
        )

        return jsonify({
            "error":
            "Could not complete login."
        }), 500


# ============================================================
# GOOGLE LOGIN
# ============================================================

@app.route(
    "/api/auth/google",
    methods=["POST"]
)
def google_login():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        credential = data.get(
            "credential"
        )


        if not credential:

            return jsonify({
                "error":
                "Google credential is missing."
            }), 400


        if not GOOGLE_CLIENT_ID:

            return jsonify({
                "error":
                "Google sign-in is not configured."
            }), 500


        from google.oauth2 import id_token

        from google.auth.transport import requests as google_requests


        info = id_token.verify_oauth2_token(

            credential,

            google_requests.Request(),

            GOOGLE_CLIENT_ID
        )


        if info.get("iss") not in (
            "accounts.google.com",
            "https://accounts.google.com"
        ):

            return jsonify({
                "error":
                "Invalid Google token issuer."
            }), 401


        if not info.get(
            "email_verified"
        ):

            return jsonify({
                "error":
                "Google email is not verified."
            }), 401


        email = clean_email(
            info.get("email")
        )

        google_sub = info.get(
            "sub"
        )

        name = str(
            info.get("name")
            or email.split("@")[0]
        ).strip()


        if (
            not email
            or not google_sub
        ):

            return jsonify({
                "error":
                "Google did not provide the required account details."
            }), 401


        # ----------------------------------------------------
        # Existing Google user
        # ----------------------------------------------------

        user = get_user_by_google_sub(
            google_sub
        )


        if user:

            user_id = user["id"]

            name = user["name"]


        else:

            # ------------------------------------------------
            # Existing email account
            # ------------------------------------------------

            existing = get_user_by_email(
                email
            )


            if existing:

                existing_google_sub = (
                    existing["google_sub"]
                )


                if existing_google_sub not in (
                    None,
                    google_sub
                ):

                    return jsonify({
                        "error":
                        "This email is linked to another Google account."
                    }), 409


                link_google_account(
                    existing["id"],
                    google_sub
                )


                user_id = existing["id"]

                name = existing["name"]


            # -----------------------------------------------
            # New Google user
            # -----------------------------------------------

            else:

                user_id = create_user(

                    name=name,

                    email=email,

                    password_hash=None,

                    google_sub=google_sub
                )


        session.clear()

        session["user_id"] = user_id


        return jsonify({

            "message":
            "Google sign-in successful.",

            "user": {

                "id":
                user_id,

                "name":
                name,

                "email":
                email
            }

        })


    except ValueError:

        return jsonify({
            "error":
            "Google sign-in token is invalid or expired."
        }), 401


    except Exception:

        app.logger.exception(
            "Google sign-in validation failed"
        )

        return jsonify({
            "error":
            "Google sign-in could not be verified."
        }), 401


# ============================================================
# LOGOUT
# ============================================================

@app.route(
    "/api/auth/logout",
    methods=["POST"]
)
def logout():

    session.clear()

    return jsonify({
        "message":
        "Logged out successfully."
    })


# ============================================================
# CURRENT USER
# ============================================================

@app.route(
    "/api/me",
    methods=["GET"]
)
@login_required
def current_user():

    user = get_user_by_id(
        session["user_id"]
    )

    return jsonify({

        "user": {

            "id":
            user["id"],

            "name":
            user["name"],

            "email":
            user["email"]
        }

    })


# ============================================================
# ADD / UPDATE DAILY METER READING
# ============================================================

@app.route(
    "/api/readings",
    methods=["POST"]
)
@login_required
def add_reading():

    try:

        data = request.get_json(
            silent=True
        ) or {}


        user_id = session[
            "user_id"
        ]


        # ----------------------------------------------------
        # DATE
        # ----------------------------------------------------

        reading_date_text = str(

            data.get("date")
            or data.get("reading_date")
            or today_ist().isoformat()

        ).strip()


        try:

            reading_date = date.fromisoformat(
                reading_date_text
            )

        except ValueError:

            return jsonify({
                "error":
                "Date must use YYYY-MM-DD format."
            }), 400


        if reading_date > today_ist():

            return jsonify({
                "error":
                "You cannot enter a future meter reading."
            }), 400


        # ----------------------------------------------------
        # METER READINGS
        # ----------------------------------------------------

        previous_reading = safe_float(

            data.get(
                "previous_reading"
            ),

            "Previous meter reading"
        )


        current_reading = safe_float(

            data.get(
                "current_reading"
            ),

            "Current meter reading"
        )


        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if (
            previous_reading < 0
            or current_reading < 0
        ):

            return jsonify({
                "error":
                "Meter readings cannot be negative."
            }), 400


        if current_reading < previous_reading:

            return jsonify({
                "error":
                "Current meter reading cannot be less than previous meter reading."
            }), 400


        # ----------------------------------------------------
        # CHECK EXISTING DATE
        # ----------------------------------------------------

        existing = get_reading_by_date(

            user_id,

            reading_date_text
        )


        # ----------------------------------------------------
        # FIND PREVIOUS RECORDED DAY
        # ----------------------------------------------------

        earlier = get_latest_reading_before(

            user_id,

            reading_date_text
        )


        # ----------------------------------------------------
        # KEEP METER READINGS CONTINUOUS
        # ----------------------------------------------------

        if not existing and earlier:

            expected_previous = float(

                earlier["current_reading"]
                or 0
            )


            if not math.isclose(

                previous_reading,

                expected_previous,

                rel_tol=0,

                abs_tol=0.01

            ):

                return jsonify({

                    "error": (

                        "Previous reading must be "
                        f"{expected_previous:.2f}, "

                        "because it must match "
                        "the latest recorded "
                        "meter reading."
                    )

                }), 400


        # ----------------------------------------------------
        # CORE CALCULATION
        # ----------------------------------------------------

        kwh = round(

            current_reading
            - previous_reading,

            2
        )


        # ----------------------------------------------------
        # DAILY COST
        # ----------------------------------------------------

        cost = calculate_cost(
            kwh
        )


        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        reading_id, created = (
            save_or_update_reading(

                user_id=user_id,

                reading_date=
                reading_date_text,

                previous_reading=
                previous_reading,

                current_reading=
                current_reading,

                kwh=kwh,

                cost=cost,

                created_at=iso_now()
            )
        )


        saved = get_reading_by_id(

            user_id,

            reading_id
        )


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return jsonify({

            "message":
            "Daily meter reading saved successfully.",

            "created":
            created,

            "reading":
            row_to_dict(saved),

            "calculation": {

                "previous_reading":
                previous_reading,

                "current_reading":
                current_reading,

                "consumption_kwh":
                kwh,

                "units":
                kwh,

                "rate_per_kwh":
                RATE_PER_KWH,

                "estimated_cost":
                cost
            }

        }), 201 if created else 200


    except ValueError as exc:

        return jsonify({
            "error":
            str(exc)
        }), 400


    except Exception:

        app.logger.exception(
            "Saving meter reading failed"
        )

        return jsonify({
            "error":
            "Could not save the meter reading."
        }), 500


# ============================================================
# GET READING HISTORY
# ============================================================

@app.route(
    "/api/readings",
    methods=["GET"]
)
@login_required
def list_readings():

    try:

        user_id = session[
            "user_id"
        ]


        limit = request.args.get(
            "limit",
            default=30,
            type=int
        )


        limit = max(
            1,
            min(limit, 3650)
        )


        rows = get_readings(
            user_id
        )


        rows = rows[-limit:]


        return jsonify({

            "readings": [
                row_to_dict(row)
                for row in rows
            ],

            "count":
            len(rows),

            "rate_per_kwh":
            RATE_PER_KWH

        })


    except Exception:

        app.logger.exception(
            "Reading history failed"
        )

        return jsonify({
            "error":
            "Could not load reading history."
        }), 500


# ============================================================
# DELETE READING
# ============================================================

@app.route(
    "/api/readings/<int:reading_id>",
    methods=["DELETE"]
)
@login_required
def remove_reading(
    reading_id
):

    try:

        deleted = delete_reading(

            session["user_id"],

            reading_id
        )


        if not deleted:

            return jsonify({
                "error":
                "Reading not found."
            }), 404


        return jsonify({
            "message":
            "Reading deleted successfully."
        })


    except Exception:

        app.logger.exception(
            "Deleting reading failed"
        )

        return jsonify({
            "error":
            "Could not delete the reading."
        }), 500


# ============================================================
# DASHBOARD CALCULATION
# ============================================================

def build_dashboard(
    user_id
):

    today = today_ist()

    today_text = today.isoformat()


    # --------------------------------------------------------
    # DATE RANGES
    # --------------------------------------------------------

    start_7 = (
        today
        - timedelta(days=6)
    )

    start_30 = (
        today
        - timedelta(days=29)
    )

    previous_30_start = (
        today
        - timedelta(days=59)
    )

    previous_30_end = (
        today
        - timedelta(days=30)
    )


    # --------------------------------------------------------
    # LAST 60 DAYS
    # --------------------------------------------------------

    rows_60 = get_readings(

        user_id,

        previous_30_start.isoformat(),

        today_text
    )


    # --------------------------------------------------------
    # LAST 30 DAYS
    # --------------------------------------------------------

    rows_30 = [

        row

        for row in rows_60

        if row["reading_date"]
        >= start_30.isoformat()

    ]


    # --------------------------------------------------------
    # LAST 7 DAYS
    # --------------------------------------------------------

    rows_7 = [

        row

        for row in rows_30

        if row["reading_date"]
        >= start_7.isoformat()

    ]


    # --------------------------------------------------------
    # PREVIOUS 30 DAYS
    # --------------------------------------------------------

    previous_30 = [

        row

        for row in rows_60

        if (
            previous_30_start.isoformat()
            <= row["reading_date"]
            <= previous_30_end.isoformat()
        )

    ]


    # --------------------------------------------------------
    # TODAY
    # --------------------------------------------------------

    today_rows = [

        row

        for row in rows_30

        if row["reading_date"]
        == today_text

    ]


    today_kwh = sum_kwh(
        today_rows
    )


    today_cost = round(

        sum(
            float(row["cost"] or 0)
            for row in today_rows
        ),

        2
    )


    # --------------------------------------------------------
    # 7 DAY
    # --------------------------------------------------------

    usage_7 = sum_kwh(
        rows_7
    )

    average_7 = average_kwh(
        rows_7
    )


    # --------------------------------------------------------
    # 30 DAY
    # --------------------------------------------------------

    usage_30 = sum_kwh(
        rows_30
    )

    average_30 = average_kwh(
        rows_30
    )


    # --------------------------------------------------------
    # PREVIOUS 30 DAY
    # --------------------------------------------------------

    usage_previous_30 = sum_kwh(
        previous_30
    )

    previous_average_30 = average_kwh(
        previous_30
    )


    # ========================================================
    # TOMORROW PREDICTION
    # ========================================================

    if rows_7 and rows_30:

        tomorrow_kwh = round(

            (
                average_7 * 0.60
            )
            +
            (
                average_30 * 0.40
            ),

            2
        )


    elif rows_7:

        tomorrow_kwh = average_7


    elif rows_30:

        tomorrow_kwh = average_30


    else:

        tomorrow_kwh = 0.0


    tomorrow_cost = calculate_cost(
        tomorrow_kwh
    )


    # ========================================================
    # CURRENT MONTH
    # ========================================================

    month_start = today.replace(
        day=1
    )


    days_in_month = calendar.monthrange(

        today.year,

        today.month

    )[1]


    elapsed_days = today.day


    month_rows = get_readings(

        user_id,

        month_start.isoformat(),

        today_text
    )


    month_kwh = sum_kwh(
        month_rows
    )


    month_cost = round(

        sum(
            float(row["cost"] or 0)
            for row in month_rows
        ),

        2
    )


    # --------------------------------------------------------
    # MONTHLY PROJECTION
    # --------------------------------------------------------

    if month_rows:

        average_daily_kwh = round(

            month_kwh
            / elapsed_days,

            2
        )

        projected_month_kwh = round(

            average_daily_kwh
            * days_in_month,

            2
        )


    elif average_30 > 0:

        average_daily_kwh = average_30

        projected_month_kwh = round(

            average_30
            * days_in_month,

            2
        )


    else:

        average_daily_kwh = 0.0

        projected_month_kwh = 0.0


    projected_month_cost = calculate_cost(

        projected_month_kwh
    )


    # ========================================================
    # CONSUMPTION TREND
    # ========================================================

    if average_30 == 0:

        trend = "No data"


    elif average_7 > average_30 * 1.05:

        trend = "Increasing"


    elif average_7 < average_30 * 0.95:

        trend = "Decreasing"


    else:

        trend = "Stable"


    # ========================================================
    # COMPARISON
    # ========================================================

    today_vs_7 = percentage_change(

        today_kwh,

        average_7
    )


    today_vs_30 = percentage_change(

        today_kwh,

        average_30
    )


    last_30_vs_previous_30 = percentage_change(

        usage_30,

        usage_previous_30
    )


    # ========================================================
    # CHART DATA
    # ========================================================

    by_date = {

        row["reading_date"]:
        row

        for row in rows_30

    }


    chart_labels = []

    chart_kwh = []

    chart_cost = []


    for offset in range(
        29,
        -1,
        -1
    ):

        current_date = (
            today
            - timedelta(days=offset)
        )


        key = current_date.isoformat()


        row = by_date.get(
            key
        )


        chart_labels.append(

            current_date.strftime(
                "%d %b"
            )

        )


        if row:

            chart_kwh.append(

                round(
                    float(row["kwh"] or 0),
                    2
                )

            )

            chart_cost.append(

                round(
                    float(row["cost"] or 0),
                    2
                )

            )

        else:

            chart_kwh.append(
                0
            )

            chart_cost.append(
                0
            )


    # ========================================================
    # RECENT HISTORY
    # ========================================================

    recent_history = list(
        reversed(
            rows_30[-10:]
        )
    )


    # ========================================================
    # FINAL DASHBOARD OBJECT
    # ========================================================

    return {

        "generated_at":
        iso_now(),

        "rate_per_kwh":
        RATE_PER_KWH,


        # ----------------------------------------------------
        # TODAY
        # ----------------------------------------------------

        "today": {

            "date":
            today_text,

            "kwh":
            today_kwh,

            "units":
            today_kwh,

            "cost":
            today_cost,

            "reading":

                row_to_dict(
                    today_rows[-1]
                )
                if today_rows
                else None

        },


        # ----------------------------------------------------
        # 7 DAYS
        # ----------------------------------------------------

        "last_7_days": {

            "days_with_data":
            len(rows_7),

            "total_kwh":
            usage_7,

            "average_kwh_per_recorded_day":
            average_7,

            "average_kwh_per_calendar_day":
            round(
                usage_7 / 7,
                2
            )

        },


        # ----------------------------------------------------
        # 30 DAYS
        # ----------------------------------------------------

        "last_30_days": {

            "days_with_data":
            len(rows_30),

            "total_kwh":
            usage_30,

            "average_kwh_per_recorded_day":
            average_30,

            "average_kwh_per_calendar_day":
            round(
                usage_30 / 30,
                2
            )

        },


        # ----------------------------------------------------
        # PREVIOUS 30 DAYS
        # ----------------------------------------------------

        "previous_30_days": {

            "days_with_data":
            len(previous_30),

            "total_kwh":
            usage_previous_30,

            "average_kwh_per_recorded_day":
            previous_average_30

        },


        # ----------------------------------------------------
        # COMPARISON
        # ----------------------------------------------------

        "comparison": {

            "today_vs_7_day_average_percent":
            today_vs_7,

            "today_vs_30_day_average_percent":
            today_vs_30,

            "last_30_vs_previous_30_percent":
            last_30_vs_previous_30

        },


        # ----------------------------------------------------
        # PREDICTION
        # ----------------------------------------------------

        "prediction": {

            "tomorrow_date":
            (
                today
                + timedelta(days=1)
            ).isoformat(),

            "tomorrow_kwh":
            tomorrow_kwh,

            "tomorrow_units":
            tomorrow_kwh,

            "tomorrow_cost":
            tomorrow_cost,

            "method":
            "60% 7-day average + 40% 30-day average"

        },


        # ----------------------------------------------------
        # MONTHLY
        # ----------------------------------------------------

        "monthly": {

            "month":
            today.strftime("%Y-%m"),

            "days_in_month":
            days_in_month,

            "elapsed_days":
            elapsed_days,

            "recorded_days":
            len(month_rows),

            "current_kwh":
            month_kwh,

            "current_units":
            month_kwh,

            "current_bill":
            month_cost,

            "average_daily_kwh":
            average_daily_kwh,

            "projected_kwh":
            projected_month_kwh,

            "projected_units":
            projected_month_kwh,

            "projected_bill":
            projected_month_cost

        },


        # ----------------------------------------------------
        # TREND
        # ----------------------------------------------------

        "trend":
        trend,


        # ----------------------------------------------------
        # CHART
        # ----------------------------------------------------

        "chart": {

            "labels":
            chart_labels,

            "kwh":
            chart_kwh,

            "cost":
            chart_cost

        },


        # ----------------------------------------------------
        # HISTORY
        # ----------------------------------------------------

        "recent_history": [

            row_to_dict(row)

            for row in recent_history

        ]

    }


# ============================================================
# DASHBOARD API
# ============================================================

@app.route(
    "/api/dashboard",
    methods=["GET"]
)
@login_required
def dashboard_api():

    try:

        dashboard = build_dashboard(

            session["user_id"]

        )

        return jsonify(
            dashboard
        )


    except Exception:

        app.logger.exception(
            "Dashboard calculation failed"
        )

        return jsonify({
            "error":
            "Could not calculate dashboard data."
        }), 500


# ============================================================
# PDF REPORT
# ============================================================

@app.route(
    "/api/report",
    methods=["GET"]
)
@login_required
def report():

    try:

        from reportlab.lib.pagesizes import A4

        from reportlab.pdfgen import canvas


        dashboard = build_dashboard(

            session["user_id"]

        )


        user = get_user_by_id(

            session["user_id"]

        )


        buffer = BytesIO()


        pdf = canvas.Canvas(

            buffer,

            pagesize=A4

        )


        width, height = A4


        pdf.setTitle(

            "Energy Consumption Report"

        )


        x = 45

        y = height - 50


        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        pdf.setFont(
            "Helvetica-Bold",
            18
        )

        pdf.drawString(
            x,
            y,
            "Energy Consumption Report"
        )


        y -= 25


        pdf.setFont(
            "Helvetica",
            10
        )


        pdf.drawString(
            x,
            y,
            f"User: {user['name']}"
        )


        y -= 15


        pdf.drawString(
            x,
            y,
            f"Email: {user['email']}"
        )


        y -= 15


        pdf.drawString(
            x,
            y,
            f"Generated: {dashboard['generated_at']}"
        )


        # ----------------------------------------------------
        # MONTHLY
        # ----------------------------------------------------

        y -= 35


        pdf.setFont(
            "Helvetica-Bold",
            13
        )


        pdf.drawString(
            x,
            y,
            "Current Month"
        )


        y -= 22


        pdf.setFont(
            "Helvetica",
            11
        )


        monthly = dashboard[
            "monthly"
        ]


        lines = [

            f"Current recorded usage: "
            f"{monthly['current_kwh']:.2f} kWh",

            f"Current recorded cost: "
            f"Rs. {monthly['current_bill']:.2f}",

            f"Average daily usage: "
            f"{monthly['average_daily_kwh']:.2f} kWh",

            f"Projected monthly usage: "
            f"{monthly['projected_kwh']:.2f} kWh",

            f"Projected monthly bill: "
            f"Rs. {monthly['projected_bill']:.2f}",

            f"Configured rate: "
            f"Rs. {dashboard['rate_per_kwh']:.2f} / kWh"

        ]


        for line in lines:

            pdf.drawString(
                x,
                y,
                line
            )

            y -= 18


        # ----------------------------------------------------
        # TOMORROW
        # ----------------------------------------------------

        y -= 15


        pdf.setFont(
            "Helvetica-Bold",
            13
        )


        pdf.drawString(
            x,
            y,
            "Tomorrow Prediction"
        )


        y -= 22


        pdf.setFont(
            "Helvetica",
            11
        )


        prediction = dashboard[
            "prediction"
        ]


        pdf.drawString(

            x,

            y,

            f"Estimated usage: "
            f"{prediction['tomorrow_kwh']:.2f} kWh"

        )


        y -= 18


        pdf.drawString(

            x,

            y,

            f"Estimated cost: "
            f"Rs. {prediction['tomorrow_cost']:.2f}"

        )


        # ----------------------------------------------------
        # RECENT READINGS
        # ----------------------------------------------------

        y -= 35


        pdf.setFont(
            "Helvetica-Bold",
            13
        )


        pdf.drawString(

            x,

            y,

            "Recent Meter Readings"

        )


        y -= 22


        pdf.setFont(
            "Helvetica-Bold",
            9
        )


        pdf.drawString(
            x,
            y,
            "Date"
        )


        pdf.drawString(
            x + 75,
            y,
            "Previous"
        )


        pdf.drawString(
            x + 150,
            y,
            "Current"
        )


        pdf.drawString(
            x + 225,
            y,
            "kWh"
        )


        pdf.drawString(
            x + 280,
            y,
            "Cost"
        )


        y -= 16


        pdf.setFont(
            "Helvetica",
            9
        )


        for reading in dashboard[
            "recent_history"
        ]:

            if y < 60:

                pdf.showPage()

                y = height - 50

                pdf.setFont(
                    "Helvetica",
                    9
                )


            previous = (
                reading["previous_reading"]
                if reading["previous_reading"]
                is not None
                else 0
            )


            current = (
                reading["current_reading"]
                if reading["current_reading"]
                is not None
                else 0
            )


            pdf.drawString(
                x,
                y,
                reading["date"]
            )


            pdf.drawString(
                x + 75,
                y,
                f"{previous:.2f}"
            )


            pdf.drawString(
                x + 150,
                y,
                f"{current:.2f}"
            )


            pdf.drawString(
                x + 225,
                y,
                f"{reading['kwh']:.2f}"
            )


            pdf.drawString(
                x + 280,
                y,
                f"Rs. {reading['cost']:.2f}"
            )


            y -= 16


        pdf.save()


        buffer.seek(0)


        return send_file(

            buffer,

            mimetype="application/pdf",

            as_attachment=True,

            download_name=
            "energy_consumption_report.pdf"

        )


    except ImportError:

        return jsonify({

            "error":
            "Report generation requires reportlab. Install it with pip install reportlab."

        }), 500


    except Exception:

        app.logger.exception(
            "Report generation failed"
        )

        return jsonify({

            "error":
            "Could not generate the report."

        }), 500


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

init_db()


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "5000"
        )
    )


    debug = (
        os.environ.get(
            "FLASK_DEBUG",
            "1"
        ) == "1"
    )


    print()
    print("=" * 65)

    print(
        "ENERGY CONSUMPTION AND PREDICTION ANALYSIS SYSTEM"
    )

    print("=" * 65)

    print(
        f"Database: {DATABASE_PATH}"
    )

    print(
        f"Rate: Rs. {RATE_PER_KWH:.2f} per kWh"
    )

    print(
        f"Login: http://127.0.0.1:{port}/login"
    )

    print(
        f"Dashboard: http://127.0.0.1:{port}/dashboard"
    )

    print("=" * 65)
    print()


    app.run(

        host="0.0.0.0",

        port=port,

        debug=debug

    )