from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy

from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_gravatar import Gravatar
from flask_ckeditor import CKEditor
from forms import CreatePostForm, LoginForm, RegisterForm, CommentForm
from functools import wraps
from datetime import date
import os
import smtplib

EMAIL = "YOUR EMAIL"
PASS = "YOUR PASSWORD"

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)
login_manager = LoginManager()
login_manager.init_app(app)

## CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


gravatar = Gravatar(app=app, size=45, rating='g', default='retro', force_default=False, force_lower=False,
                    use_ssl=False, base_url=None)


##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)

    # *******ONE TO MANY RELATIONSHIP***************
    posts = relationship("BlogPost", back_populates='author')
    comments = relationship("Comment", back_populates='comment_author')
    # ********************************************************
    email = db.Column(db.String(250), unique=True)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)


db.create_all()


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # ******* Here Parent_class(User) 'users.id'
    # which in the format of Camel_Case converted into
    # 'camel_case'***********

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # ***********PARENT RELATIONSHIP***************
    comments = relationship('Comment', back_populates='parent_post')
    author = relationship('User', back_populates='posts')


db.create_all()


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    comment_author = relationship('User', back_populates='comments')

    # ***********CHILD RELATIONSHIP***************
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=False)
    parent_post = relationship('BlogPost', back_populates='comments')
    text = db.Column(db.Text, nullable=False)


db.create_all()


def admin_only(f):
    @wraps(f)
    def forbidden(*args, **kwargs):
        if current_user.id != 1:
            abort(403)
        return f(*args, **kwargs)

    return forbidden


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if request.method == "POST":
        email = request.form['email']
        print(email)
        password = request.form['password']
        # Comparing user's entered email against email stored in database
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("That email does not exist. Please try again.")
        elif not check_password_hash(user.password, password):
            flash("Password incorrect. Please try again.")
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))

    return render_template("login.html", form=form)


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == "POST":
        if User.query.filter_by(email=request.form['email']).first():
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
        new_user = User()
        new_user.email = request.form['email']
        new_user.password = generate_password_hash(request.form['password'], method='pbkdf2:sha256', salt_length=8)
        new_user.name = request.form['name']
        print(new_user.password)

        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/")
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for('login'))
        new_comment = Comment(text=form.comment_text.data, comment_author=current_user, parent_post=requested_post)
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html", post=requested_post, form=form, current_user=current_user)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def make_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        blogpost = BlogPost(title=form.title.data, subtitle=form.subtitle.data, author_id=current_user.id,
                            img_url=form.img_url.data, body=form.body.data, date=date.today().strftime("%B %m %Y"))
        db.session.add(blogpost)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(title=post.title, subtitle=post.subtitle, author=post.author, img_url=post.img_url,
                               body=post.body, )

    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        post.date = date.today().strftime("%B %m %Y")
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user)


@app.route("/delete/<post_id>")
@admin_only
def delete_post(post_id):
    post = db.session.query(BlogPost).get(post_id)
    if post:
        db.session.delete(post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("index.html", post_id=post.id)


@app.route("/about")
def about():
    return render_template("about.html")


##CONTACT
@app.route("/contact", methods=['GET', 'POST'])
def contact():
    if request.method == "POST":
        data = request.form
        send_email(data["name"], data["email"], data["message"])
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", msg_sent=False)


def send_email(name, email, message):
    email_message = f"Subject:New Message\n\nName: {name}\nEmail: {email}\nMessage: {message}".encode("utf-8")
    with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
        connection.starttls()
        connection.login(EMAIL, PASS)
        connection.sendmail(EMAIL, EMAIL, email_message)


if __name__ == "__main__":
    app.run(debug=True)
