CREATE TABLE student (
    id INTEGER PRIMARY KEY,
    entyear INTEGER NOT NULL,
    stdNo TEXT NOT NULL UNIQUE,
    email TEXT,
    name1 TEXT,
    name2 TEXT,
    nickname TEXT,
    gender TEXT,
    COO TEXT,
    enrolled INTEGER DEFAULT 1
);