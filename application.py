from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Select the transactions done by the buyer
    items = db.execute("SELECT * FROM transactions WHERE id = :id",
            id=session["user_id"])

    # Create variable for the grand total to be used later
    grand_total = 0

    # Update prices and total (theoretically, there might be changes in prices)
    for item in items:
        symbol = item["symbol"]
        shares = item["shares"]
        stock = lookup(symbol)
        total = shares * stock["price"]
        grand_total += total
        db.execute("UPDATE transactions SET price = :price, total = :total WHERE id = :id AND symbol = :symbol",
                    price = usd(stock["price"]),
                    total = usd(total),
                    id = session["user_id"],
                    symbol = symbol)

    # Select user's updated cash to be used for the total
    updated_cash = db.execute("SELECT cash FROM users WHERE id = :id",
                    id = session["user_id"])

    # Add the updated cash with the grand total
    grand_total += updated_cash[0]["cash"]

    # Print transaction
    print_transactions = db.execute("SELECT * FROM transactions WHERE id = :id",
                    id = session["user_id"])

    return render_template("index.html", stocks = print_transactions, \
                    cash = usd(updated_cash[0]["cash"]), total = usd(grand_total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("Missing Symbol!")

        # Ensure shares was submitted
        if not request.form.get("shares"):
            return apology("Missing Shares!")

        try:
            shares = int(request.form.get("shares"))

            # Ensure positive integer was submitted
            if shares < 0:
                return apology("Value should be at leat 0!")

        except:
            return apology("Shares must be non fractional, non negative and only numeric! ")

        # Get quote with help from help function
        quote = lookup(request.form.get("symbol"))

        # Check if lookup failed
        if quote == None:
            return apology("Invalid Symbol")

        # Check if user can afford stock
        usercash = db.execute("SELECT cash FROM users WHERE id = :id",
            id=session["user_id"])

        spend = shares * quote["price"]

        # Check if user can afford the shares
        if not usercash or float(usercash[0]["cash"]) < spend:
            return apology("Insufficient funds!")

        # Check if user already has the stock
        stockshares = db.execute("SELECT shares FROM transactions WHERE id = :id AND symbol = :symbol",
                        id = session["user_id"],
                        symbol = quote["symbol"])

        if not stockshares:

            # Perform buy by inserting details @ transaction table
            db.execute("INSERT INTO transactions (id, price, symbol, name, shares, total) VALUES(:username, :price, \
                        :symbol, :name, :shares, :total)",
                        username = session["user_id"],
                        price = quote["price"],
                        name = quote["name"],
                        shares = shares,
                        total = shares * quote["price"],
                        symbol = quote["symbol"].upper())

        # Add shares to the current stock
        else:
            updatedshares = stockshares[0]["shares"] + shares
            db.execute("UPDATE transactions SET shares = :shares WHERE id = :id AND symbol = :symbol",
                            shares = updatedshares,
                            id = session["user_id"],
                            symbol = quote["symbol"])

        # Update user cash
        update = db.execute("UPDATE users SET cash = cash - :spend WHERE id = :id",
                            id = session["user_id"],
                            spend = shares * quote["price"])

        # Update history
        db.execute("INSERT INTO history (id, symbol, shares, price) VALUES(:id, :symbol, :shares, :price)",
                        id = session["user_id"],
                        symbol = quote["symbol"],
                        shares = shares,
                        price = usd(quote["price"]))

        return redirect(url_for("index"))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Access entries on history table
    histories = db.execute("SELECT * FROM history WHERE id = :id",
                    id = session["user_id"])

    return render_template("history.html", histories = histories)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        print(rows)
        print(len(rows))

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("Missing Symbol!")

        # Store symbol in all caps
        symbol = request.form.get("symbol").upper()

        # Get quote with help from help function
        quote = lookup(symbol)

        # Check if lookup failed
        if quote == None:
            return apology("Invalid Symbol")

        return render_template("quoted.html", name = quote["name"], price = usd(quote["price"]), symbol = symbol)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Missing username!", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Missing password!", 400)

        # Check if password matches
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Password don't match!", 400)

        # Add username and hashed password to database
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                        username=request.form.get("username"),
                        hash=generate_password_hash(request.form.get("password")))

        # If insertion failed, it means username already exists. Return apology.
        if not result:
            return apology("Username already exists!", 400)

        session["user_id"] = result

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":

        # Selecting symbols on transactions table in prep for rendering of symbols on SELECT format on jinja
        stocksymbols = db.execute("SELECT symbol FROM transactions WHERE id = :id",
                        id = session["user_id"])
        return render_template("sell.html", stocksymbols = stocksymbols)

    else:

        # Ensure shares was submitted
        if not request.form.get("shares"):
            return apology("Missing Shares!")

        shares = int(request.form.get("shares"))

        # Ensure positive integer was submitted
        if shares < 0:
            return apology("Value should be at leat 0!")

        # Get quote with help from help function
        quote = lookup(request.form.get("symbol"))

        # Look for the stock the buyer wants to sell
        stockshares = db.execute("SELECT shares FROM transactions WHERE id = :id AND symbol = :symbol",
                        id = session["user_id"],
                        symbol = quote["symbol"])

        # Ensure that enough shares are present to be sold
        if not stockshares or int(stockshares[0]["shares"]) < shares:
            return apology("Insufficient Shares!")

        # Deduct shares with shares entered
        totalshares = stockshares[0]["shares"] - shares

        # Update the shares of the stock (how much was sold)
        db.execute("UPDATE transactions SET shares = shares - :shares WHERE id = :id AND symbol = :symbol",
                    id=session["user_id"],
                    shares = int(request.form.get("shares")),
                    symbol = quote["symbol"])

        # Delete entry if otal shares of stock is zero
        if totalshares == 0:
            db.execute("DELETE FROM transactions where id = :id AND symbol = :symbol",
                        id = session["user_id"],
                        symbol = quote["symbol"])

        # Update user's cash
        db.execute("UPDATE users SET cash = cash + :profit WHERE id = :id",
                    id=session["user_id"],
                    profit = shares * quote["price"])

        # Update history
        db.execute("INSERT INTO history (id, symbol, shares, price) VALUES(:id, :symbol, :shares, :price)",
                        id = session["user_id"],
                        symbol = quote["symbol"],
                        shares = shares * -1,
                        price = usd(quote["price"]))

        return redirect(url_for("index"))


@app.route("/changepw", methods=["GET", "POST"])
@login_required
def changepw():
    """Change the password of the user user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure current password was submitted
        if not request.form.get("current"):
            return apology("Missing Current Password!", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Missing password!", 403)

        # Check if password matches
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Password don't match!", 403)

        # Query database for the id of the user
        id = db.execute("SELECT * FROM users WHERE id = :id",
                          id=session["user_id"])

        # Ensure current password is correct
        if not check_password_hash(id[0]["hash"], request.form.get("current")):
            return apology("Wrong Current Password", 403)

        # Add new hashed password to database
        result = db.execute("UPDATE users SET hash = :hash where id = :id",
                        id=session["user_id"],
                        hash=generate_password_hash(request.form.get("password")))

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("changepw.html")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
