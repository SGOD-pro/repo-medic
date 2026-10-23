from sqlalchemy import create_engine, text

engine = create_engine('sqlite:///:memory:')

def init_db():
    engine.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)'))
    engine.execute(text("INSERT INTO users (name) VALUES ('alice')"))

def get_user_count():
    res = engine.execute(text('SELECT count(*) FROM users'))
    return res.scalar()
