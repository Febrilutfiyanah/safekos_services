from insightface.app import FaceAnalysis
import cv2
import numpy as np

face_app = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)

face_app.prepare(
    ctx_id=0,
    det_size=(640, 640)
)


def generate_embedding(image_path):

    image = cv2.imread(image_path)

    faces = face_app.get(image)

    if len(faces) == 0:
        return None

    embedding = faces[0].embedding

    embedding = embedding / np.linalg.norm(embedding)

    return embedding.tolist()