
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Category, Item, User

engine = create_engine('sqlite:///itemcatalog.db')
# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
# A DBSession() instance establishes all conversations with the database
# and represents a "staging zone" for all the objects loaded into the
# database session object. Any change made against the objects in the
# session won't be persisted into the database until you call
# session.commit(). If you're not happy about the changes, you can
# revert all of them back to the last commit by calling
# session.rollback()
session = DBSession()


# Create dummy user
User1 = User(name="Robo Barista", email="tinnyTim@udacity.com",
             picture='https://pbs.twimg.com/profile_images/2671170543/18debd694829ed78203a5a36dd364160_400x400.png')
session.add(User1)
session.commit()

User2 = User(name="Tester", email="Tester@Test.com",
             picture='https://pbs.twimg.com/profile_images/2671170543/18debd694829ed78203a5a36dd364160_400x400.png')
session.add(User2)
session.commit()

category1 = Category(name="Soccer")

session.add(category1)
session.commit()

Item2 = Item(user_id=1, title="Soccer cleats", description="The shoes",
                      category=category1)

session.add(Item2)
session.commit()


Item2 = Item(user_id=1, title="Jersy", description="The shirt",
                      category=category1)

session.add(Item2)
session.commit()

category2 = Category(name="Basketball")

session.add(category2)
session.commit()

category3 = Category(name="Baseball")

session.add(category3)
session.commit()

Item2 = Item(user_id=1, title="Bat", description="The bat",
                      category=category3)

session.add(Item2)
session.commit()

category4 = Category(name="Frisbee")

session.add(category4)
session.commit()

category5 = Category(name="Snowboarding")

session.add(category5)
session.commit()

Item2 = Item(user_id=2, title="Snowboard", description="They are boards where both feet are secured to the same board, which are wider than skis",
                      category=category5)

session.add(Item2)
session.commit()

category6 = Category(name="Rock Climbing")

session.add(category6)
session.commit()

category7 = Category(name="Foosball")

session.add(category7)
session.commit()

category8 = Category(name="Skating")

session.add(category8)
session.commit()

category9 = Category(name="Hockey")

session.add(category9)
session.commit()


print "added menu items!"
