CREATE TABLE students(id INTEGER PRIMARY KEY, name TEXT NOT NULL, grade INTEGER NOT NULL, house TEXT NOT NULL);
CREATE TABLE courses(id INTEGER PRIMARY KEY, name TEXT NOT NULL, subject TEXT NOT NULL, credits INTEGER NOT NULL);
CREATE TABLE enrollments(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, course_id INTEGER NOT NULL, score INTEGER NOT NULL);
INSERT INTO students VALUES
  (1,'Ava',9,'red'),(2,'Ben',10,'blue'),(3,'Cleo',9,'green'),(4,'Dev',11,'red'),
  (5,'Elle',10,'blue'),(6,'Finn',12,'green'),(7,'Gita',11,'red'),(8,'Hank',12,'blue');
INSERT INTO courses VALUES
  (1,'Algebra','math',4),(2,'Biology','science',4),(3,'History','humanities',3),
  (4,'Poetry','arts',2),(5,'Robotics','science',5),(6,'Statistics','math',4);
INSERT INTO enrollments VALUES
  (1,1,1,91),(2,1,2,84),(3,2,3,77),(4,3,1,88),(5,4,5,95),(6,5,4,82),
  (7,6,6,90),(8,7,5,89),(9,8,2,73),(10,2,1,86),(11,5,6,92),(12,6,3,81);
