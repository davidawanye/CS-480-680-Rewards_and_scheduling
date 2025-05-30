from ensurepip import bootstrap
from flask import render_template, redirect, request, url_for, flash, render_template_string
from flask_mailman import EmailMessage
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import select
from . import auth
from .login_manager import load_user
from .. import db, login_manager
from ..models.user import User
from ..static.forms.login import LoginForm
from ..static.forms.register import RegistrationForm
from ..static.forms.reset_password_form import ResetPasswordForm
from ..static.forms.passwordreset import PasswordResetForm
from ..static.edit import EditForm
from ..auth.reset_pass_email_content import reset_password_email_html_content
from ..auth.validate_email_content import validate_email_html_content

@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            next = request.args.get('next')
            if next is None or not next.startswith('/'):
                next = url_for('main.dashboard')
            return redirect(next)
        flash('Invalid Username or Password')
    return render_template('auth/login.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('main.index'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data
        )
        db.session.add(user)
        db.session.commit()
        flash('Account created')
        flash('Please validate email address')
        send_validate_account_email(user)
        login_user(user)
        flash('A confirmation email has been sent to your email address, please validate your account.')
        return redirect(url_for('main.inactive'))
    return render_template('auth/register.html', form=form)

def send_validate_account_email(user):
    validate_email_url = url_for('auth.confirm_email', token=user.generate_password_reset_token(), user_id=user.id, _external=True)
    email_body = render_template_string(validate_email_html_content, validate_email_url=validate_email_url)
    message = EmailMessage(subject='Validate Your Account', body=email_body, to=[user.email])
    message.content_subtype = 'html'
    message.send()

@auth.route('/confirm/<token>/<int:user_id>')
@login_required
def confirm_email(token, user_id):
    if current_user.is_confirmed() == True:
        flash('Account already confirmed.')
        return redirect(url_for('main.dashboard'))
    user = User.validate_reset_password_token(token, user_id)

    if not user:
        flash('The confirmation link is invalid or has expired')
    else:
        user.confirm_account()
        db.session.commit()
        flash('Your account has been confirmed.')
    return redirect(url_for('main.dashboard'))

@auth.route('/reset_password', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = PasswordResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            send_reset_password_email(user)

        flash('Instructions to reset your password were sent to your email address')

        return redirect(url_for('auth.reset_password_request'))
    return render_template('auth/forgotpass.html', form=form)

def send_reset_password_email(user):
    reset_password_url = url_for('auth.reset_password', token=user.generate_password_reset_token(), user_id=user.id, _external=True)
    email_body = render_template_string(reset_password_email_html_content, reset_password_url=reset_password_url)
    message = EmailMessage(subject='Reset your password', body=email_body, to=[user.email])
    message.content_subtype = 'html'
    message.send()

@auth.route('/reset_password/<token>/<int:user_id>', methods=['GET', 'POST'])
def reset_password(token, user_id):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    user = User.validate_reset_password_token(token, user_id)
    if not user:
        return render_template('auth/reset_password_error.html', title='Reset Password error')
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.password = form.password.data
        db.session.commit()

        return render_template('auth/reset_password_success.html', title='Reset Password success')
    
    return render_template('auth/reset_password.html', title='Reset Password', form=form)

@auth.route('/admin', methods=['GET', 'POST'])
def admin():
    return render_template('auth/admin.html')

