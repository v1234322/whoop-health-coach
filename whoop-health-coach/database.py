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
                CREATE TABLE IF NOT EXISTS whoop_daily
        (

            id SERIAL PRIMARY KEY,

            date DATE NOT NULL,

            recovery_score FLOAT,

            hrv FLOAT,

            resting_heart_rate FLOAT,


            sleep_score FLOAT,

            sleep_duration FLOAT,

            sleep_efficiency FLOAT,

            deep_sleep_duration FLOAT,

            rem_sleep_duration FLOAT,


            cycle_strain FLOAT,


            workout_data JSONB,


            raw_data JSONB,


            created_at TIMESTAMP DEFAULT NOW()

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



    # =========================
    # 检查今天是否已有记录
    # =========================


    cur.execute(

        """

        SELECT id

        FROM whoop_daily

        WHERE date = CURRENT_DATE

        LIMIT 1

        """

    )


    existing = cur.fetchone()





    values = (

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
            "sleep_efficiency"
        ),


        data.get(
            "deep_sleep_duration"
        ),


        data.get(
            "rem_sleep_duration"
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



        json.dumps(data)

    )





    # =========================
    # 今天已有数据 -> UPDATE
    # =========================


    if existing:



        cur.execute(

            """

            UPDATE whoop_daily

            SET


            recovery_score = %s,


            hrv = %s,


            resting_heart_rate = %s,


            sleep_score = %s,


            sleep_duration = %s,


            sleep_efficiency = %s,


            deep_sleep_duration = %s,


            rem_sleep_duration = %s,


            cycle_strain = %s,


            workout_data = %s,


            raw_data = %s,


            created_at = NOW()



            WHERE id = %s


            """,


            values + (

                existing[0],

            )


        )



        print(

            "WHOOP DAILY UPDATED"

        )





    # =========================
    # 今天没有数据 -> INSERT
    # =========================


    else:



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


            sleep_efficiency,


            deep_sleep_duration,


            rem_sleep_duration,


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


            %s,


            %s,


            %s,


            %s


            )


            """,


            values


        )



        print(

            "WHOOP DAILY INSERTED"

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
