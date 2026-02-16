import pandas as pd
from surprise import Dataset, Reader, SVD
from surprise.model_selection import train_test_split
from surprise import accuracy


# Recommend top-N books for a given user
def get_top_n_recommendations(user_id, df, model, n=5):
    all_books = df['book_url'].unique()
    rated_books = df[df['review_author'] == user_id]['book_url'].tolist()
    unrated_books = [book for book in all_books if book not in rated_books]

    predictions = [
        (book, model.predict(user_id, book).est) for book in unrated_books
    ]
    top_n = sorted(predictions, key=lambda x: x[1], reverse=True)[:n]
    return top_n

def main():
    # Load your CSV file
    df = pd.read_csv("reviews.csv")

    # Prepare the dataset
    ratings_df = df[['review_author', 'book_url', 'numeric_rating']]

    # Create a Surprise dataset
    reader = Reader(rating_scale=(1, 5))
    data = Dataset.load_from_df(ratings_df, reader)

    # Train/test split
    trainset, testset = train_test_split(data, test_size=0.2, random_state=42)

    # Train SVD model
    model = SVD()
    model.fit(trainset)

    # Evaluate
    predictions = model.test(testset)
    rmse = accuracy.rmse(predictions)
    print(f"Test RMSE: {rmse:.4f}")

    # Example usage
    user_id = 'Joan Frank'  # replace with any user in your dataset
    recommendations = get_top_n_recommendations(user_id, df, model, n=5)

    print(f"\nTop 5 recommendations for user '{user_id}':")
    for book, est_rating in recommendations:
        print(f"{book} — Predicted Rating: {est_rating:.2f}")