from flask import Flask, render_template, request
from CashOnline.CashInterpreter import interpret_command, get_prompt


app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.twig", prompt=get_prompt())


@app.route("/interpret", methods=["POST"])
def interpret():
    cmd = request.form["cmd"]
    value = interpret_command(cmd)
    return "<br>".join(value).replace("\n", "<br>") + "|" + get_prompt()
