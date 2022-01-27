from venv import create
from flask import Flask
from main import app
import redis
from rq import Connection, Worker
