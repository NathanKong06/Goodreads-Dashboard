import pandas as pd
import time
from requests import Session, HTTPError
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, List, Optional, Callable

MAX_WORKERS = 8  
DELAY_SECONDS = 2
BASE_URL = "https://www.goodreads.com/book/show/"

s = Session()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
def scrape_book_data(book_id: str) -> Tuple[str, List[str], float]:
    url = f"{BASE_URL}{book_id}"
    genres: List[str] = []
    avg_rating: float = None

    time.sleep(DELAY_SECONDS) 

    try:
        response = s.get(url, headers=HEADERS)
        response.raise_for_status() 

        soup = BeautifulSoup(response.content, 'html.parser')

        #Extract Genres
        genre_elements = soup.select('.BookPageMetadataSection__genres .BookPageMetadataSection__genreButton')
        for element in genre_elements:
            genre_text = element.get_text().strip()
            genres.append(genre_text)
        # Extract Average Rating
        rating_element = soup.select_one('.RatingStatistics__rating')
        if rating_element:
            try:
                avg_rating = float(rating_element.get_text().strip())
            except Exception:
                avg_rating = None
        return book_id, genres, avg_rating

    except HTTPError as e:
        print(f"ERROR: Could not fetch book ID {book_id}. Status: {e.response.status_code}. Skipping.")
        return book_id, [], None
    except Exception as e:
        print(f"An unexpected error occurred for book ID {book_id}: {e}. Skipping.")
        return book_id, [], None

def enrich_library(df: pd.DataFrame, progress_callback: Optional[Callable[[int, int], None]] = None) -> Optional[pd.DataFrame]:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("enrich_library expects a pandas DataFrame as input")

    if 'Book Id' not in df.columns:
        return df

    df = df.copy()
    df['Book Id'] = df['Book Id'].astype(str)

    if 'Genres' not in df.columns:
        df['Genres'] = pd.NA
        need_enrich_mask = pd.Series(True, index=df.index)
    else:
        def _is_empty_genres(val):
            if pd.isna(val):
                return True
            if isinstance(val, list):
                return len(val) == 0
            if isinstance(val, str):
                s = val.strip()
                if s == "" or s == "[]":
                    return True
            return False

        need_enrich_mask = df['Genres'].apply(_is_empty_genres)

    if 'Exclusive Shelf' in df.columns:
        read_mask = df['Exclusive Shelf'].astype(str).str.lower() == 'read'
    else:
        read_mask = df['Date Read'].notna() if 'Date Read' in df.columns else pd.Series(False, index=df.index)

    final_mask = need_enrich_mask & read_mask

    book_ids_list = df.loc[final_mask, 'Book Id'].unique().tolist()
    book_ids_list = [str(id_str).strip() for id_str in book_ids_list if str(id_str).strip().isdigit()]

    if not book_ids_list:
        if progress_callback:
            try:
                progress_callback(0, 0)
            except Exception:
                pass
        return df

    results = []
    total = len(book_ids_list)
    completed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_id = {executor.submit(scrape_book_data, book_id): book_id for book_id in book_ids_list}
        for future in as_completed(future_to_id):
            book_id = future_to_id.get(future)
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                print(exc)
                results.append((book_id, [], None))
            finally:
                completed += 1
                if progress_callback:
                    try:
                        progress_callback(completed, total)
                    except Exception:
                        pass

    genre_map = {}
    rating_map = {}

    for book_id, genres, avg_rating in results:
        if isinstance(genres, (list, tuple)):
            genre_map[book_id] = list(genres)
        elif pd.isna(genres):
            genre_map[book_id] = []
        else:
            genre_map[book_id] = [genres]

        rating_map[book_id] = avg_rating

    if genre_map:
        mask = df['Book Id'].isin(genre_map.keys())
        df.loc[mask, 'Genres'] = df.loc[mask, 'Book Id'].map(genre_map)

    if rating_map:
        mapped_ratings = df['Book Id'].map(rating_map)

        if 'Average Rating' in df.columns:
            df['Average Rating'] = mapped_ratings.combine_first(df['Average Rating'])
        else:
            df['Average Rating'] = mapped_ratings

    return df