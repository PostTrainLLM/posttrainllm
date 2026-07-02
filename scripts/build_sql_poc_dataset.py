#!/usr/bin/env python3
"""Build the expanded SQL POC dataset.

The first SQL POC proved the factory loop but used a tiny overlapping fixture.
This generator creates a deterministic, non-overlapping text-to-SQL set across
several SQLite domains plus preference pairs for SQL-only completions.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path


SYSTEM = "You are a text-to-SQL model. Return only one SQLite SELECT query, no markdown."


@dataclass(frozen=True)
class Example:
    domain: str
    question: str
    sql: str


@dataclass(frozen=True)
class Domain:
    name: str
    schema: str
    schema_prompt: str
    examples: list[Example]


def jdump(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def prompt(schema_prompt: str, question: str) -> str:
    return f"{SYSTEM} Schema: {schema_prompt}. Question: {question}"


def bad_completion(sql: str, idx: int) -> tuple[str, str]:
    styles = [
        ("prose_wrapped_sql", f"Answer: {sql}"),
        ("markdown_fence", f"```sql\n{sql}\n```"),
        ("extra_explanation", f"{sql} This query selects the requested rows."),
        ("missing_semicolon", sql.rstrip(";")),
    ]
    return styles[idx % len(styles)]


def build_domains() -> list[Domain]:
    company_schema = """
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
""".strip()
    company_prompt = (
        "departments(id, name); employees(id, name, dept_id, salary, level); "
        "projects(id, name, owner_dept_id, budget, status)"
    )
    company: list[Example] = []
    for dept in ["engineering", "sales", "support", "finance"]:
        company += [
            Example("company", f"List employee names in {dept}.",
                    f"select e.name from employees e join departments d on e.dept_id = d.id where d.name = '{dept}';"),
            Example("company", f"Count employees in {dept}.",
                    f"select count(*) from employees e join departments d on e.dept_id = d.id where d.name = '{dept}';"),
            Example("company", f"What is the highest salary in {dept}?",
                    f"select max(e.salary) from employees e join departments d on e.dept_id = d.id where d.name = '{dept}';"),
            Example("company", f"List active projects owned by {dept}.",
                    f"select p.name from projects p join departments d on p.owner_dept_id = d.id where d.name = '{dept}' and p.status = 'active';"),
        ]
    for threshold in [80000, 90000, 100000, 120000, 130000]:
        company += [
            Example("company", f"List employee names with salary above {threshold}.",
                    f"select name from employees where salary > {threshold};"),
            Example("company", f"List employee names with salary below {threshold}.",
                    f"select name from employees where salary < {threshold};"),
            Example("company", f"Count projects with budget above {threshold}.",
                    f"select count(*) from projects where budget > {threshold};"),
        ]
    for level in ["junior", "mid", "senior"]:
        company.append(Example("company", f"Count {level} employees.",
                               f"select count(*) from employees where level = '{level}';"))

    retail_schema = """
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
""".strip()
    retail_prompt = (
        "customers(id, name, city); products(id, name, category, price); "
        "orders(id, customer_id, product_id, quantity, status)"
    )
    retail: list[Example] = []
    for city in ["Austin", "Boston", "Denver"]:
        retail += [
            Example("retail", f"List customers from {city}.",
                    f"select name from customers where city = '{city}';"),
            Example("retail", f"Count shipped orders from customers in {city}.",
                    f"select count(*) from orders o join customers c on o.customer_id = c.id where c.city = '{city}' and o.status = 'shipped';"),
        ]
    for category in ["electronics", "furniture", "stationery"]:
        retail += [
            Example("retail", f"List product names in {category}.",
                    f"select name from products where category = '{category}';"),
            Example("retail", f"Average price for {category} products.",
                    f"select avg(price) from products where category = '{category}';"),
            Example("retail", f"Total quantity ordered for {category} products.",
                    f"select sum(o.quantity) from orders o join products p on o.product_id = p.id where p.category = '{category}';"),
        ]
    for status in ["shipped", "pending", "cancelled"]:
        retail.append(Example("retail", f"Count {status} orders.",
                              f"select count(*) from orders where status = '{status}';"))
    for price in [10, 50, 200, 1000]:
        retail += [
            Example("retail", f"List products cheaper than {price}.",
                    f"select name from products where price < {price};"),
            Example("retail", f"List products more expensive than {price}.",
                    f"select name from products where price > {price};"),
        ]

    library_schema = """
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
""".strip()
    library_prompt = (
        "authors(id, name, country); books(id, title, author_id, genre, pages); "
        "members(id, name, tier); loans(id, book_id, member_id, returned)"
    )
    library: list[Example] = []
    for country in ["USA", "Nigeria", "UK", "Japan"]:
        library += [
            Example("library", f"List book titles by authors from {country}.",
                    f"select b.title from books b join authors a on b.author_id = a.id where a.country = '{country}';"),
            Example("library", f"Count authors from {country}.",
                    f"select count(*) from authors where country = '{country}';"),
        ]
    for genre in ["fantasy", "sci-fi", "literary", "classic"]:
        library += [
            Example("library", f"List {genre} book titles.",
                    f"select title from books where genre = '{genre}';"),
            Example("library", f"Average pages for {genre} books.",
                    f"select avg(pages) from books where genre = '{genre}';"),
        ]
    for tier in ["gold", "silver", "bronze"]:
        library += [
            Example("library", f"Count {tier} members.",
                    f"select count(*) from members where tier = '{tier}';"),
            Example("library", f"List open loan book titles for {tier} members.",
                    f"select b.title from loans l join books b on l.book_id = b.id join members m on l.member_id = m.id where m.tier = '{tier}' and l.returned = 0;"),
        ]
    for pages in [250, 300, 400]:
        library += [
            Example("library", f"List books longer than {pages} pages.",
                    f"select title from books where pages > {pages};"),
            Example("library", f"Count books shorter than {pages} pages.",
                    f"select count(*) from books where pages < {pages};"),
        ]

    school_schema = """
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
""".strip()
    school_prompt = (
        "students(id, name, grade, house); courses(id, name, subject, credits); "
        "enrollments(id, student_id, course_id, score)"
    )
    school: list[Example] = []
    for house in ["red", "blue", "green"]:
        school += [
            Example("school", f"List student names in the {house} house.",
                    f"select name from students where house = '{house}';"),
            Example("school", f"Average enrollment score for {house} house students.",
                    f"select avg(e.score) from enrollments e join students s on e.student_id = s.id where s.house = '{house}';"),
            Example("school", f"Count students in the {house} house.",
                    f"select count(*) from students where house = '{house}';"),
        ]
    for subject in ["math", "science", "humanities", "arts"]:
        school += [
            Example("school", f"List course names in {subject}.",
                    f"select name from courses where subject = '{subject}';"),
            Example("school", f"Total credits for {subject} courses.",
                    f"select sum(credits) from courses where subject = '{subject}';"),
            Example("school", f"Average score in {subject} courses.",
                    f"select avg(e.score) from enrollments e join courses c on e.course_id = c.id where c.subject = '{subject}';"),
        ]
    for grade in [9, 10, 11, 12]:
        school += [
            Example("school", f"List students in grade {grade}.",
                    f"select name from students where grade = {grade};"),
            Example("school", f"Count enrollments for grade {grade} students.",
                    f"select count(*) from enrollments e join students s on e.student_id = s.id where s.grade = {grade};"),
        ]
    for threshold in [80, 85, 90]:
        school += [
            Example("school", f"List students with any score above {threshold}.",
                    f"select distinct s.name from enrollments e join students s on e.student_id = s.id where e.score > {threshold};"),
            Example("school", f"Count enrollments with score below {threshold}.",
                    f"select count(*) from enrollments where score < {threshold};"),
        ]

    clinic_schema = """
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
""".strip()
    clinic_prompt = (
        "doctors(id, name, specialty); patients(id, name, age, city); "
        "visits(id, doctor_id, patient_id, reason, cost)"
    )
    clinic: list[Example] = []
    for specialty in ["cardiology", "pediatrics", "dermatology", "orthopedics"]:
        clinic += [
            Example("clinic", f"List doctors in {specialty}.",
                    f"select name from doctors where specialty = '{specialty}';"),
            Example("clinic", f"Count visits handled by {specialty} doctors.",
                    f"select count(*) from visits v join doctors d on v.doctor_id = d.id where d.specialty = '{specialty}';"),
            Example("clinic", f"Average visit cost for {specialty}.",
                    f"select avg(v.cost) from visits v join doctors d on v.doctor_id = d.id where d.specialty = '{specialty}';"),
        ]
    for city in ["Austin", "Boston", "Denver"]:
        clinic += [
            Example("clinic", f"List patient names in {city}.",
                    f"select name from patients where city = '{city}';"),
            Example("clinic", f"Total visit cost for patients in {city}.",
                    f"select sum(v.cost) from visits v join patients p on v.patient_id = p.id where p.city = '{city}';"),
            Example("clinic", f"Count visits for patients in {city}.",
                    f"select count(*) from visits v join patients p on v.patient_id = p.id where p.city = '{city}';"),
        ]
    for age in [18, 30, 50, 60]:
        clinic += [
            Example("clinic", f"List patients older than {age}.",
                    f"select name from patients where age > {age};"),
            Example("clinic", f"Count patients younger than {age}.",
                    f"select count(*) from patients where age < {age};"),
        ]
    for cost in [150, 200, 300]:
        clinic += [
            Example("clinic", f"List visit reasons costing more than {cost}.",
                    f"select reason from visits where cost > {cost};"),
            Example("clinic", f"Count visits costing less than {cost}.",
                    f"select count(*) from visits where cost < {cost};"),
        ]

    return [
        Domain("company", company_schema, company_prompt, company),
        Domain("retail", retail_schema, retail_prompt, retail),
        Domain("library", library_schema, library_prompt, library),
        Domain("school", school_schema, school_prompt, school),
        Domain("clinic", clinic_schema, clinic_prompt, clinic),
    ]


def ensure_executes(db_path: Path, sql: str) -> None:
    with sqlite3.connect(db_path) as db:
        db.execute(sql).fetchall()


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(jdump(row) for row in rows) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evals/sql-poc-expanded")
    ap.add_argument("--seed", type=int, default=20260702)
    ap.add_argument("--dev-per-domain", type=int, default=18)
    ns = ap.parse_args()

    out = Path(ns.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "schemas").mkdir(exist_ok=True)
    (out / "dbs").mkdir(exist_ok=True)
    rng = random.Random(ns.seed)
    domains = build_domains()

    train_rows: list[dict[str, object]] = []
    dev_rows: list[dict[str, object]] = []
    preference_rows: list[dict[str, object]] = []
    manifest: dict[str, object] = {
        "dataset_id": "sql-poc-expanded-v1",
        "seed": ns.seed,
        "domains": [],
        "split": "domain-stratified deterministic shuffle; train/dev examples do not share question text or gold SQL",
    }

    for domain in domains:
        schema_path = out / "schemas" / f"{domain.name}.sql"
        schema_path.write_text(domain.schema + "\n")
        db_path = out / "dbs" / f"{domain.name}.db"
        if db_path.exists():
            db_path.unlink()
        with sqlite3.connect(db_path) as db:
            db.executescript(domain.schema)

        examples = list(domain.examples)
        rng.shuffle(examples)
        dev_count = min(ns.dev_per_domain, max(1, len(examples) // 3))
        dev = examples[:dev_count]
        train = examples[dev_count:]
        for i, ex in enumerate(train):
            ensure_executes(db_path, ex.sql)
            p = prompt(domain.schema_prompt, ex.question)
            train_rows.append({
                "id": f"{domain.name}-train-{i:03d}",
                "domain": domain.name,
                "instruction": p,
                "response": ex.sql,
            })
            failure_type, rejected = bad_completion(ex.sql, i)
            preference_rows.append({
                "id": f"{domain.name}-pref-{i:03d}",
                "domain": domain.name,
                "failure_type": failure_type,
                "prompt": p,
                "chosen": ex.sql,
                "rejected": rejected,
            })
        for i, ex in enumerate(dev):
            ensure_executes(db_path, ex.sql)
            dev_rows.append({
                "id": f"{domain.name}-dev-{i:03d}",
                "domain": domain.name,
                "question": ex.question,
                "prompt": prompt(domain.schema_prompt, ex.question),
                "gold_sql": ex.sql,
                "db": f"{domain.name}.db",
            })
        manifest["domains"].append({
            "name": domain.name,
            "schema": str(schema_path),
            "db": str(db_path),
            "train_rows": len(train),
            "dev_rows": len(dev),
        })

    train_pairs = {(r["instruction"], r["response"]) for r in train_rows}
    dev_pairs = {(r["prompt"], r["gold_sql"]) for r in dev_rows}
    if train_pairs & dev_pairs:
        raise SystemExit("train/dev overlap detected")

    write_jsonl(out / "train.jsonl", train_rows)
    write_jsonl(out / "dev.jsonl", dev_rows)
    write_jsonl(out / "preferences.jsonl", preference_rows)
    (out / "failure_taxonomy.json").write_text(jdump({
        "sql_wrong_schema": "Uses a table or column that does not exist.",
        "sql_wrong_filter": "Uses the wrong WHERE predicate or constant.",
        "sql_wrong_join": "Joins on the wrong key or skips a required join.",
        "sql_wrong_aggregation": "Uses the wrong aggregate or grouping.",
        "sql_prose_wrapped": "Contains correct-looking SQL plus prose or test text.",
        "sql_no_select": "Does not contain a SELECT statement.",
    }) + "\n")
    manifest["counts"] = {
        "train_rows": len(train_rows),
        "dev_rows": len(dev_rows),
        "preference_rows": len(preference_rows),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(train_rows)} train, {len(dev_rows)} dev, {len(preference_rows)} preference rows to {out}")


if __name__ == "__main__":
    main()
