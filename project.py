#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect
from flask import jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker, joinedload
from models import Base, Category, Item, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Item Catalog App"

# Connect to Database and create database session
engine = create_engine('sqlite:///itemcatalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = (''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(32)))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code, now compatible with Python3
    request.get_data()
    code = request.data.decode('utf-8')

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    # Submit request, parse response - Python3 compatible
    h = httplib2.Http()
    response = h.request(url, 'GET')[1]
    str_response = response.decode('utf-8')
    result = json.loads(str_response)

    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps("Current user "
                                 "is already connected."), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output +=  """ "
                    style = "width: 300px;
                    height: 300px;
                    border-radius: 150px;
                    -webkit-border-radius: 150px;
                    -moz-border-radius: 150px;
                  " > """
    flash("you are now logged in as %s" % login_session['username'])
    return output


# Helper Functions
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except Exception:
        return None

# DISCONNECT - Revoke a current user's token and reset their login_session
@app.route('/logout')
def gdisconnect():
    # Only disconnect a connected user.
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        # Reset the user's sesson.
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']

        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return redirect(url_for('showLatestItems'))
    else:
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# JSON APIs to view categories Information
@app.route('/catalog.json')
def CatalogJSON():
    categories = (session.query(Category).options(
                 joinedload(Category.items)).all())
    return (jsonify(Catalog=[dict(c.serialize,
            items=[i.serialize for i in c.items]) for c in categories]))


# Show all Catalogs
@app.route('/')
def showLatestItems():
    Categories = session.query(Category).all()
    Items = (session.query(Item.title, Item.id, Item.description, Item.user_id,
             Category.name).join(Category, Item.cat_id == Category.id).order_by
             (Item.id.desc()))
    if 'username' not in login_session:
        return (render_template('publicLatestItems.html',
                Items=Items, Categories=Categories))
    else:
        return (render_template('latestItems.html',
                Items=Items, Categories=Categories))

# Show Category Items
@app.route('/catalog/<string:Category_name>/items')
def showCategoryItem(Category_name):
    Categories = session.query(Category).all()
    Items = (session.query(Item).join(Category,
             Item.cat_id == Category.id).filter
             (Category.name == Category_name))
    if 'username' not in login_session:
        return (render_template('publicCategoryItems.html', Items=Items,
                Categories=Categories, Category_name=Category_name))
    else:
        return (render_template('categoryItems.html', Items=Items,
                Categories=Categories, Category_name=Category_name))


# Show Item
@app.route('/catalog/<string:Category_name>/<string:Item_name>')
def showItem(Category_name, Item_name):
    CategoryItem = (session.query(Item).join(Category,
                    Item.cat_id == Category.id).filter
                    (Item.title == Item_name,
                    Category.name == Category_name))
    if 'username' not in login_session:
        return render_template('publicItem.html', CategoryItem=CategoryItem)
    else:
        return render_template('item.html', CategoryItem=CategoryItem)


# Create a new item
@app.route('/catalog/items/new/', methods=['GET', 'POST'])
def newCategoryItem():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newItem = Item(title=request.form['name'],
                       description=request.form['description'],
                       cat_id=request.form['category'],
                       user_id=login_session['user_id'])
        session.add(newItem)
        flash('New Item %s Successfully Created' % newItem.title)
        session.commit()
        return redirect(url_for('showLatestItems'))
    else:
        return render_template('newCategoryItem.html')

# Edit item
@app.route('/catalog/items/<string:Item_name>/edit/', methods=['GET', 'POST'])
def editItem(Item_name):
    if 'username' not in login_session:
        return redirect('/login')
    editedItem = session.query(Item).filter(Item.title == Item_name).one()
    if login_session['user_id'] != editedItem.user_id:
        return """<script>function myFunction()
                  {alert('You are not authorized to edit this items.');}
                  </script><body onload='myFunction()''>"""
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['category']:
            editedItem.cat_id = request.form['category']
        session.add(editedItem)
        session.commit()
        flash('Item Successfully Edited')
        return redirect(url_for('showLatestItems'))
    else:
        return render_template('edititem.html', item=editedItem)


# Delete an item
@app.route('/catalog/items/<string:Item_name>/delete', methods=['GET', 'POST'])
def deleteItem(Item_name):
    if 'username' not in login_session:
        return redirect('/login')
    itemToDelete = session.query(Item).filter(Item.title == Item_name).one()
    if login_session['user_id'] != itemToDelete.user_id:
        return """<script>function myFunction()
                  {alert('You are not authorized to delete this items.');}
                  </script><body onload='myFunction()''>"""
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Item Successfully Deleted')
        return redirect(url_for('showLatestItems'))
    else:
        return render_template('deleteItem.html', item=itemToDelete)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
