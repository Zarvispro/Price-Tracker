from flask import Flask, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import requests
from bs4 import BeautifulSoup
import schedule
import time
import threading
import platform
from fake_useragent import UserAgent

# Import notification library based on platform
if platform.system() == 'Darwin':
    from pync import Notifier
else:
    from plyer import notification

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///price_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
ua = UserAgent()
session = requests.Session()


class Tracker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    selectors = db.Column(db.String(500), nullable=False)
    threshold = db.Column(db.Float, nullable=False)
    notification_time = db.Column(db.String(10), nullable=False)


def get_product_price(url, selectors):
    headers = {
        'User-Agent': ua.random
    }
    response = session.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    for selector in selectors:
        price_tag = soup.select_one(selector)
        if price_tag:
            return price_tag.text.strip()

    raise ValueError("Could not find the price on the page")


def send_notification(title, message):
    if platform.system() == 'Darwin':
        Notifier.notify(message, title=title)
    else:
        notification.notify(
            title=title,
            message=message,
            timeout=10  # seconds
        )


def check_price(tracker):
    try:
        price = get_product_price(tracker.url, tracker.selectors.split(','))
        print(f"The price for {tracker.name} is: {price}")
        price_value = float(price.replace('£', '').replace(',', ''))

        if price_value < tracker.threshold:
            send_notification(
                title='Price Alert!',
                message=f'The price for {tracker.name} has dropped to £{price}. Check it out here: {tracker.url}'
            )
    except Exception as e:
        print(f"An error occurred: {e}")


def schedule_check(tracker):
    schedule.every().day.at(tracker.notification_time).do(check_price, tracker)


def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = request.form['name']
        url = request.form['url']
        selectors = request.form['selectors']
        threshold = float(request.form['threshold'])
        notification_time = request.form['notification_time']

        tracker = Tracker(name=name, url=url, selectors=selectors, threshold=threshold,
                          notification_time=notification_time)
        db.session.add(tracker)
        db.session.commit()

        schedule_check(tracker)

        return redirect(url_for('index'))

    trackers = Tracker.query.all()
    return render_template('index.html', trackers=trackers)


@app.route('/edit/<int:tracker_id>', methods=['GET', 'POST'])
def edit(tracker_id):
    tracker = Tracker.query.get_or_404(tracker_id)
    if request.method == 'POST':
        tracker.name = request.form['name']
        tracker.url = request.form['url']
        tracker.selectors = request.form['selectors']
        tracker.threshold = float(request.form['threshold'])
        tracker.notification_time = request.form['notification_time']

        db.session.commit()

        schedule.clear(tracker_id)
        schedule_check(tracker)

        return redirect(url_for('index'))

    return render_template('edit.html', tracker=tracker)


@app.route('/delete/<int:tracker_id>', methods=['POST'])
def delete(tracker_id):
    tracker = Tracker.query.get_or_404(tracker_id)
    db.session.delete(tracker)
    db.session.commit()

    schedule.clear(tracker_id)
    return redirect(url_for('index'))


if __name__ == '__main__':
    threading.Thread(target=run_scheduler).start()
    app.run(debug=True)
