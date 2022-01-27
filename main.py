from venv import create
from flask import Flask, flash, jsonify, render_template, request, redirect, url_for, abort, Response
from werkzeug.utils import secure_filename
import os
from flask import send_from_directory
import pandas as pd
from web_scraping import scraping_emails
import json
import logging
import redis
from rq import Queue, Connection, Worker
from flask.cli import FlaskGroup



# basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'xlsx'}
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = '427c64d1e8e2d5c13bff0beeb588131a'
app.config['REDIS_URL'] = 'redis://localhost:6379/0'
app.config['QUEUES'] = ["default"]

@app.cli.command("run_worker")
def run_worker():
    print("This is worker function")
    redis_url = app.config["REDIS_URL"]
    redis_connection = redis.from_url(redis_url)
    with Connection(redis_connection):
        worker = Worker(app.config["QUEUES"])
        worker.work()

logging.basicConfig(filename='record.log', level=logging.DEBUG, format=f'%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')

def allowed_file(filename):
    app.logger.info("Checking File Extension")
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        app.logger.info("Getting file from request object if exist")
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']
        print("File name form:", file.filename)
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_to_process = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_to_process)
            print(file_to_process)

            try:
                with Connection(redis.from_url(app.config['REDIS_URL'])):
                    q = Queue()
                    df = pd.read_excel(file_to_process,engine='openpyxl',dtype=object,header=None)
                    l = df.values.tolist()
                    res = list(map(''.join, l))
                    task = q.enqueue(scraping_emails(res, app.config['UPLOAD_FOLDER']))
                    print(f"\n\nThis is task: {task}\nTask id: {task.get_id()}")
                response_obj = {
                    "status": "success",
                    "data": {
                        "task_id": task.get_id()
                    }
                }
                app.logger.info("Emails scrapped Successfully!")
                return jsonify(response_obj), 202
            except Exception as e:
                print("This is error:", e)
                app.logger.warning("File format provided by user doesn't match")
                err_msg = json.dumps({'Message': "OOPS! Email Scraper couldn't scrap your emails from uploaded file; looks like it doesn't match with appropriate format."})
                abort(Response(err_msg, 400))
            # return jsonify({"path": filename})
    return render_template('index.html')

@app.route('/uploads/<name>')
def download_file(name):
    print("In the download directory")
    print(app.config["UPLOAD_FOLDER"])
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)
app.add_url_rule(
    "/uploads/<name>", endpoint="download_file", build_only=True
)

@app.route("/tasks/<task_id>", methods=["GET"])
def get_status(task_id):
    with Connection(redis.from_url(app.config["REDIS_URL"])):
        q = Queue()
        task = q.fetch_job(task_id)
    if task:
        response_object = {
            "status": "success",
            "data": {
                "task_id": task.get_id(),
                "task_status": task.get_status(),
                "task_result": task.result,
            },
        }
    else:
        response_object = {"status": "error"}
    return jsonify(response_object)

if __name__ == '__main__':
    app.run(debug=True)
    app.cli()