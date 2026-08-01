import os
import json
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



# =========================
# INIT DATABASE
# =========================

def init_db():

    conn = get_connection()

    cur = conn.cursor()



    # =====================
    # WHOOP TOKEN TABLE
    # =====================

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



    # =====================
    # WHOOP DAILY DATA TABLE
    # =====================

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS whoop_daily
        (

            id SERIAL PRIMARY KEY,


            date DATE NOT NULL,


            recovery_score FLOAT,


            hrv FLOAT,


            resting_heart_rate FLOAT,


            sleep_score FLOAT,


            sleep_duration FLOAT,


            cycle_strain FLOAT,


            workout_data JSONB,


            raw_data JSONB,


            created_at TIMESTAMP DEFAULT NOW()

        )
        """
    )



    conn.commit()


    cur.close()

    conn.close()




# =========================
# SAVE REFRESH TOKEN
# =========================

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





# =========================
# LOAD REFRESH TOKEN
# =========================

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





# =========================
# SAVE DAILY WHOOP DATA
# =========================

def save_daily_data(data):


    conn = get_connection()

    cur = conn.cursor()



    cur.execute(

        """

        INSERT INTO whoop_daily

        (

            date,

            recovery_score,

            hrv,

            resting_heart_rate,

            sleep_score,

            sleep_duration,

            cycle_strain,

            workout_data,

            raw_data

        )


        VALUES

        (

            CURRENT_DATE,

            %s,

            %s,

            %s,

            %s,

            %s,

            %s,

            %s,

            %s

        )


        """,


        (

            data.get(
                "recovery_score"
            ),


            data.get(
                "hrv"
            ),


            data.get(
                "resting_heart_rate"
            ),


            data.get(
                "sleep_score"
            ),


            data.get(
                "sleep_duration"
            ),


            data.get(
                "cycle_strain"
            ),


            json.dumps(
                data.get(
                    "workout_data",
                    {}
                )
            ),


            json.dumps(
                data
            )

        )

    )



    conn.commit()


    cur.close()

    conn.close()




# =========================
# LOAD 7 DAYS DATA
# =========================

def load_last_7_days():


    conn = get_connection()

    cur = conn.cursor()



    cur.execute(

        """

        SELECT

            date,

            recovery_score,

            hrv,

            resting_heart_rate,

            sleep_score,

            sleep_duration,

            cycle_strain


        FROM whoop_daily


        ORDER BY date DESC


        LIMIT 7


        """

    )



    rows = cur.fetchall()



    cur.close()

    conn.close()



    return rows
