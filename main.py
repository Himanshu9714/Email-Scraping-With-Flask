from flask import Flask, flash, jsonify, render_template, request, redirect, url_for, abort, Response
from werkzeug.utils import secure_filename
import os
from flask import send_from_directory
import pandas as pd
from web_scraping import scraping_emails
import json
import logging
from celery_utils import make_celery

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'xlsx'}
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = '427c64d1e8e2d5c13bff0beeb588131a'
app.config['CELERY_BROKER_URL'] = "redis://redis:6379/"
app.config['CELERY_BACKEND'] = "redis://redis:6379/"
celery = make_celery(app)

logging.basicConfig(filename='record.log', level=logging.DEBUG, format=f'%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')

@celery.task(name='main.scrap_emails')
def scrap_emails(list_of_urls):
    scraping_emails(list_of_urls, app.config['UPLOAD_FOLDER'])

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
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_to_process = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_to_process)
            print(file_to_process)

            try:
                df = pd.read_excel(file_to_process,engine='openpyxl',dtype=object,header=None)
                l = df.values.tolist()
                res = list(map(''.join, l))
                task = scrap_emails.delay(res)
                print(f"\n\nThis is task: {task}\nTask id: {task.id}")
                response_obj = {
                    "status": "success",
                    "data": {
                        "task_id": task.id
                    }
                }
                app.logger.info("Emails scrapped Successfully!")
                return jsonify(response_obj), 202
            except Exception as e:
                print("This is error:", e)
                app.logger.warning("File format provided by user doesn't match")
                err_msg = json.dumps({'Message': "OOPS! Email Scraper couldn't scrap your emails from uploaded file; looks like it doesn't match with appropriate format."})
                abort(Response(err_msg, 400))
    return render_template('index.html')

@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)
    
app.add_url_rule(
    "/uploads/<name>", endpoint="download_file", build_only=True
)

@app.route("/tasks/<task_id>", methods=["GET"])
def get_status(task_id):
    task = scrap_emails.AsyncResult(task_id)
    print("Task name in tasks:", task)
    if task:
        response_object = {
            "status": "success",
            "data": {
                "task_id": task.id,
                "task_status": task.status,
                "task_result": task.result,
            },
        }
    else:
        response_object = {"status": "error"}
    return jsonify(response_object)

if __name__ == '__main__':
    app.run(debug=True)
    app.cli()