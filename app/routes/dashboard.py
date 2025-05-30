from functools import wraps
from app.models.availabletimes import AvailableTimes
from app.models.booking import Booking
from app.models.client import Client
from app.models.services import Service
from app.static.forms.availability import AvailabilityForm
from app.static.forms.booking import BookingForm
from app.static.forms.myservices import ServiceForm
from .. import db
from app.models.rewards import RewardTransaction
from app.static.edit import EditForm
from app.static.rewards import RewardsForm
from app.static.forms.contact import ContactForm
from app.static.pricing import PriceForm
from . import main
from flask import flash, render_template, redirect, url_for, request
from flask_login import login_required, current_user
from ..auth.routes import send_validate_account_email
import calendar
from flask_mailman import EmailMessage

def check_is_confirmed(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.is_confirmed() == False:
            flash("Please confirm your account!", "warning")
            return redirect(url_for("main.inactive"))
        return func(*args, **kwargs)

    return decorated_function

@main.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    cal = calendar.HTMLCalendar(calendar.SUNDAY)
    form = AvailabilityForm()
    times = AvailableTimes.query.filter_by(user_id=current_user.id).all()
    bookings = Booking.query.filter_by(user_id=current_user.id).all()
    
    user_id = current_user.id
    availability = [{}]
    appointments = [{}]
    for time in times:
        availability = [
            {
                'todo' : 'Start Availability',
                'date' : time.available_start
            },
            {
                'todo' : 'End Availability',
                'date' : time.available_end
            }
        ]
    for booking in bookings:
        bkid = booking.service_type
        service = Service.query.filter_by(id=bkid).first()
        appointments = [
            {
                'todo' : service.name,
                'date' : booking.booking_date
            }
        ]
    if form.validate_on_submit():
        available = AvailableTimes(
            user_id=current_user.id,
            available_start=form.availablefrom.data,
            available_end=form.availableto.data
        )
        db.session.add(available)
        db.session.commit()
        return redirect(url_for('main.dashboard'))
    return render_template('dashboard.html', calendar=cal.formatmonth(2025, 3), form=form, availability=availability, appointments=appointments, user_id=user_id)

@main.route('/inactive')
@login_required
def inactive():
    if current_user.is_confirmed() == True:
        return redirect(url_for('main.dashboard'))
    return render_template('inactive.html')

@main.route('/resend_confirmation')
@login_required
def resend():
    if current_user.is_confirmed() == True:
        flash('Account already confirmed.')
        return redirect(url_for('main.dashboard'))
    send_validate_account_email(current_user)
    return redirect(url_for('main.inactive'))

@main.route('/myservices', methods=['GET', 'POST'])
@login_required
def myservices():
    form = ServiceForm()

    if request.method == 'POST' and 'delete_id' in request.form:
        service_id = request.form.get('delete_id')
        service = Service.query.filter_by(id=service_id, user_id=current_user.id).first()
        if service:
            db.session.delete(service)
            db.session.commit()
            flash('Service deleted.', 'success')
        return redirect(url_for('main.myservices'))

    if form.validate_on_submit():
        service = Service(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            user_id=current_user.id,
            is_active=form.is_active.data
        )
        db.session.add(service)
        db.session.commit()
        flash('Service added successfully!', 'success')
        return redirect(url_for('main.myservices'))

    servicesList = Service.query.filter_by(user_id=current_user.id).all()

    return render_template('myservices.html', form=form, servicesList=servicesList)


@main.route('/rewards', methods=['GET', 'POST'])
@login_required
def rewards():
    clientList = Client.query.filter_by(user_id=current_user.id).all()
    return render_template('loyaltycard.html', clientList=clientList)

@main.route('/profilesettings', methods=['GET', 'POST'])
def profilesettings():
    username=current_user.username
    account='Customer'
    if current_user.is_client():
        account='Owner'
    return render_template('profilesettings.html', username=username, account=account)

@main.route('/editprofilesettings', methods=['GET', 'POST'])
def editprofilesettings():
    user = current_user
    account='Customer'
    form = EditForm()
    if form.validate_on_submit():
        user.username=form.username.data
        account=form.account_type.data
        db.session.commit()
        flash('Profile changes saved.')
        return redirect(url_for('main.profilesettings'))

    return render_template('editprofilesettings.html', form=form)

@main.route('/booking/<int:user_id>', methods=['GET', 'POST'])
def bookings(user_id):
    form = BookingForm()
    user = current_user
    services = Service.query.filter_by(user_id=current_user.id).all()
    services_list = [(i.id, i.name) for i in services]
    form.service_type.choices = services_list
    if form.validate_on_submit():
        booking = Booking(
            service_type = form.service_type.data,
            booking_date = form.date.data,
            user_id = current_user.id
        )
        db.session.add(booking)
        db.session.commit()

        client = Client(
            name = form.name.data,
            email = form.email.data,
            phone = form.phone.data,
            user_id = current_user.id,
            booking_id = booking.id
        )
        db.session.add(client)
        db.session.commit()
        return redirect(url_for('main.bookings', user_id=current_user.id))
    return render_template('booking.html', form=form, user=user, services=services)

@main.route('/clients')
def clients():
    clientList = Client.query.filter_by(user_id=current_user.id).all()
    return render_template('clients.html', clientList=clientList)

@main.route('/pricing')
def pricing():
    form = PriceForm()
    if form.validate_on_submit():
        pricing=form.billing_type.data
        #return redirect(url_for(main.payment))
    return render_template('pricing.html', form=form)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        # Compose the message
        email_body = f"""
New message from Loyals Contact Form:

Name: {form.name.data}
Email: {form.email.data}

Message:
{form.message.data}
        """
        message = EmailMessage(
            subject="New Contact Form Submission - Loyals",
            body=email_body,
            to=["loyalsbooking@gmail.com"]
        )
        try:
            message.send()
            flash("Thanks for your message! We'll get back to you shortly.")
        except Exception as e:
            print("Email send error:", e)
            flash("Sorry, we couldn't send your message right now.", "danger")

        return redirect(url_for('main.contact'))

    return render_template("contact.html", form=form)