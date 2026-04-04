# Import database connection helper
from app.database import get_db_connection


# A Fixed skill list 
SKILLS = [
    "Python",
    "SQL",
    "Java",
    "AWS",
    "Azure",
    "GCP",
    "Spark",
    "Airflow",
    "Docker",
    "PostgreSQL",
    "FastAPI",
    "Git",
]

def extract_skills_from_text(text):
    matched_skills = []

    # Convert text to lower case for case-insensitive matching
    lower_text = text.lower()

    for skill in SKILLS:
        if skill.lower() in lower_text:
            matched_skills.append(skill)
    
    return matched_skills


def insert_skill(cur, skill_name):
    # Insert skill if not already existed
    cur.execute(
        """
        INSERT INTO skills_extracted (skill_name)
        VALUES (%s)
        ON CONFLICT (skill_name) DO NOTHING;
        """,
        (skill_name,)
    )

    # Get skill id
    cur.execute(
        """
        SELECT id
        FROM skills_extracted
        WHERE skill_name = %s;
        """,
        (skill_name,)
    )

    return cur.fetchone()[0]


def insert_job_skill_map(cur, job_id, skill_id):
    cur.execute(
        """
        INSERT INTO job_skill_map (job_id, skill_id)
        VALUES (%s, %s)
        ON CONFLICT (job_id, skill_id) DO NOTHING;
        """,
        (job_id, skill_id)
    )


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            id,
            title,
            description
        FROM jobs_cleaned;
        """
    )

    jobs = cur.fetchall()

    for job in jobs:
        job_id, title, description = job

        # Combine title and description for matching
        full_text = f"{title} {description or ''}"

        matched_skills = extract_skills_from_text(full_text)

        # Insert matched skills and link them to current job
        for skill in matched_skills:
            skill_id = insert_skill(cur, skill)
            insert_job_skill_map(cur, job_id, skill_id)


        print(f"Job ID: {job_id}")
        print(f"Matched skills: {matched_skills}")
        print("-" * 40)
    
    conn.commit()

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()