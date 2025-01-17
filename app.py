import os
import datetime
from flask import (
    Flask, flash, render_template, redirect, request, session, url_for)
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
if os.path.exists("env.py"):
    import env

app = Flask(__name__)

# Mongo DB Constants
app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)


# Set accessible variables
@app.context_processor
def get_db_collections():
    """Set dictories as a global variable so all templates can call it
    Used for dictionaries that are used in more then one template and
    dictonaries that aren't changed / updated offend if at all.
    User can't edit these dictionaries.
    """
    alcohol_categories = list(mongo.db.alcohol.find())
    units = list(mongo.db.units.find())
    tools = list(mongo.db.tools.find())
    glasses = list(mongo.db.glasses.find())
    return dict(
        alcohol_categories=alcohol_categories,
        units=units,
        tools=tools,
        glasses=glasses
    )


# Home
@app.route("/", defaults={"alcohol_name": None}, methods=["GET", "POST"])
@app.route("/home", defaults={"alcohol_name": None}, methods=["GET", "POST"])
@app.route("/home/<alcohol_name>", methods=["GET", "POST"])
def home(alcohol_name):
    """The plain homepage will return all the cocktails but the user
    can filter the cocktails from the main site nav. This selection
    will cause the alcohol filter to run and only cocktails that
    use that alochol will be presenteed on the page.
    """
    # Alcohol Filter
    if alcohol_name:
        alcohol = mongo.db.alcohol.find_one({"alcohol_name": alcohol_name})
        # Catch bad url, alcohol_name will accept anything as correct
        if not alcohol:
            return render_template('404.html'), 404

        # Alcohol Newly Added
        newest = list(mongo.db.cocktails.find({
            "alcohol": alcohol_name.lower()}
        ).sort(
            "date_added", -1
        ).limit(18))

        # Alcohol Top Rated
        top_rated = list(mongo.db.cocktails.find(
            {"alcohol": alcohol_name.lower()}
        ).sort(
            [("rating", -1), ("no_rating", -1)]
        ).limit(18))

        # Alcohol Most Popular
        popular = list(mongo.db.cocktails.find(
            {"alcohol": alcohol_name.lower()}
        ).sort(
            [("no_of_bookmarks", -1), ("no_rating", -1)]
        ).limit(18))

        # Alcohol Featured Cocktail
        mixology_cocktials = list(mongo.db.cocktails.find({
            "alcohol": alcohol_name.lower(),
            "author_id": "60255ef95f5d67939e673ce2"
        }).sort(
            [("no_of_bookmarks", -1), ("no_rating", -1)]
        ).limit(1))

        featured_cocktail = mixology_cocktials[0]

        # Add the arrangements into a list for template to iterate
        sort_cats = [
            {"name": "Newly Added", "cocktails": newest},
            {"name": "Top Rated", "cocktails": top_rated},
            {"name": "Most Popular", "cocktails": popular}
        ]

    # Homepage
    else:
        alcohol = None
        # Sort Cocktails into different arrangements

        # Newly Added
        newest = list(mongo.db.cocktails.find().sort(
            "date_added", -1
        ).limit(18))

        # Top Rated
        top_rated = list(mongo.db.cocktails.find().sort(
            [("rating", -1), ("no_rating", -1)]
        ).limit(18))

        # Most Popular
        popular = list(mongo.db.cocktails.find().sort(
            "no_of_bookmarks", -1
        ).limit(18))

        # Featured Cocktail
        mixology_cocktials = list(mongo.db.cocktails.find({
            "author_id": "60255ef95f5d67939e673ce2"
        }).sort(
            [("no_of_bookmarks", -1), ("no_rating", -1)]
        ).limit(1))

        featured_cocktail = mixology_cocktials[0]

        # Add the arrangements into a list for template to iterate
        sort_cats = [
            {"name": "Newly Added", "cocktails": newest},
            {"name": "Top Rated", "cocktails": top_rated},
            {"name": "Most Popular", "cocktails": popular}
        ]

    # Get user bookmarks
    user_bookmarks = get_bookmarks()

    # Bookmarking
    if request.method == "POST":
        form_type = request.form.get("form-submit")
        if form_type == "bookmark":
            submit_bookmark(user_bookmarks)

    if not alcohol_name:
        return render_template(
            "home.html",
            sort_cats=sort_cats,
            user_bookmarks=user_bookmarks,
            featured_cocktail=featured_cocktail
        )

    else:
        return render_template(
            "home.html",
            alcohol=alcohol,
            sort_cats=sort_cats,
            user_bookmarks=user_bookmarks,
            featured_cocktail=featured_cocktail
        )


# Search
@app.route("/search", defaults={"query": None}, methods=["GET", "POST"])
@app.route("/search/<query>", methods=["GET", "POST"])
def search(query):
    """ The search gets the query from the form input
    (if no form input the query will be set to " " and
    no results will be return, the user can then search
    from the results page). The search results are filter
    via alochol type and user. If a user is found the
    session user will be taken straight to the user
    profile.
    """
    # Get user bookmarks
    user_bookmarks = get_bookmarks()

    if request.method == "POST":
        # Get Query
        if query is None:
            query = request.form.get("query").lower()

        form_type = request.form.get("form-submit")

        # Bookmarking
        if form_type == "bookmark":
            submit_bookmark(user_bookmarks)
            return redirect(url_for(
                "search",
                query=query
            ))

    if not query:
        query = " "
    # Find Users
    user = mongo.db.users.find_one({"username": query})

    # if user, takes the user straight to the user profile page
    if user:
        flash("User Found")
        return redirect(url_for(
            "profile",
            profile_name=user["username"],
            profile_id=user["_id"]
        ))

    # Find all cocktails
    all_cocktails = list(mongo.db.cocktails.find(
        {"$text": {"$search": query}})
    )

    # Block blank searches
    if query == "":
        flash("Empty search input")
        return redirect(url_for("home"))

    alcohol_categories = list(mongo.db.alcohol.find())

    # Filter cocktails by alcohol
    vodka_cocktails = []
    whiskey_cocktails = []
    gin_cocktails = []
    rum_cocktails = []
    tequila_cocktails = []

    # Used if no cocktail are found to tell user no user was found
    user = []

    # If all cocktail has at least one
    if len(all_cocktails) > 0:
        for alcohol in alcohol_categories:

            # Create list name
            filt = f"{str(alcohol['alcohol_name'].lower())}_cocktails"
            cocktails = list(mongo.db.cocktails.find({
                "$text": {
                    "$search": query
                },
                "alcohol": alcohol['alcohol_name'].lower()
            }))

            if len(cocktails) > 0:
                # Set list name as variable and extend cocktail to the
                # corresponding list abover
                vars()[filt].extend(cocktails)

    # Stage info for template to iterate
    cocktail_search_cats = [
        {"name": "User", "cocktails": user},
        {"name": "All Cocktails", "cocktails": all_cocktails},
        {"name": "Vodka Cocktails", "cocktails": vodka_cocktails},
        {"name": "Whiskey Cocktails", "cocktails": whiskey_cocktails},
        {"name": "Gin Cocktails", "cocktails": gin_cocktails},
        {"name": "Rum Cocktails", "cocktails": rum_cocktails},
        {"name": "Tequila Cocktails", "cocktails": tequila_cocktails},
    ]

    return render_template(
        "search.html",
        cocktail_search_cats=cocktail_search_cats,
        query=query,
        user_bookmarks=user_bookmarks,
    )


@app.route("/view-all/<order_by>", methods=["GET", "POST"])
def view_all(order_by):
    """ View All finds all the cocktails in the database
    and then filters them into their alochol types then
    sorts them by the users selected link value
    eg. Top Rated, Most Popular, Newly Added
    """
    # Get user bookmarks
    user_bookmarks = get_bookmarks()

    # Bookmarking
    if request.method == "POST":
        form_type = request.form.get("form-submit")
        if form_type == "bookmark":
            submit_bookmark(user_bookmarks)
            return redirect(url_for(
                "view_all",
                order_by=order_by
            ))

    if order_by == "top-rated":
        order = "rating"

    elif order_by == "newly-added":
        order = "date_added"

    elif order_by == "most-popular":
        order = "no_of_bookmarks"

    else:
        return render_template('404.html'), 404

    all_cocktails = list(mongo.db.cocktails.find().sort(order, -1))

    alcohol_categories = list(mongo.db.alcohol.find())

    # Filter cocktails by alcohol
    vodka_cocktails = []
    whiskey_cocktails = []
    gin_cocktails = []
    rum_cocktails = []
    tequila_cocktails = []

    # If all cocktail has at least one
    if len(all_cocktails) > 0:
        for alcohol in alcohol_categories:

            # Create list name
            filt = f"{str(alcohol['alcohol_name'].lower())}_cocktails"
            cocktails = list(mongo.db.cocktails.find({
                "alcohol": alcohol['alcohol_name'].lower()
            }).sort(
                order, -1
            ))

            if len(cocktails) > 0:
                # Set list name as variable and extend cocktail to the
                # corresponding list abover
                vars()[filt].extend(cocktails)

    # Stage info for template to iterate
    cocktail_search_cats = [
        {"name": "All Cocktails", "cocktails": all_cocktails},
        {"name": "Vodka Cocktails", "cocktails": vodka_cocktails},
        {"name": "Whiskey Cocktails", "cocktails": whiskey_cocktails},
        {"name": "Gin Cocktails", "cocktails": gin_cocktails},
        {"name": "Rum Cocktails", "cocktails": rum_cocktails},
        {"name": "Tequila Cocktails", "cocktails": tequila_cocktails},
    ]

    return render_template(
        "view-all.html",
        order_by=order_by,
        cocktail_search_cats=cocktail_search_cats,
        user_bookmarks=user_bookmarks,
    )


# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    """Checks user's credentials agianest the datebase.
    If the username is found the function will check
    the password hash against the one is the datebase.
    If everything matches the user is logged in and
    their username and id are add as session cookies.
    They are then taken to the homepage else feedback
    is given and the user remains on the login page
    """
    if request.method == "POST":
        # Check username is in database
        user_in_db = mongo.db.users.find_one(
            {"username": request.form.get("login-username").lower()})

        if user_in_db:
            # Check password of username matches password in datebase
            if check_password_hash(
                user_in_db["password"], request.form.get("login-password")
            ):

                # If the password matches
                # Set Username into session cookie
                session["user"] = request.form.get("login-username").lower()

                # Set user Id into session ID-
                session["id"] = str(mongo.db.users.find_one(
                    {"username": request.form.get("login-username").lower()}
                ).get(
                    "_id"
                ))

                # Set form submit no to block against re submit on reload
                # Set to value a random number genarator can't produce
                session["formsubmitno"] = "nothing"

                flash("Welcome {}".format(request.form.get("login-username")))
                # Return the user to the home page logged in
                return redirect(url_for("home"))

            else:
                # If passwords don't matach
                flash("Username or Password is Incorrect")
                return redirect(url_for("login"))

        else:
            # If username isn't in datebase
            flash("Username or Password is Incorrect")
            return redirect(url_for("login"))

    return render_template("login.html")


# Resigster
@app.route("/register", methods=["GET", "POST"])
def register():
    """The user signs up for the site. The username
    is checked against the datebase to see if the
    name is already taken.
    If successful they are taken to the homepage
    and their username and id are added to as
    session cookies to be used by other functions.
    """

    if request.method == "POST":
        # Check username isnt already taken by another user
        user_in_db = mongo.db.users.find_one(
            {"username": request.form.get("reg-username").lower()})

        # Tells user if the username is taken
        if user_in_db:
            flash("Username unavailable. Please choose another.")
            return redirect(url_for("register"))

        # Default image UR
        domain = "https://drive.google.com/"
        image_id = "uc?export=view&id=1xxYCbYNJ5bQmalWEqNgZyl8zjxnV5Id9"

        # Stages the form information into the correct formate for db
        register = {
            "username": request.form.get("reg-username").lower(),
            "password": generate_password_hash(
                request.form.get("reg-password")),
            "bookmarks": [],
            "image": f"{domain}{image_id}",
            "date_added": datetime.datetime.utcnow(),
            "rated_cocktails": []
        }

        # Add staged form information to the db
        mongo.db.users.insert_one(register)

        # Add user to session cookies
        session["user"] = request.form.get("reg-username").lower()
        session["id"] = str(mongo.db.users.find_one(
            {"username": request.form.get("reg-username").lower()}
        ).get("_id"))

        # Set form submit no to block against re submit on reload
        # Set to value a random number genarator can't produce
        session["formsubmitno"] = "nothing"

        # Tells user they are successfil register
        flash("Success! Thank You for signing up to Mixology")
        return redirect(url_for("home"))

    return render_template("register.html")


# Logout
@app.route("/logout")
def logout():
    """The user is logged out by clearing their
    session cookies. The form submission number
    cookie is re added as it is used by over
    function to stop forms being resubmitted on
    reload
    """
    # Removes all session cookies
    session.clear()
    session["formsubmitno"] = "nothing"
    # Tells user they have logged out
    flash("You have successfully logged out")
    return redirect(url_for("home"))


# Profile
@app.route(
    "/profile/<profile_name>/<profile_id>",
    defaults={"edit": "false"},
    methods=["GET", "POST"])
@app.route(
    "/profile/<profile_name>/<profile_id>/<edit>",
    methods=["GET", "POST"])
def profile(profile_name, profile_id, edit):
    """Finds all of the cocktails authored by
    the user and filters them by alcohol type.
    If the user owns the profile they can update
    their profile and the changes will be made
    to the datebase.
    """
    # Get user bookmarks
    user_bookmarks = get_bookmarks()

    profile = mongo.db.users.find_one(
        {"username": profile_name}
    )

    if not profile:
        flash("Profile Doesn't Exist")
        return redirect(url_for("home"))

    # Determinds which form is being posted
    if request.method == "POST":
        form_type = request.form.get("form-submit")

        if form_type == "bookmark":
            submit_bookmark(user_bookmarks)

        elif form_type == "update-profile":
            update_return = update_profile(profile_name, profile_id)

            # Will reload the page in edit mode
            if update_return == "true":
                edit = "true"

        elif form_type == "delete-profile":
            delete_profile(profile_id)

    bookmarked_cocktails = get_bookmarked_cocktails()

    user_all_cocktails = list(mongo.db.cocktails.find(
        {"author_id": profile_id}).sort("date_added", -1)
    )

    # Filter cocktail by alcohol
    alcohol_categories = list(mongo.db.alcohol.find())

    # Filter user cocktails by alcohol
    user_vodka_cocktails = []
    user_whiskey_cocktails = []
    user_gin_cocktails = []
    user_rum_cocktails = []
    user_tequila_cocktails = []

    # If user filter cocktails
    for alcohol in alcohol_categories:
        filt = f"user_{str(alcohol['alcohol_name'].lower())}_cocktails"
        cocktails = list(mongo.db.cocktails.find({
            "alcohol": alcohol['alcohol_name'].lower(),
            "author_id": profile_id
        }).sort("date_added", -1))

        if len(cocktails) > 0:
            vars()[filt].extend(cocktails)

    # Stage info for template to iterate
    user_alcohol_cats = [
        {"name": "Cocktails", "cocktails": user_all_cocktails},
        {
            "name": "Vodka Cocktails",
            "cocktails": user_vodka_cocktails
        },
        {
            "name": "Whiskey Cocktails",
            "cocktails": user_whiskey_cocktails
        },
        {"name": "Gin Cocktails", "cocktails": user_gin_cocktails},
        {"name": "Rum Cocktails", "cocktails": user_rum_cocktails},
        {
            "name": "Tequila Cocktails",
            "cocktails": user_tequila_cocktails
        },
    ]

    # Block non profile Owners from editing via url
    if edit == "true":
        if session["id"] != profile_id:
            edit = "false"
            flash("Unauthorized to edit profile")

    # Stop error from bad /edit url
    elif edit != "true" or edit != "false":
        edit = "false"

    return render_template(
        "profile.html",
        user_all_cocktails=user_all_cocktails,
        bookmarked_cocktails=bookmarked_cocktails,
        user_alcohol_cats=user_alcohol_cats,
        profile=profile,
        user_bookmarks=user_bookmarks,
        edit=edit
    )


# Delete Profile
@app.route("/delete-profile/<user_id>")
def delete_profile(user_id):
    """Finds all of the cocktails authored by
    the user and deletes them from the datebase
    as well as the user. The user is logged out
    by the session cookies being cleared.
    """
    # Delete profile from db
    mongo.db.users.delete_one({"_id": ObjectId(user_id)})

    # Delete all cocktials in db owned by the user
    mongo.db.cocktails.delete_many({"author_id": user_id})

    # Clear session / log out
    session.clear()

    # Set form submit no or error thrown when form submitted
    # Set to value a random number genarator can't produce
    session["formsubmitno"] = "nothing"

    flash("Profile Deleted")
    return redirect(url_for("home"))


# Cocktail Recipe Page
@app.route("/cocktail/<cocktail_name>/<cocktail_id>", methods=[
    "GET", "POST"])
def cocktail(cocktail_name, cocktail_id):
    """This function find the cocktail by id
    in the datebase for the template to display it.
    This function will also determine if the cocktail
    has been bookmarked by the user.

    User can view rate and bookmark cocktails from
    this page. This function calls the function to
    handle updating the database.
    """
    # Get user bookmarks and user rated cocktails
    if session.get('user'):
        user_bookmarks = mongo.db.users.find_one(
            {"username": session["user"]}).get("bookmarks")

        user_rated_cocktails = mongo.db.users.find_one(
            {"username": session["user"]}).get("rated_cocktails")

    else:
        user_rated_cocktails = []
        user_bookmarks = []

    # Determine which form has been submitted
    if request.method == "POST":
        form_type = request.form.get("form-submit")
        if form_type == "bookmark":
            submit_bookmark(user_bookmarks)
        elif form_type == "rating":
            submit_rating(user_rated_cocktails)

    if session.get('user'):
        if cocktail_id in user_bookmarks:
            bookmark = "true"

        else:
            bookmark = "false"

    else:
        bookmark = "false"

    cocktail = mongo.db.cocktails.find_one({"_id": ObjectId(cocktail_id)})
    return render_template(
        "cocktail.html",
        cocktail=cocktail,
        bookmark=bookmark,
        user_rated_cocktails=user_rated_cocktails
    )


# Delete Cocktail
@app.route("/delete-cocktail/<cocktail_id>")
def delete_cocktail(cocktail_id):
    """When a cocktail is deleted via this function
    its ID is removed from all user lists e.g.
    Bookmarks and Rated Cocktails.
    """
    # Delete cocktail from db
    mongo.db.cocktails.delete_one({"_id": ObjectId(cocktail_id)})

    # Delete cocktail form users bookmarks
    users_booked = list(mongo.db.users.find({"bookmarks": cocktail_id}))
    users_rated = list(mongo.db.users.find({"rated_cocktails": cocktail_id}))

    # Remove Bookmarks
    for user in users_booked:
        if len(user["bookmarks"]) == 1:
            removed_bookmark = []

        else:
            removed_bookmark = user["bookmarks"].remove(cocktail_id)

        # Stage user new key values
        user_query = {"_id": ObjectId(user["_id"])}
        user_update = {"$set": {"bookmarks":  removed_bookmark}}

        # Update datebase
        mongo.db.users.update_one(user_query, user_update)

    # Remove Ratings
    for user in users_rated:
        if len(user["rated_cocktails"]) == 1:
            removed_rating = []

        else:
            removed_rating = user["rated_cocktails"].remove(cocktail_id)

        # Stage user new key values
        user_query = {"_id": ObjectId(user["_id"])}
        user_update = {"$set": {"rated_cocktails":  removed_rating}}

        # Update datebase
        mongo.db.users.update_one(user_query, user_update)

    flash("Cocktail Deleted")
    return redirect(url_for(
        "profile",
        profile_name=session["user"],
        profile_id=session["id"]
    ))


# Create / Edit Cocktail Form
@app.route("/cocktail-edit/<cocktail_name>/<cocktail_id>", methods=[
    "GET", "POST"
])
@app.route("/cocktail-create", defaults={
    "cocktail_name": None,
    "cocktail_id": None
}, methods=["GET", "POST"])
def cocktail_create(cocktail_name, cocktail_id):
    """Stages the cocktail information to be add
    or updated to the datebase depending on where
    the cocktail is being added or edited. It then
    pushes this staged information to the datebase.
    """
    if request.method == "POST":
        # Grab random number from form
        form_random_value = request.form.get("random"),

        # Block against reload re submits
        if form_random_value != session["formsubmitno"]:
            session["formsubmitno"] = form_random_value

            # Get the number of each input field
            ingred_count = int(request.form.get("no-of-ingred"))
            garnish_count = int(request.form.get("no-of-garnish"))
            tool_count = int(request.form.get("no-of-tools"))
            instr_count = int(request.form.get("no-of-instr"))

            """" Sets the formated inputs to variables
            Calling the formate function with the correct input
            and counter
            """
            ingredients = formate_inputs("ingredient", ingred_count)
            garnishes = formate_inputs("garnish", garnish_count)
            tools = formate_inputs("tool", tool_count)
            instructions = formate_inputs("instruction", instr_count)

            if not cocktail_id:
                # Stages form input ready to be pushed to the datebase
                register = {
                    "cocktail_name": request.form.get("cocktail-name").lower(),
                    "alcohol": request.form.get("alcohol"),
                    "image": request.form.get("cocktail-img-url"),
                    "date_added": datetime.datetime.utcnow(),
                    "rating": 0,
                    "no_rating": 0,
                    "no_of_bookmarks": 0,
                    "author": session["user"],
                    "author_id": session["id"],
                    "ingredients": ingredients,
                    "garnish": garnishes,
                    "tools": tools,
                    "glass": request.form.get("glass").lower(),
                    "instructions": instructions,
                    "rating_sum": 0,
                }

                # Pushes the staged info to the datebase
                mongo.db.cocktails.insert_one(register)

                # Gives the user feedback on a sucessful submission
                flash("Coctail Added")

                return redirect(url_for(
                    "profile", profile_name=session["user"],
                    profile_id=session["id"]
                ))

            else:
                # Stages form input ready to be pushed to the datebase
                cocktail_query = {"_id": ObjectId(cocktail_id)}
                edit = {
                    "$set": {
                        "cocktail_name": request.form.get(
                            "cocktail-name"
                        ).lower(),
                        "alcohol": request.form.get("alcohol").lower(),
                        "image": request.form.get("cocktail-img-url"),
                        "ingredients": ingredients,
                        "garnish": garnishes,
                        "tools": tools,
                        "glass": request.form.get("glass").lower(),
                        "instructions": instructions
                    }
                }

                # Pushes the staged info to the datebase
                mongo.db.cocktails.update_one(cocktail_query, edit)

                # Gives the user feedback on a sucessful submission
                flash("Coctail Updated")

                cocktail = mongo.db.cocktails.find_one({
                    "_id": ObjectId(cocktail_id)
                })
                return render_template("cocktail.html", cocktail=cocktail)

        else:
            if cocktail_id:
                flash("Changes Saved")
                cocktail = mongo.db.cocktails.find_one({
                    "_id": ObjectId(cocktail_id)
                })
                return render_template("cocktail.html", cocktail=cocktail)
            else:
                flash("Cocktail Already Added")
                return redirect(url_for(
                    "profile",
                    profile_name=session["user"],
                    profile_id=session["id"]
                ))

    # Non logged in user feedback
    elif not session.get("user"):
        flash("You must be logged in to create a cocktail")
        return redirect(url_for("login"))

    elif cocktail_id:
        cocktail = mongo.db.cocktails.find_one({"_id": ObjectId(cocktail_id)})
        if cocktail["author_id"] != session["id"]:
            flash("Unauthorized to edit cocktail")
            return redirect(
                url_for(
                    "cocktail",
                    cocktail_name=cocktail["cocktail_name"].replace(' ', '-'),
                    cocktail_id=cocktail["_id"]
                )
            )

        return render_template("cocktail-edit.html", cocktail=cocktail)

    return render_template("cocktail-create.html")


def formate_inputs(item, count):
    """Formates cocktail information into correct
    formate for the datebase.

    Variables are given by the cocktail_create()
    function.

    Count is set by cocktail_create()
    form inputs from cocktail create form
    """
    # Empty array to put the formated items into
    item_formatted = []

    # Iterates through the number of a specific input
    # count must be +1 as not starting at 0
    for x in range(1, count + 1):
        if item == "tool" or item == "instruction":

            # Gets the item from form input
            item_info = request.form.get(f"{item}-{x}")

            # Adds item to the formatted array
            item_formatted.append(item_info)

        elif item == "garnish":

            # Gets the item from form input
            item_amount = request.form.get(f"{item}-amount-{x}")
            item_name = request.form.get(f"{item}-name-{x}")

            # Formates the inputs into a array
            item_info = [f"{item_amount}", f"{item_name}"]

            # Adds item to the formatted array
            item_formatted.append(item_info)

        elif item == "ingredient":

            # Gets the item from form input
            item_amount = request.form.get(f"{item}-amount-{x}")
            item_unit = request.form.get(f"{item}-unit-{x}")
            item_name = request.form.get(f"{item}-name-{x}")

            # Formates the inputs into a array
            item_info = [f"{item_amount}", f"{item_unit}", f"{item_name}"]

            # Adds item to the formatted array
            item_formatted.append(item_info)

    return item_formatted


# Get users Bookmakers
def get_bookmarked_cocktails():
    """Retrieves bookmark cocktail IDs from user
    bookmark list in datebase. It then returns
    the cocktails from the IDs and puts them in
    a list.
    """
    if session.get('user'):
        # Get user bookmarked cocktial ids form db
        bookmark_list = mongo.db.users.find_one(
                {"username": session["user"]}).get("bookmarks")

        # Empty array to add the bookmarked cocktails to
        bookmarked_cocktial = []

        # Loops through bookmark list adding cocktails from db to arary above
        for cocktail_id in bookmark_list:

            cocktail = mongo.db.cocktails.find_one(
                {"_id": ObjectId(cocktail_id)}
            )

            bookmarked_cocktial.insert(0, cocktail)

        return bookmarked_cocktial

    else:
        return []


# Get bookmarks of user
def get_bookmarks():
    """Gets logged in users bookmarks if
    no user in session cookie it will
    set it to an empty list so forms that
    rely on it can still function.
    """
    if session.get('user'):
        bookmarks = mongo.db.users.find_one(
            {"username": session["user"]}
        ).get(
            "bookmarks"
        )

    # No bookmarks if no user is logged in
    else:
        bookmarks = []

    return bookmarks


# Bookmarking
def submit_bookmark(user_bookmarks):
    """Add or removes cocktail ID from
    session user bookmarks and updates it
    in the database.
    """
    if not session.get("user"):
        flash("You must be logged in to bookmark cocktails")

    else:
        cocktail_id = request.form.get("cocktail-id")

        cocktail = mongo.db.cocktails.find_one(
            {"_id": ObjectId(cocktail_id)})

        bookmark_count = cocktail.get("no_of_bookmarks")

        # Grab random number from form
        form_random_value = request.form.get("random"),

        # Block against reload re submits
        if form_random_value != session["formsubmitno"]:
            session["formsubmitno"] = form_random_value

            # Check if cocktail is already bookmarked
            if cocktail_id in user_bookmarks:
                # If it is remove it
                user_bookmarks.remove(cocktail_id)
                bookmark_count -= 1

            else:
                # If it is NOT add it
                user_bookmarks.append(cocktail_id)
                bookmark_count += 1

        # Stage query to find the session user
        # Stage the data to be updated
        query = {"_id": ObjectId(session["id"])}
        # $set allows only one key to be updated without stating the rest
        update = {"$set": {"bookmarks": user_bookmarks}}

        cocktail_query = {"_id": ObjectId(cocktail_id)}
        cocktail_update = {"$set": {"no_of_bookmarks": bookmark_count}}

        # Update datebase
        mongo.db.users.update_one(query, update)
        mongo.db.cocktails.update_one(cocktail_query, cocktail_update)


# Update User Info
def update_profile(profile_name, profile_id):
    """Stages and updates user information
    to the database.
    """
    # Grab random number from form
    form_random_value = request.form.get("random")

    # Block against reload re submits
    if form_random_value != session["formsubmitno"]:
        session["formsubmitno"] = form_random_value

        user_in_db = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})

        prev_username = request.form.get("username")

        # Check username isnt already taken by another user
        if user_in_db and profile_name != prev_username:
            # Tells user if the username is taken
            flash("Username unavailable. Please choose another.")
            return "true"

        else:
            username = request.form.get("username")
            image_url = request.form.get("image-url")

            # Stage query to find the session user
            # Stage the data to be updated
            query = {"_id": ObjectId(profile_id)}
            # $set allows only one key to be updated without stating the rest
            update = {
                "$set": {
                    "username": username,
                    "image": image_url
                }
            }
            flash("Changes Saved")
            session["user"] = request.form.get("username").lower()
            mongo.db.users.update_one(query, update)

            # Update cocktail author key
            if profile_name != prev_username:
                cocktail_query = {"author_id": profile_id}
                cocktail_update = {"$set": {"author": username}}

                mongo.db.cocktails.update_many(cocktail_query, cocktail_update)


# Submit Cocktail Rating
def submit_rating(user_rated_cocktails):
    """Calculates bookmark rating and
    adds the cocktail ID to the session
    user bookmark list and updates the
    database.
    """
    # Grab random number from form
    form_random_value = request.form.get("random")

    # Block against reload re submits
    if form_random_value != session["formsubmitno"]:
        session["formsubmitno"] = form_random_value

        if not session.get("user"):
            flash("You must be logged in to bookmark cocktails")

        else:
            # Find cocktial
            cocktail_id = request.form.get("cocktail-id")

            cocktail = mongo.db.cocktails.find_one(
                {"_id": ObjectId(cocktail_id)})

            # Get key values
            user_rating = int(request.form.get("star-rating"))
            no_rating = cocktail.get("no_rating")
            rating_sum = cocktail.get("rating_sum")

            # Work out new rating
            no_rating += 1
            new_rating_sum = rating_sum + user_rating
            new_rating = new_rating_sum / no_rating

            # Stage cocktial new key values
            cocktail_query = {"_id": ObjectId(cocktail_id)}
            cocktail_update = {
                "$set": {
                    "no_rating": no_rating,
                    "rating": new_rating,
                    "rating_sum": new_rating_sum
                }
            }

            # Add cocktail to users rated cocktails
            # Used to stop them rating it twice
            user_rated_cocktails.append(cocktail_id)

            # Stage user new key values
            user_query = {"_id": ObjectId(session["id"])}
            user_update = {"$set": {"rated_cocktails": user_rated_cocktails}}

            # Update datebase
            mongo.db.cocktails.update_one(cocktail_query, cocktail_update)
            mongo.db.users.update_one(user_query, user_update)


# Error Handler 404 Page Not Found
@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404


if __name__ == "__main__":
    app.run(
        host=os.environ.get("IP"),
        port=int(os.environ.get("PORT")),
        debug=False
    )
