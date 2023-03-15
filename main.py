import sqlalchemy.exc
from flask import Flask, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, CreateRegisterForm, CreateLoginForm, CreateCommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)
gravatar = Gravatar(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

## CONFIGURE LOGIN
login_manager = LoginManager()
login_manager.init_app(app)


##CONFIGURE TABLES
class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), nullable=False, unique=True)
    password = db.Column(db.String(250), nullable=False, unique=True)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    time = db.Column(db.DateTime(), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    author = relationship("User", back_populates="comments")
    parent_post = relationship("BlogPost", back_populates="comments")


with app.app_context():
    db.create_all()
    admin = db.session.get(User, 1)



def admin_only(func):
    @wraps(func)
    def internal(*args, **kwargs):
        if current_user.get_id() == str(admin.id):
            return func(*args, **kwargs)
        else:
            flash("Login like admin to access this resource")
            return redirect(url_for("login"))
    return internal


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    is_admin = True if current_user.get_id() == "1" else False
    return render_template("index.html", all_posts=posts,
                           logged_in=current_user.is_authenticated,
                           is_admin=is_admin,
                           admin_name=admin.name if admin else "")


@app.route('/register', methods=["GET", "POST"])
def register():
    register_form = CreateRegisterForm()
    if register_form.validate_on_submit():
        new_user = User(
            name=register_form.name.data.title(),
            email=register_form.email.data,
            password=generate_password_hash(register_form.password.data)
        )
        try:
            db.session.add(new_user)
            db.session.commit()
        except sqlalchemy.exc.IntegrityError:
            flash("There is an user with that email, try to login")
        return redirect(url_for("login"))
    return render_template("register.html", form=register_form,
                           logged_in=current_user.is_authenticated,
                           admin_name=admin.name if admin else "")


@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = CreateLoginForm()
    if login_form.validate_on_submit():
        user_email = login_form.email.data
        user_password = login_form.password.data
        user = User.query.filter_by(email=user_email).first()
        print(user)
        if user:
            if check_password_hash(user.password, user_password):
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("Wrong password, try again")
        else:
            flash("Wrong Email, try again")

    return render_template("login.html", form=login_form,
                           logged_in=current_user.is_authenticated,
                           admin_name=admin.name if admin else "")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.session.get(BlogPost, post_id)
    is_admin = True if current_user.get_id() == "1" else False  # 1 --> admin id
    comment_form = CreateCommentForm()
    if comment_form.validate_on_submit():
        if current_user.is_authenticated:
            new_text = comment_form.comment.data
            new_time = datetime.now()
            new_comment = Comment(
                text=new_text,
                time=new_time,
                author_id=int(current_user.get_id()),
                post_id=post_id
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            flash("To comment please login to the page")
            return redirect(url_for("login"))
    post_comments = db.session.get(BlogPost, post_id).comments
    return render_template("post.html", post=requested_post,
                           logged_in=current_user.is_authenticated,
                           is_admin=is_admin,
                           admin_name=admin.name if admin else "",
                           form=comment_form,
                           comments=post_comments)


@app.route("/about")
def about():
    return render_template("about.html",
                           logged_in=current_user.is_authenticated,
                           admin_name=admin.name if admin else "")


@app.route("/contact")
def contact():
    return render_template("contact.html",
                           logged_in=current_user.is_authenticated,
                           admin_name=admin.name if admin else "")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, is_edit=False,
                           logged_in=current_user.is_authenticated,
                           admin_name=admin.name if admin else "")


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, is_edit=True,
                           logged_in=current_user.is_authenticated,
                           admin_name=admin.name if admin else "")


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
