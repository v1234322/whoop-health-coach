import os
import psycopg2


DATABASE_URL = os.environ.get(
    "DATABASE_URL"
)


def get_connection():

    if not DATABASE_URL:
        raise Exception(
            "Missing DATABASE_URL"
        )

    return psycopg2.connect(
        DATABASE_URL
    )



def init_db():

    conn = get_connection()

    cur = conn.cursor()


    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS whoop_tokens
        (
            id INTEGER PRIMARY KEY,
            refresh_token TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )


    conn.commit()

    cur.close()

    conn.close()



def save_refresh_token(token):

    conn = get_connection()

    cur = conn.cursor()


    cur.execute(
        """
        INSERT INTO whoop_tokens
        (
            id,
            refresh_token
        )
        VALUES
        (
            1,
            %s
        )

        ON CONFLICT(id)

        DO UPDATE SET

        refresh_token =
        EXCLUDED.refresh_token,

        updated_at =
        NOW()

        """,
        (
            token,
        )
    )


    conn.commit()

    cur.close()

    conn.close()



def load_refresh_token():

    conn = get_connection()

    cur = conn.cursor()


    cur.execute(
        """
        SELECT refresh_token

        FROM whoop_tokens

        WHERE id = 1

        """
    )


    result = cur.fetchone()


    cur.close()

    conn.close()


    if result:

        return result[0]


    return None
