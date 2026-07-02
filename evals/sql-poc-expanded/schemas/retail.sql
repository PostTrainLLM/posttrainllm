CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL);
CREATE TABLE products(id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price INTEGER NOT NULL);
CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL, status TEXT NOT NULL);
INSERT INTO customers VALUES (1,'Nia','Austin'),(2,'Omar','Boston'),(3,'Priya','Austin'),(4,'Quinn','Denver'),(5,'Rae','Boston');
INSERT INTO products VALUES
  (1,'Laptop','electronics',1200),(2,'Mouse','electronics',25),(3,'Desk','furniture',300),
  (4,'Chair','furniture',150),(5,'Notebook','stationery',8),(6,'Pen','stationery',3);
INSERT INTO orders VALUES
  (1,1,1,1,'shipped'),(2,1,2,2,'shipped'),(3,2,3,1,'pending'),(4,3,4,4,'shipped'),
  (5,4,5,10,'cancelled'),(6,5,6,20,'shipped'),(7,3,1,1,'pending'),(8,2,2,3,'shipped');
