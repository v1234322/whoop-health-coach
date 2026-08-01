import json
import os


TOKEN_FILE = "token.json"


def load_refresh_token():

    if os.path.exists(TOKEN_FILE):

        with open(
            TOKEN_FILE,
            "r"
        ) as f:

            data = json.load(f)

            return data.get(
                "refresh_token"
            )


    return os.environ.get(
        "WHOOP_REFRESH_TOKEN"
    )



def save_refresh_token(token):

    with open(
        TOKEN_FILE,
        "w"
    ) as f:

        json.dump(

            {
                "refresh_token": token
            },

            f

        )
