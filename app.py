import os
from datetime import date
from functools import wraps

from cs50 import SQL
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "change-this-to-a-long-random-secret-in-production",
)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

Session(app)

db = SQL("sqlite:///fitness.db")


def error(message, code=400):
    """
    Stores an error message in Flask's session, then returns the user
    to the page they came from. The message is displayed in a modal
    created by layout.html.
    """
    flash(message, "error")

    if request.referrer:
        return redirect(request.referrer)

    if session.get("user_id"):
        return redirect(url_for("index"))

    return redirect(url_for("login"))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")

        return f(*args, **kwargs)

    return decorated_function


def get_selected_date(date_string):
    """
    Gets a date sent from an HTML date input.

    HTML date inputs use YYYY-MM-DD.
    If no date is supplied, or an invalid date is supplied,
    today is returned.
    """
    if not date_string:
        return date.today()

    try:
        return date.fromisoformat(date_string)
    except ValueError:
        return date.today()


def date_values(selected_date):
    """
    Returns date formats needed by the app.

    input_date: YYYY-MM-DD, used by <input type="date">
    db_date: DD/MM/YYYY, matching the existing database format
    display_date: DD/MM/YYYY, used in headings
    """
    return {
        "input_date": selected_date.strftime("%Y-%m-%d"),
        "db_date": selected_date.strftime("%d/%m/%Y"),
        "display_date": selected_date.strftime("%d/%m/%Y"),
    }


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/contact")
@login_required
def contact():
    return render_template("contact.html")


@app.route("/tips")
@login_required
def tips():
    return render_template("tips.html")


@app.route("/exerciselist", methods=["GET", "POST"])
@login_required
def exerciselist():
    if request.method == "POST":
        name = request.form.get("exercise-name")
        desc = request.form.get("exercise-desc")
        muscles = request.form.get("exercise-muscles")

        if not name or not muscles:
            return error("Name and muscles fields must be filled in.", 400)

        db.execute(
            """INSERT INTO exercises (name, description, muscles_used)
            VALUES (?, ?, ?)""",
            name,
            desc,
            muscles,
        )

        return redirect("/exerciselist")

    exercises = db.execute("SELECT * FROM exercises;")

    return render_template("exerciselist.html", exercises=exercises)


@app.route("/foodlist", methods=["GET", "POST"])
@login_required
def foodlist():
    if request.method == "POST":
        name = request.form.get("food-name")
        protein = request.form.get("food-protein")
        carbs = request.form.get("food-carbs")
        fat = request.form.get("food-fat")
        calories = request.form.get("food-calories")

        if not name or not protein or not carbs or not fat or not calories:
            return error("All form fields must be filled in.", 400)

        db.execute(
            """INSERT INTO foods
            (name, protein_per_hundred_grams, carbs_per_hundred_grams,
             fat_per_hundred_grams, calories_per_hundred_grams)
            VALUES (?, ?, ?, ?, ?)""",
            name,
            protein,
            carbs,
            fat,
            calories,
        )

        return redirect("/foodlist")

    foods = db.execute("SELECT * FROM foods;")

    return render_template("foodlist.html", foods=foods)


@app.route("/workoutlog", methods=["GET", "POST"])
@login_required
def workoutlog():
    if request.method == "POST":
        db.execute(
            """INSERT INTO workouts (date, user_id)
            VALUES (?, ?)""",
            date.today().strftime("%d/%m/%Y"),
            session["user_id"],
        )

        return redirect("/workoutlog")

    selected_date = get_selected_date(request.args.get("date"))
    dates = date_values(selected_date)

    exercises = db.execute("SELECT * FROM exercises;")

    workouts = db.execute(
        """SELECT * FROM workouts
        WHERE user_id = ? AND date = ?
        ORDER BY id DESC;""",
        session["user_id"],
        dates["db_date"],
    )

    workout_ids = [workout["id"] for workout in workouts]

    if workout_ids:
        placeholders = ",".join("?" for _ in workout_ids)

        exercise_instances = db.execute(
            f"""SELECT * FROM exercise_instances
            WHERE workout_id IN ({placeholders});""",
            *workout_ids,
        )
    else:
        exercise_instances = []

    return render_template(
        "workoutlog.html",
        workouts=workouts,
        exercise_instances=exercise_instances,
        exercises=exercises,
        selected_date=dates["input_date"],
    )


@app.route("/fooddiary", methods=["GET", "POST"])
@login_required
def fooddiary():
    if request.method == "POST":
        db.execute(
            """INSERT INTO food_logs (date, user_id)
            VALUES (?, ?)""",
            date.today().strftime("%d/%m/%Y"),
            session["user_id"],
        )

        return redirect("/fooddiary")

    selected_date = get_selected_date(request.args.get("date"))
    dates = date_values(selected_date)

    foods = db.execute("SELECT * FROM foods;")

    foodlogs = db.execute(
        """SELECT * FROM food_logs
        WHERE user_id = ? AND date = ?
        ORDER BY id DESC;""",
        session["user_id"],
        dates["db_date"],
    )

    food_log_ids = [foodlog["id"] for foodlog in foodlogs]

    if food_log_ids:
        placeholders = ",".join("?" for _ in food_log_ids)

        foodinstances = db.execute(
            f"""SELECT * FROM food_instances
            WHERE food_log_id IN ({placeholders});""",
            *food_log_ids,
        )
    else:
        foodinstances = []

    return render_template(
        "fooddiary.html",
        foodlogs=foodlogs,
        foods=foods,
        foodinstances=foodinstances,
        selected_date=dates["input_date"],
    )


@app.route("/mystats", methods=["GET", "POST"])
@login_required
def mystats():
    if request.method == "POST":
        weight = request.form.get("weight")
        steps = request.form.get("steps")
        sleep = request.form.get("sleep")

        selected_date = get_selected_date(request.form.get("date"))
        dates = date_values(selected_date)

        if not weight and not steps and not sleep:
            return error("At least one stat must be entered.", 400)

        db.execute(
            """INSERT INTO stats
            (weight_kg, steps, sleep_hours, date, user_id)
            VALUES (?, ?, ?, ?, ?)""",
            weight,
            steps,
            sleep,
            dates["db_date"],
            session["user_id"],
        )

        return redirect("/mystats?date=" + dates["input_date"])

    selected_date = get_selected_date(request.args.get("date"))
    dates = date_values(selected_date)

    stats = db.execute(
        """SELECT * FROM stats
        WHERE user_id = ? AND date = ?
        ORDER BY id DESC;""",
        session["user_id"],
        dates["db_date"],
    )

    return render_template(
        "mystats.html",
        stats=stats,
        selected_date=dates["input_date"],
        display_date=dates["display_date"],
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username or not password or not confirmation:
            return error("All fields must be filled in.", 400)

        rows = db.execute(
            "SELECT * FROM users WHERE username = ?;",
            username,
        )

        if len(rows) != 0:
            return error("That username already exists. Please choose another.", 400)

        if password != confirmation:
            return error("Passwords must match.", 403)

        db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?);",
            username,
            generate_password_hash(password),
        )

        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "POST":
        if not request.form.get("username"):
            return error("Please enter your username.", 403)

        if not request.form.get("password"):
            return error("Please enter your password.", 403)

        rows = db.execute(
            "SELECT * FROM users WHERE username = ?",
            request.form.get("username"),
        )

        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"],
            request.form.get("password"),
        ):
            return error("Invalid username and/or password.", 403)

        session["user_id"] = rows[0]["id"]

        return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()

    return redirect("/")


@app.route("/deleteworkout/<int:id>", methods=["POST"])
@login_required
def delete_workout(id):
    db.execute(
        """DELETE FROM exercise_instances
        WHERE workout_id = ?;""",
        id,
    )

    db.execute(
        """DELETE FROM workouts
        WHERE id = ?;""",
        id,
    )

    return redirect("/workoutlog")


@app.route("/addexercise/<int:workout_id>", methods=["POST"])
@login_required
def add_exercise(workout_id):
    weight = request.form.get("weight")
    sets = request.form.get("sets")
    reps = request.form.get("reps")
    name = request.form.get("exercise-name")

    if not weight or not name or not sets or not reps:
        return error("All exercise fields must be entered.", 400)

    db.execute(
        """INSERT INTO exercise_instances
        (workout_id, exercise_name, weight_kg, sets, reps)
        VALUES (?, ?, ?, ?, ?);""",
        workout_id,
        name,
        weight,
        sets,
        reps,
    )

    return redirect("/workoutlog")


@app.route("/deleteexercise/<int:id>", methods=["POST"])
@login_required
def delete_exercise(id):
    db.execute(
        """DELETE FROM exercises
        WHERE id = ?;""",
        id,
    )

    return redirect("/exerciselist")


@app.route("/deletefood/<int:id>", methods=["POST"])
@login_required
def delete_food(id):
    db.execute(
        """DELETE FROM foods
        WHERE id = ?;""",
        id,
    )

    return redirect("/foodlist")


@app.route("/filteredexerciselist", methods=["GET"])
@login_required
def filter_exercise_list():
    musclefilter = request.args.get("musclefilter")

    filtered_exercises = db.execute(
        """SELECT * FROM exercises
        WHERE muscles_used LIKE ?;""",
        "%" + musclefilter + "%",
    )

    return render_template(
        "exerciselist.html",
        exercises=filtered_exercises,
    )


@app.route("/addfood/<int:foodlog_id>", methods=["POST"])
@login_required
def add_food(foodlog_id):
    name = request.form.get("food-name")
    amount = request.form.get("amount")

    if not name or not amount:
        return error("All food fields must be entered.", 400)

    try:
        amount = int(amount)
    except ValueError:
        return error("Amount must be a whole number.", 400)

    foodinfo = db.execute(
        """SELECT * FROM foods
        WHERE name = ?;""",
        name,
    )

    if not foodinfo:
        return error("That food could not be found.", 404)

    protein = int(foodinfo[0]["protein_per_hundred_grams"] * (amount / 100))
    carbs = int(foodinfo[0]["carbs_per_hundred_grams"] * (amount / 100))
    fat = int(foodinfo[0]["fat_per_hundred_grams"] * (amount / 100))
    calories = int(foodinfo[0]["calories_per_hundred_grams"] * (amount / 100))

    db.execute(
        """INSERT INTO food_instances
        (food_log_id, food_name, amount_grams, protein_grams,
         carbs_grams, fat_grams, calories)
        VALUES (?, ?, ?, ?, ?, ?, ?);""",
        foodlog_id,
        name,
        amount,
        protein,
        carbs,
        fat,
        calories,
    )

    return redirect("/fooddiary")


@app.route("/deletefoodlog/<int:id>", methods=["POST"])
@login_required
def delete_foodlog(id):
    db.execute(
        """DELETE FROM food_instances
        WHERE food_log_id = ?;""",
        id,
    )

    db.execute(
        """DELETE FROM food_logs
        WHERE id = ?;""",
        id,
    )

    return redirect("/fooddiary")


@app.route("/deletestat/<int:id>", methods=["POST"])
@login_required
def delete_stat(id):
    selected_date = get_selected_date(request.form.get("date"))

    db.execute(
        """DELETE FROM stats
        WHERE id = ?;""",
        id,
    )

    return redirect(
        "/mystats?date=" + selected_date.strftime("%Y-%m-%d")
    )


@app.route("/deleteexerciseinstance/<int:id>", methods=["POST"])
@login_required
def delete_exercise_instance(id):
    db.execute(
        """DELETE FROM exercise_instances
        WHERE id = ?;""",
        id,
    )

    return redirect("/workoutlog")


@app.route("/deletefoodinstance/<int:id>", methods=["POST"])
@login_required
def delete_food_instance(id):
    db.execute(
        """DELETE FROM food_instances
        WHERE id = ?;""",
        id,
    )

    return redirect("/fooddiary")