CREATE TABLE departments(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE employees(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  dept_id INTEGER NOT NULL,
  salary INTEGER NOT NULL,
  FOREIGN KEY(dept_id) REFERENCES departments(id)
);

CREATE TABLE projects(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  owner_dept_id INTEGER NOT NULL,
  budget INTEGER NOT NULL,
  FOREIGN KEY(owner_dept_id) REFERENCES departments(id)
);

INSERT INTO departments VALUES
  (1, 'engineering'),
  (2, 'sales'),
  (3, 'support');

INSERT INTO employees VALUES
  (1, 'Alice', 1, 140000),
  (2, 'Bob', 2, 95000),
  (3, 'Carol', 1, 125000),
  (4, 'Dan', 3, 80000);

INSERT INTO projects VALUES
  (1, 'Apollo', 1, 200000),
  (2, 'Beacon', 2, 75000),
  (3, 'Cedar', 3, 50000);
