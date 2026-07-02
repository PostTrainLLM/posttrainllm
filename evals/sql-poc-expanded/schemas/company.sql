CREATE TABLE departments(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE employees(id INTEGER PRIMARY KEY, name TEXT NOT NULL, dept_id INTEGER NOT NULL, salary INTEGER NOT NULL, level TEXT NOT NULL);
CREATE TABLE projects(id INTEGER PRIMARY KEY, name TEXT NOT NULL, owner_dept_id INTEGER NOT NULL, budget INTEGER NOT NULL, status TEXT NOT NULL);
INSERT INTO departments VALUES (1,'engineering'),(2,'sales'),(3,'support'),(4,'finance');
INSERT INTO employees VALUES
  (1,'Alice',1,140000,'senior'),(2,'Bob',2,95000,'mid'),(3,'Carol',1,125000,'senior'),
  (4,'Dan',3,80000,'junior'),(5,'Eve',4,118000,'senior'),(6,'Frank',2,102000,'mid'),
  (7,'Grace',1,99000,'mid'),(8,'Heidi',3,76000,'junior');
INSERT INTO projects VALUES
  (1,'Apollo',1,200000,'active'),(2,'Beacon',2,75000,'active'),(3,'Cedar',3,50000,'paused'),
  (4,'Delta',4,120000,'active'),(5,'Echo',1,90000,'paused');
