from flask import Flask, flash, jsonify, render_template, request, redirect, url_for, abort, Response
from werkzeug.utils import secure_filename
import os
from flask import send_from_directory
import pandas as pd
from web_scraping import scraping_emails
import json
import logging

basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx'}
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(basedir,UPLOAD_FOLDER)
app.config['SECRET_KEY'] = '427c64d1e8e2d5c13bff0beeb588131a'
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
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_to_process = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_to_process)

            try:
                df = pd.read_excel(file_to_process,engine='openpyxl',dtype=object,header=None)
                l = df.values.tolist()
                res = list(map(''.join, l))
                scraping_emails(res, app.config['UPLOAD_FOLDER'])
                app.logger.info("Emails scrapped Successfully!")
            except Exception:
                app.logger.warning("File format provided by user doesn't match")
                err_msg = json.dumps({'Message': "OOPS! Email Scraper couldn't scrap your emails from uploaded file; looks like it doesn't match with appropriate format."})
                abort(Response(err_msg, 400))
            return jsonify({"path": filename})
    return render_template('index.html')

@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)
app.add_url_rule(
    "/uploads/<name>", endpoint="download_file", build_only=True
)
if __name__ == '__main__':
    app.run()