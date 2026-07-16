from deepface import DeepFace

DB_PATH = "known_faces"


def recognize(frame):

    try:

        result = DeepFace.find(
            img_path=frame,
            db_path=DB_PATH,
            model_name="ArcFace",
            detector_backend="opencv",
            enforce_detection=False,
            silent=True
        )

        if len(result[0]) > 0:

            identity = result[0]["identity"][0]

            nama = identity.split("\\")[-1].split(".")[0]

            return {
                "status": "resident",
                "name": nama
            }

        return {
            "status": "stranger",
            "name": None
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }