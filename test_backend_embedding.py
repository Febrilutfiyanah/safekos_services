from ai.arcface_service import generate_embedding

embedding = generate_embedding("uploads/test.jpg")

if embedding is None:
    print("Wajah tidak ditemukan")
else:
    print(type(embedding))
    print("Panjang:", len(embedding))
    print("5 nilai pertama:", embedding[:5])