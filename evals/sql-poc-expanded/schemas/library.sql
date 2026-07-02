CREATE TABLE authors(id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL);
CREATE TABLE books(id INTEGER PRIMARY KEY, title TEXT NOT NULL, author_id INTEGER NOT NULL, genre TEXT NOT NULL, pages INTEGER NOT NULL);
CREATE TABLE members(id INTEGER PRIMARY KEY, name TEXT NOT NULL, tier TEXT NOT NULL);
CREATE TABLE loans(id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL, member_id INTEGER NOT NULL, returned INTEGER NOT NULL);
INSERT INTO authors VALUES (1,'Le Guin','USA'),(2,'Achebe','Nigeria'),(3,'Austen','UK'),(4,'Murakami','Japan');
INSERT INTO books VALUES
  (1,'Earthsea',1,'fantasy',320),(2,'Dispossessed',1,'sci-fi',380),(3,'Things Fall Apart',2,'literary',209),
  (4,'Pride and Prejudice',3,'classic',279),(5,'Kafka on the Shore',4,'literary',505),(6,'Norwegian Wood',4,'literary',296);
INSERT INTO members VALUES (1,'Mina','gold'),(2,'Noah','silver'),(3,'Ira','gold'),(4,'Sol','bronze');
INSERT INTO loans VALUES (1,1,1,1),(2,2,2,0),(3,3,3,1),(4,4,1,0),(5,5,4,0),(6,6,2,1);
