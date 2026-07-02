CREATE TABLE doctors(id INTEGER PRIMARY KEY, name TEXT NOT NULL, specialty TEXT NOT NULL);
CREATE TABLE patients(id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER NOT NULL, city TEXT NOT NULL);
CREATE TABLE visits(id INTEGER PRIMARY KEY, doctor_id INTEGER NOT NULL, patient_id INTEGER NOT NULL, reason TEXT NOT NULL, cost INTEGER NOT NULL);
INSERT INTO doctors VALUES (1,'Dr Rao','cardiology'),(2,'Dr Kim','pediatrics'),(3,'Dr Chen','dermatology'),(4,'Dr Singh','orthopedics');
INSERT INTO patients VALUES
  (1,'Lena',34,'Austin'),(2,'Milo',12,'Boston'),(3,'Nora',47,'Austin'),(4,'Paz',63,'Denver'),
  (5,'Remy',8,'Boston'),(6,'Sara',29,'Denver'),(7,'Tao',54,'Austin');
INSERT INTO visits VALUES
  (1,1,1,'checkup',220),(2,2,2,'fever',120),(3,3,3,'rash',180),(4,4,4,'knee',300),
  (5,2,5,'cough',110),(6,1,7,'chest pain',450),(7,3,6,'allergy',160),(8,4,1,'shoulder',280);
